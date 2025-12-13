#!/usr/bin/env python3
"""Serveur simple pour servir l'UI NEW TEMPS X avec le JSON de l'épisode."""

import http.server
import socketserver
import json
import os
from pathlib import Path
from urllib.parse import urlparse, parse_qs

PORT = 8000
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
UI_DIR = Path(__file__).parent


class EpisodeHandler(http.server.SimpleHTTPRequestHandler):
    """Handler personnalisé pour servir l'UI et le JSON de l'épisode."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(UI_DIR), **kwargs)
    
    def do_HEAD(self):
        """Gère les requêtes HEAD (pour vérifier l'existence des fichiers)."""
        # HEAD est identique à GET mais sans body
        # On utilise self.command pour différencier dans les méthodes
        self.do_GET()
    
    def do_GET(self):
        """Gère les requêtes GET."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        # Route pour lister les runs
        if path == '/api/runs':
            self.serve_runs_list()
            return
        
        # Route pour l'API JSON (avec run optionnel)
        if path == '/api/episode.json' or path.startswith('/api/episode.json'):
            self.serve_episode_json(path)
            return
        
        # Route pour l'API audio
        if path.startswith('/api/audio/'):
            self.serve_audio_file(path)
            return
        
        # Route pour l'API images
        if path.startswith('/api/images/'):
            self.serve_image_file(path)
            return
        
        # Route pour la racine
        if path == '/' or path == '/index.html':
            self.serve_file(UI_DIR / 'index.html', 'text/html')
            return
        
        # Servir les fichiers statiques (CSS, JS, etc.)
        file_path = UI_DIR / path.lstrip('/')
        # Vérifier que le fichier est bien dans UI_DIR (sécurité)
        try:
            file_path.resolve().relative_to(UI_DIR.resolve())
        except ValueError:
            self.send_error(403, "Access denied")
            return
        
        if file_path.exists() and file_path.is_file():
            self.serve_file(file_path, self.guess_content_type(file_path))
        else:
            self.send_error(404, f"File not found: {path}")
    
    def serve_runs_list(self):
        """Liste tous les runs disponibles."""
        try:
            if not OUTPUT_DIR.exists():
                runs = []
            else:
                # Lister tous les répertoires dans output/ qui contiennent un episode.json
                runs = []
                run_dirs = []
                for run_dir in OUTPUT_DIR.iterdir():
                    if run_dir.is_dir():
                        episode_json = run_dir / "episode.json"
                        if episode_json.exists():
                            run_dirs.append((run_dir, episode_json))
                
                # Trier par date de modification (plus récent en premier)
                run_dirs.sort(key=lambda x: x[1].stat().st_mtime, reverse=True)
                
                for run_dir, episode_json in run_dirs:
                    try:
                        with open(episode_json, 'r', encoding='utf-8') as f:
                            episode_data = json.load(f)
                        run_name = run_dir.name
                        episode_title = episode_data.get('episode_title', run_name)
                        scenario = episode_data.get('scenario_input', '')
                        
                        # Extraire la date depuis le timestamp dans le nom ou utiliser la date de modification
                        import datetime
                        mtime = episode_json.stat().st_mtime
                        date_created = datetime.datetime.fromtimestamp(mtime)
                        date_str = date_created.strftime("%d/%m/%Y %H:%M")
                        
                        runs.append({
                            'name': run_name,
                            'title': episode_title,
                            'scenario': scenario[:100] + '...' if len(scenario) > 100 else scenario,
                            'date': date_str,
                            'timestamp': mtime
                        })
                    except Exception as e:
                        # Ignorer les erreurs de lecture mais logger pour debug
                        print(f"Warning: Could not read {episode_json}: {e}")
                        pass
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(runs, ensure_ascii=False, indent=2).encode('utf-8'))
        except Exception as e:
            self.send_error(500, f"Error listing runs: {str(e)}")
    
    def serve_episode_json(self, path: str = '/api/episode.json'):
        """Sert le JSON de l'épisode pour un run spécifique."""
        try:
            # Extraire le nom du run depuis les query params
            parsed_path = urlparse(self.path)
            query_params = parse_qs(parsed_path.query)
            run_name = query_params.get('run', [None])[0]
            
            # Si pas de run spécifié, utiliser le plus récent
            if not run_name:
                # Trouver le run le plus récent
                if OUTPUT_DIR.exists():
                    run_dirs = [d for d in OUTPUT_DIR.iterdir() if d.is_dir() and (d / "episode.json").exists()]
                    if run_dirs:
                        run_dirs.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                        run_name = run_dirs[0].name
                    else:
                        self.send_error(404, "No runs found")
                        return
                else:
                    self.send_error(404, "Output directory not found")
                    return
            
            episode_json = OUTPUT_DIR / run_name / "episode.json"
            if not episode_json.exists():
                self.send_error(404, f"Episode JSON not found for run: {run_name}")
                return
            
            with open(episode_json, 'r', encoding='utf-8') as f:
                episode_data = json.load(f)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(episode_data, ensure_ascii=False, indent=2).encode('utf-8'))
        except Exception as e:
            self.send_error(500, f"Error loading episode: {str(e)}")
    
    def serve_file(self, file_path, content_type, support_range=False):
        """Sert un fichier statique.
        
        Args:
            file_path: Chemin du fichier à servir
            content_type: Type MIME du fichier
            support_range: Si True, supporte les requêtes Range (pour streaming audio/video)
        """
        try:
            if isinstance(file_path, str):
                # Si c'est un chemin relatif, le résoudre depuis UI_DIR
                if not Path(file_path).is_absolute():
                    file_path = UI_DIR / file_path
                else:
                    file_path = Path(file_path)
            else:
                file_path = Path(file_path)
            
            # Vérifier que le fichier existe
            if not file_path.exists():
                self.send_error(404, f"File not found: {file_path}")
                return
            
            file_size = file_path.stat().st_size
            
            # Support des requêtes Range pour le streaming
            if support_range and 'Range' in self.headers:
                range_header = self.headers['Range']
                # Parser la requête Range (ex: "bytes=0-1023")
                if range_header.startswith('bytes='):
                    ranges = range_header.replace('bytes=', '').split('-')
                    start = int(ranges[0]) if ranges[0] else 0
                    end = int(ranges[1]) if ranges[1] else file_size - 1
                    
                    if start < 0 or end >= file_size or start > end:
                        self.send_error(416, "Range Not Satisfiable")
                        return
                    
                    content_length = end - start + 1
                    
                    with open(file_path, 'rb') as f:
                        f.seek(start)
                        content = f.read(content_length)
                    
                    self.send_response(206)  # Partial Content
                    self.send_header('Content-Type', content_type)
                    self.send_header('Content-Length', str(content_length))
                    self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
                    self.send_header('Accept-Ranges', 'bytes')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    # Ne pas envoyer le body pour les requêtes HEAD
                    if self.command != 'HEAD':
                        self.wfile.write(content)
                    return
            
            # Lecture normale du fichier
            with open(file_path, 'rb') as f:
                content = f.read()
            
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            if support_range:
                self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            # Ne pas envoyer le body pour les requêtes HEAD
            if self.command != 'HEAD':
                self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Error serving file: {str(e)}")
    
    def serve_audio_file(self, path):
        """Sert un fichier audio en cherchant par actKey dans le run spécifié."""
        try:
            # Extraire l'actKey et le run depuis le chemin
            # Format: /api/audio/acte_1?run=run_name
            parsed_path = urlparse(self.path)
            query_params = parse_qs(parsed_path.query)
            run_name = query_params.get('run', [None])[0]
            
            # Extraire l'actKey du chemin (ex: /api/audio/acte_1 -> acte_1)
            act_key = path.replace('/api/audio/', '').split('?')[0].strip()
            if not act_key:
                self.send_error(400, "Act key missing")
                return
            
            # Si pas de run spécifié, utiliser le plus récent
            if not run_name:
                if OUTPUT_DIR.exists():
                    run_dirs = [d for d in OUTPUT_DIR.iterdir() if d.is_dir() and (d / "episode.json").exists()]
                    if run_dirs:
                        run_dirs.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                        run_name = run_dirs[0].name
                    else:
                        self.send_error(404, "No runs found")
                        return
                else:
                    self.send_error(404, "Output directory not found")
                    return
            
            # Chercher le fichier audio dans le répertoire du run
            audio_dir = OUTPUT_DIR / run_name / "audio"
            if not audio_dir.exists():
                self.send_error(404, f"Audio directory not found for run: {run_name}")
                return
            
            # Chercher un fichier qui commence par l'actKey
            # Pour twilight_zone, chercher aussi "twilight_zone_*.mp3"
            if act_key == "twilight_zone":
                matching_files = list(audio_dir.glob("twilight_zone_*.mp3"))
            else:
                matching_files = list(audio_dir.glob(f"{act_key}_*.mp3"))
            
            if not matching_files:
                self.send_error(404, f"Audio file not found for {act_key} in run {run_name}")
                return
            
            # Prendre le premier fichier trouvé (normalement il n'y en a qu'un)
            audio_file = matching_files[0]
            
            # Si c'est une requête HEAD, juste confirmer que le fichier existe
            if self.command == 'HEAD':
                self.send_response(200)
                self.send_header('Content-Type', 'audio/mpeg')
                self.send_header('Content-Length', str(audio_file.stat().st_size))
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                return
            
            # Servir le fichier avec support du streaming (Range requests)
            self.serve_file(audio_file, 'audio/mpeg', support_range=True)
            
        except Exception as e:
            self.send_error(500, f"Error serving audio: {str(e)}")
    
    def serve_image_file(self, path):
        """Sert un fichier image en cherchant dans le répertoire images du run spécifié."""
        try:
            # Extraire le nom du fichier image et le run depuis le chemin
            # Format: /api/images/filename.png?run=run_name
            parsed_path = urlparse(self.path)
            query_params = parse_qs(parsed_path.query)
            run_name = query_params.get('run', [None])[0]
            
            # Extraire le nom du fichier du chemin (ex: /api/images/acte_1_xxx.png -> acte_1_xxx.png)
            image_filename = path.replace('/api/images/', '').split('?')[0].strip()
            if not image_filename:
                self.send_error(400, "Image filename missing")
                return
            
            # Si pas de run spécifié, utiliser le plus récent
            if not run_name:
                if OUTPUT_DIR.exists():
                    run_dirs = [d for d in OUTPUT_DIR.iterdir() if d.is_dir() and (d / "episode.json").exists()]
                    if run_dirs:
                        run_dirs.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                        run_name = run_dirs[0].name
                    else:
                        self.send_error(404, "No runs found")
                        return
                else:
                    self.send_error(404, "Output directory not found")
                    return
            
            # Chercher le fichier image dans le répertoire du run
            images_dir = OUTPUT_DIR / run_name / "images"
            if not images_dir.exists():
                self.send_error(404, f"Images directory not found for run: {run_name}")
                return
            
            image_file = images_dir / image_filename
            if not image_file.exists():
                self.send_error(404, f"Image file not found: {image_filename} in run {run_name}")
                return
            
            # Servir le fichier image
            self.serve_file(image_file, self.guess_content_type(image_file))
            
        except Exception as e:
            self.send_error(500, f"Error serving image: {str(e)}")
    
    def guess_content_type(self, file_path):
        """Devine le type de contenu d'un fichier."""
        suffix = file_path.suffix.lower()
        content_types = {
            '.html': 'text/html',
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.json': 'application/json',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.svg': 'image/svg+xml',
            '.mp3': 'audio/mpeg',
            '.mp4': 'video/mp4',
            '.wav': 'audio/wav',
        }
        return content_types.get(suffix, 'application/octet-stream')
    
    def log_message(self, format, *args):
        """Override pour un logging plus propre."""
        print(f"[{self.address_string()}] {format % args}")


def main():
    """Lance le serveur."""
    if not OUTPUT_DIR.exists():
        print(f"⚠️  Avertissement: {OUTPUT_DIR} n'existe pas encore.")
        print("   Générez d'abord un épisode avec: python app.py")
        print()
    else:
        # Compter les runs disponibles
        run_count = len([d for d in OUTPUT_DIR.iterdir() if d.is_dir() and (d / "episode.json").exists()])
        if run_count == 0:
            print(f"⚠️  Avertissement: Aucun run trouvé dans {OUTPUT_DIR}")
            print("   Générez d'abord un épisode avec: python app.py")
            print()
        else:
            print(f"📊 {run_count} run(s) disponible(s)")
    
    print(f"🚀 Serveur NEW TEMPS X démarré sur http://localhost:{PORT}")
    print(f"📁 UI: {UI_DIR}")
    print(f"📁 Output: {OUTPUT_DIR}")
    print()
    print("Appuyez sur Ctrl+C pour arrêter le serveur.")
    print()
    
    with socketserver.TCPServer(("", PORT), EpisodeHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Arrêt du serveur...")
            httpd.shutdown()


if __name__ == "__main__":
    main()

