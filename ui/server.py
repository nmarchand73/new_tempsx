#!/usr/bin/env python3
"""Serveur local pour l'UI NEW TEMPS X (sert l'UI et les fichiers d'un run)."""

import argparse
import datetime
import json
import re
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
UI_DIR = Path(__file__).resolve().parent

# Un nom de run / de fichier ne contient jamais de séparateur de chemin.
SAFE_NAME = re.compile(r"^[^/\\\x00]+$")

IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def safe_child(base: Path, name: str) -> Path | None:
    """Retourne base/name s'il reste dans base, sinon None (anti path-traversal)."""
    if not name or name in (".", "..") or not SAFE_NAME.match(name):
        return None
    candidate = (base / name).resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError:
        return None
    return candidate


def list_runs() -> list[Path]:
    """Runs contenant un episode.json, du plus récent au plus ancien."""
    if not OUTPUT_DIR.is_dir():
        return []
    runs = [d for d in OUTPUT_DIR.iterdir() if d.is_dir() and (d / "episode.json").is_file()]
    return sorted(runs, key=lambda d: (d / "episode.json").stat().st_mtime, reverse=True)


class EpisodeHandler(SimpleHTTPRequestHandler):
    """Sert l'UI statique et l'API /api/* (lecture seule)."""

    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".mp3": "audio/mpeg", ".js": "text/javascript"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(UI_DIR), **kwargs)

    # --- routage -----------------------------------------------------------
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        run = query.get("run", [None])[0]

        if path == "/api/runs":
            return self._json(self._runs_payload())
        if path == "/api/episode.json":
            run_dir = self._resolve_run(run)
            if run_dir is None:
                return
            return self._send_file(run_dir / "episode.json", "application/json; charset=utf-8")
        if path.startswith("/api/audio/"):
            return self._serve_audio(unquote(path[len("/api/audio/") :]), run)
        if path.startswith("/api/images/"):
            return self._serve_image(unquote(path[len("/api/images/") :]), run)
        if path.startswith("/api/"):
            return self.send_error(HTTPStatus.NOT_FOUND)
        return super().do_GET()  # fichiers statiques (traversée gérée par la stdlib)

    do_HEAD = do_GET

    # --- helpers -----------------------------------------------------------
    def _resolve_run(self, run: str | None) -> Path | None:
        """Dossier du run demandé (ou du plus récent). Envoie l'erreur HTTP si invalide."""
        if run is None:
            runs = list_runs()
            if not runs:
                self.send_error(HTTPStatus.NOT_FOUND, "No runs found")
                return None
            return runs[0]
        run_dir = safe_child(OUTPUT_DIR, run)
        if run_dir is None or not run_dir.is_dir():
            self.send_error(HTTPStatus.NOT_FOUND, "Run not found")
            return None
        return run_dir

    def _runs_payload(self) -> list[dict]:
        payload = []
        for run_dir in list_runs():
            episode_json = run_dir / "episode.json"
            try:
                data = json.loads(episode_json.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                print(f"Warning: could not read {episode_json}: {exc}")
                continue
            mtime = episode_json.stat().st_mtime
            scenario = data.get("scenario_input", "")
            payload.append(
                {
                    "name": run_dir.name,
                    "title": data.get("episode_title", run_dir.name),
                    "scenario": scenario[:100] + "..." if len(scenario) > 100 else scenario,
                    "date": datetime.datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M"),
                    "timestamp": mtime,
                }
            )
        return payload

    def _json(self, obj) -> None:
        body = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _serve_audio(self, act_key: str, run: str | None) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_]+", act_key):
            return self.send_error(HTTPStatus.BAD_REQUEST, "Invalid act key")
        run_dir = self._resolve_run(run)
        if run_dir is None:
            return
        files = sorted((run_dir / "audio").glob(f"{act_key}_*.mp3"))
        if not files:
            return self.send_error(HTTPStatus.NOT_FOUND, "Audio not found")
        self._send_file(files[0], "audio/mpeg", ranges=True)

    def _serve_image(self, filename: str, run: str | None) -> None:
        run_dir = self._resolve_run(run)
        if run_dir is None:
            return
        image = safe_child(run_dir / "images", filename)
        ctype = IMAGE_TYPES.get(image.suffix.lower()) if image else None
        if image is None or ctype is None or not image.is_file():
            return self.send_error(HTTPStatus.NOT_FOUND, "Image not found")
        self._send_file(image, ctype)

    def _send_file(self, file_path: Path, content_type: str, ranges: bool = False) -> None:
        """Envoie un fichier, avec support des requêtes Range (lecture audio)."""
        try:
            size = file_path.stat().st_size
        except OSError:
            return self.send_error(HTTPStatus.NOT_FOUND)
        start, end, status = 0, size - 1, HTTPStatus.OK
        header = self.headers.get("Range") if ranges else None
        if header:
            m = re.fullmatch(r"bytes=(\d*)-(\d*)", header.strip())
            if not m or not (m.group(1) or m.group(2)):
                return self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            if m.group(1):
                start = int(m.group(1))
                end = min(int(m.group(2)), size - 1) if m.group(2) else size - 1
            else:  # suffixe : "bytes=-N"
                start = max(0, size - int(m.group(2)))
            if start > end or start >= size:
                return self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            status = HTTPStatus.PARTIAL_CONTENT
        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        if ranges:
            self.send_header("Accept-Ranges", "bytes")
        if status == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(file_path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def log_message(self, format, *args):
        print(f"[{self.address_string()}] {format % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Serveur UI NEW TEMPS X")
    parser.add_argument("--host", default="127.0.0.1", help="Adresse d'écoute (défaut: 127.0.0.1, local uniquement)")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    count = len(list_runs())
    print(
        f"📊 {count} run(s) disponible(s)"
        if count
        else f"⚠️  Aucun run dans {OUTPUT_DIR} (lancez d'abord: python app.py)"
    )
    print(f"🚀 http://{args.host}:{args.port}  (Ctrl+C pour arrêter)")
    with ThreadingHTTPServer((args.host, args.port), EpisodeHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Arrêt du serveur...")


if __name__ == "__main__":
    main()
