"""Script pour convertir toutes les URLs d'images thumb en format direct et supprimer les invalides.

Convertit: https://upload.wikimedia.org/wikipedia/commons/thumb/3/3d/ASIMO_4.28.11.jpg/800px-ASIMO_4.28.11.jpg
En: https://upload.wikimedia.org/wikipedia/commons/3/3d/ASIMO_4.28.11.jpg
"""

import re
import requests
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def find_image_urls_in_markdown(content: str) -> list:
    """Trouve toutes les URLs d'images dans un contenu markdown."""
    pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
    matches = []
    for match in re.finditer(pattern, content):
        alt_text = match.group(1)
        url = match.group(2).strip()
        matches.append((match, url, alt_text))
    return matches


def convert_thumb_to_direct(url: str) -> str:
    """Convertit une URL thumb Wikimedia Commons en URL directe.
    
    Args:
        url: URL au format thumb
        
    Returns:
        URL au format direct, ou URL originale si la conversion n'est pas possible
    """
    # Pattern pour extraire le chemin depuis une URL thumb
    # Exemple: /thumb/3/3d/ASIMO_4.28.11.jpg/800px-ASIMO_4.28.11.jpg
    # -> chemin = 3/3d/ASIMO_4.28.11.jpg
    thumb_pattern = r'/thumb/(.+?)/(\d+px-.+)$'
    match = re.search(thumb_pattern, url)
    
    if match:
        path = match.group(1)
        # Construire l'URL directe
        if 'upload.wikimedia.org/wikipedia/commons' in url:
            base_url = 'https://upload.wikimedia.org/wikipedia/commons/'
        elif 'upload.wikimedia.org/wikipedia/en' in url:
            base_url = 'https://upload.wikimedia.org/wikipedia/en/'
        else:
            # Autre domaine Wikimedia, extraire le domaine
            domain_match = re.search(r'(https://upload\.wikimedia\.org/wikipedia/[^/]+)', url)
            if domain_match:
                base_url = domain_match.group(1) + '/'
            else:
                return url
        
        direct_url = base_url + path
        return direct_url
    
    # Si ce n'est pas une URL thumb, retourner l'URL originale
    return url


def is_valid_image_url(url: str, timeout: int = 3) -> bool:
    """Vérifie si une URL d'image est accessible."""
    try:
        response = requests.head(url, timeout=timeout, allow_redirects=True)
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '')
            return 'image' in content_type.lower()
        return False
    except Exception as e:
        logger.debug(f"Erreur pour {url}: {e}")
        return False


def fix_markdown_file(file_path: Path, dry_run: bool = False) -> tuple[int, int]:
    """Convertit les URLs thumb en URLs directes et supprime les images invalides.
    
    Args:
        file_path: Chemin vers le fichier markdown
        dry_run: Si True, ne modifie pas le fichier
        
    Returns:
        Tuple (nombre d'URLs converties, nombre d'images supprimées)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        logger.error(f"Erreur lors de la lecture de {file_path}: {e}")
        return 0, 0
    
    original_content = content
    converted_count = 0
    removed_count = 0
    image_matches = find_image_urls_in_markdown(content)
    
    # Traiter chaque image de la fin vers le début pour préserver les positions
    for match, url, alt_text in reversed(image_matches):
        url = url.strip()
        needs_removal = False
        
        # Vérifier si c'est une URL thumb Wikimedia Commons
        if '/thumb/' in url and 'upload.wikimedia.org' in url:
            # Convertir en URL directe
            direct_url = convert_thumb_to_direct(url)
            
            if direct_url != url:
                # Vérifier que l'URL directe est valide
                if is_valid_image_url(direct_url):
                    if not dry_run:
                        # Remplacer l'URL dans le contenu
                        new_image = f"![{alt_text}]({direct_url})"
                        content = content[:match.start()] + new_image + content[match.end():]
                    converted_count += 1
                    logger.info(f"✅ Conversion: {url[:60]}... -> {direct_url[:60]}...")
                else:
                    logger.warning(f"❌ URL directe invalide: {direct_url[:60]}...")
                    needs_removal = True
            else:
                # URL thumb mais conversion échouée, vérifier l'URL originale
                if not is_valid_image_url(url):
                    logger.warning(f"❌ URL thumb invalide: {url[:60]}...")
                    needs_removal = True
        else:
            # URL non-thumb, vérifier si elle est valide
            if 'upload.wikimedia.org' in url and not is_valid_image_url(url):
                logger.warning(f"❌ URL invalide: {url[:60]}...")
                needs_removal = True
        
        # Supprimer l'image si nécessaire
        if needs_removal:
            if not dry_run:
                # Supprimer l'image et la ligne vide avant si elle existe
                start = match.start()
                end = match.end()
                
                # Supprimer la ligne vide avant
                if start > 0 and content[start-1] == '\n':
                    line_start = content.rfind('\n', 0, start-1) + 1
                    if line_start < start and content[line_start:start-1].strip() == '':
                        start = line_start
                
                # Supprimer la ligne vide après
                if end < len(content) and content[end] == '\n':
                    next_newline = content.find('\n', end + 1)
                    if next_newline > end and content[end+1:next_newline].strip() == '':
                        end = next_newline + 1
                
                content = content[:start] + content[end:]
            removed_count += 1
    
    # Écrire le fichier modifié seulement s'il y a eu des changements
    if content != original_content and not dry_run:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"✅ {file_path.name}: {converted_count} convertie(s), {removed_count} supprimée(s)")
        except Exception as e:
            logger.error(f"Erreur lors de l'écriture de {file_path}: {e}")
            return 0, 0
    elif (converted_count > 0 or removed_count > 0) and dry_run:
        logger.info(f"🔍 {file_path.name}: {converted_count} serait convertie(s), {removed_count} serait supprimée(s)")
    
    return converted_count, removed_count


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
        
        markdown_dir = run_dir / "markdown"
        if not markdown_dir.exists():
            continue
        
        # Parcourir tous les fichiers markdown
        for md_file in sorted(markdown_dir.glob("*.md")):
            converted, removed = fix_markdown_file(md_file, dry_run=dry_run)
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

