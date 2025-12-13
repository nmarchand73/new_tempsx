"""Script pour corriger les URLs d'images dans les fichiers JSON d'épisodes.

Convertit les URLs thumb en format direct et supprime les images invalides.
"""

import json
import re
import requests
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def convert_thumb_to_direct(url: str) -> str:
    """Convertit une URL thumb Wikimedia Commons en URL directe."""
    thumb_pattern = r'/thumb/(.+?)/(\d+px-.+)$'
    match = re.search(thumb_pattern, url)
    
    if match:
        path = match.group(1)
        if 'upload.wikimedia.org/wikipedia/commons' in url:
            base_url = 'https://upload.wikimedia.org/wikipedia/commons/'
        elif 'upload.wikimedia.org/wikipedia/en' in url:
            base_url = 'https://upload.wikimedia.org/wikipedia/en/'
        else:
            domain_match = re.search(r'(https://upload\.wikimedia\.org/wikipedia/[^/]+)', url)
            if domain_match:
                base_url = domain_match.group(1) + '/'
            else:
                return url
        return base_url + path
    return url


def is_valid_image_url(url: str, timeout: int = 3) -> bool:
    """Vérifie si une URL d'image est accessible."""
    try:
        response = requests.head(url, timeout=timeout, allow_redirects=True)
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '')
            return 'image' in content_type.lower()
        return False
    except Exception:
        return False


def fix_images_in_content(content: str) -> tuple[str, int, int]:
    """Corrige les URLs d'images dans un contenu markdown.
    
    Returns:
        Tuple (contenu corrigé, nombre de conversions, nombre de suppressions)
    """
    pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
    converted = 0
    removed = 0
    
    def replace_image(match):
        nonlocal converted, removed
        alt_text = match.group(1)
        url = match.group(2).strip()
        
        # Convertir les URLs thumb
        if '/thumb/' in url and 'upload.wikimedia.org' in url:
            direct_url = convert_thumb_to_direct(url)
            if direct_url != url:
                if is_valid_image_url(direct_url):
                    converted += 1
                    logger.info(f"✅ Conversion: {url[:60]}... -> {direct_url[:60]}...")
                    return f"![{alt_text}]({direct_url})"
                else:
                    logger.warning(f"❌ URL directe invalide: {direct_url[:60]}...")
                    removed += 1
                    return ""  # Supprimer l'image
            else:
                if not is_valid_image_url(url):
                    removed += 1
                    return ""
        else:
            # Vérifier les URLs non-thumb
            if 'upload.wikimedia.org' in url and not is_valid_image_url(url):
                logger.warning(f"❌ URL invalide: {url[:60]}...")
                removed += 1
                return ""
        
        return match.group(0)  # Garder l'image originale
    
    fixed_content = re.sub(pattern, replace_image, content)
    # Nettoyer les lignes vides multiples causées par les suppressions
    fixed_content = re.sub(r'\n\n\n+', '\n\n', fixed_content)
    
    return fixed_content, converted, removed


def fix_json_file(json_path: Path, dry_run: bool = False) -> tuple[int, int]:
    """Corrige les URLs d'images dans un fichier JSON d'épisode."""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            episode = json.load(f)
    except Exception as e:
        logger.error(f"Erreur lors de la lecture de {json_path}: {e}")
        return 0, 0
    
    total_converted = 0
    total_removed = 0
    
    # Corriger les images dans chaque acte
    if 'acts' in episode:
        for act_key, act_data in episode['acts'].items():
            if 'content' in act_data:
                fixed_content, converted, removed = fix_images_in_content(act_data['content'])
                if fixed_content != act_data['content']:
                    act_data['content'] = fixed_content
                    total_converted += converted
                    total_removed += removed
    
    # Corriger les images dans l'arc narratif
    if 'narrative_arc' in episode:
        fixed_arc, converted, removed = fix_images_in_content(episode['narrative_arc'])
        if fixed_arc != episode['narrative_arc']:
            episode['narrative_arc'] = fixed_arc
            total_converted += converted
            total_removed += removed
    
    # Corriger les images dans l'histoire Twilight Zone
    if 'twilight_zone_story' in episode and 'story' in episode['twilight_zone_story']:
        fixed_story, converted, removed = fix_images_in_content(episode['twilight_zone_story']['story'])
        if fixed_story != episode['twilight_zone_story']['story']:
            episode['twilight_zone_story']['story'] = fixed_story
            total_converted += converted
            total_removed += removed
    
    # Sauvegarder si des modifications ont été faites
    if (total_converted > 0 or total_removed > 0) and not dry_run:
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(episode, f, ensure_ascii=False, indent=2)
            logger.info(f"✅ {json_path.name}: {total_converted} convertie(s), {total_removed} supprimée(s)")
        except Exception as e:
            logger.error(f"Erreur lors de l'écriture de {json_path}: {e}")
            return 0, 0
    
    return total_converted, total_removed


def main():
    """Fonction principale."""
    import sys
    
    dry_run = '--dry-run' in sys.argv or '-n' in sys.argv
    
    output_dir = Path("output")
    if not output_dir.exists():
        logger.error(f"Le répertoire {output_dir} n'existe pas")
        return
    
    total_converted = 0
    total_removed = 0
    files_processed = 0
    
    # Parcourir tous les répertoires de runs
    for run_dir in sorted(output_dir.iterdir()):
        if not run_dir.is_dir():
            continue
        
        json_file = run_dir / "episode.json"
        if json_file.exists():
            converted, removed = fix_json_file(json_file, dry_run=dry_run)
            total_converted += converted
            total_removed += removed
            if converted > 0 or removed > 0:
                files_processed += 1
    
    logger.info(f"\n{'[DRY RUN] ' if dry_run else ''}✅ Correction terminée:")
    logger.info(f"   - Fichiers modifiés: {files_processed}")
    logger.info(f"   - URLs converties: {total_converted}")
    logger.info(f"   - Images invalides supprimées: {total_removed}")


if __name__ == "__main__":
    main()

