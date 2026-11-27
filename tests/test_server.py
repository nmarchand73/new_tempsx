import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from ui import server


@pytest.fixture
def base_url(tmp_path, monkeypatch):
    out = tmp_path / "output"
    run = out / "run1"
    (run / "audio").mkdir(parents=True)
    (run / "images").mkdir()
    (run / "episode.json").write_text(json.dumps({"episode_title": "T", "scenario_input": "s"}))
    (run / "audio" / "acte_1_x.mp3").write_bytes(b"0123456789")
    (run / "images" / "a.png").write_bytes(b"PNG")
    (tmp_path / "secret.json").write_text("SECRET")
    (out / "other").mkdir()
    (out / "other" / "episode.json").write_text("{}")
    monkeypatch.setattr(server, "OUTPUT_DIR", out)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.EpisodeHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""


def test_runs_and_episode(base_url):
    assert get(base_url + "/api/runs")[0] == 200
    status, body = get(base_url + "/api/episode.json?run=run1")
    assert status == 200 and json.loads(body)["episode_title"] == "T"


@pytest.mark.parametrize("run", ["..", "../..", "%2e%2e", "run1/../other", "..%2Fsecret"])
def test_run_traversal_blocked(base_url, run):
    assert get(base_url + f"/api/episode.json?run={run}")[0] == 404


@pytest.mark.parametrize("name", ["..%2F..%2Fsecret.json", "%2e%2e%2fepisode.json", "../episode.json", "a.txt"])
def test_image_traversal_blocked(base_url, name):
    assert get(base_url + f"/api/images/{name}?run=run1")[0] in (400, 404)


def test_image_ok(base_url):
    assert get(base_url + "/api/images/a.png?run=run1") == (200, b"PNG")


def test_audio_range(base_url):
    status, body = get(base_url + "/api/audio/acte_1?run=run1", {"Range": "bytes=2-4"})
    assert (status, body) == (206, b"234")
    assert get(base_url + "/api/audio/acte_1?run=run1", {"Range": "bytes=50-60"})[0] == 416
    assert get(base_url + "/api/audio/..%2Fx?run=run1")[0] == 400
