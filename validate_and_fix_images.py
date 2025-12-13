"""Script pour valider et corriger les URLs d'images dans les fichiers markdown.

Ce script vérifie chaque URL d'image et supprime celles qui ne sont pas accessibles.
"""

import re
import requests
from pathlib import Path
import logging
from urllib.parse import urlparse

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


def is_valid_image_url(url: str, timeout: int = 3) -> bool:
    """Vérifie si une URL d'image est accessible."""
    try:
        # Utiliser HEAD pour être plus rapide
        response = requests.head(url, timeout=timeout, allow_redirects=True)
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '')
            return 'image' in content_type.lower()
        return False
    except requests.exceptions.Timeout:
        logger.debug(f"Timeout pour {url}")
        return False
    except Exception as e:
        logger.debug(f"Erreur pour {url}: {e}")
        return False


def fix_markdown_file(file_path: Path, dry_run: bool = False) -> int:
    """Corrige les URLs d'images dans un fichier markdown.
    
    Args:
        file_path: Chemin vers le fichier markdown
        dry_run: Si True, ne modifie pas le fichier, affiche seulement ce qui serait fait
        
    Returns:
        Nombre d'images supprimées
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        logger.error(f"Erreur lors de la lecture de {file_path}: {e}")
        return 0
    
    original_content = content
    removed_count = 0
    image_matches = find_image_urls_in_markdown(content)
    
    # Traiter chaque image de la fin vers le début pour préserver les positions
    for match, url, alt_text in reversed(image_matches):
        # Vérifier si l'URL est valide
        if not is_valid_image_url(url):
            logger.warning(f"Image invalide dans {file_path.name}: {alt_text[:50]}... ({url[:60]}...)")
            
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
            else:
                removed_count += 1
        else:
            logger.debug(f"Image valide: {url[:60]}...")
    
    # Écrire le fichier modifié seulement s'il y a eu des changements
    if content != original_content and not dry_run:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"✅ {file_path.name}: {removed_count} image(s) supprimée(s)")
        except Exception as e:
            logger.error(f"Erreur lors de l'écriture de {file_path}: {e}")
            return 0
    elif removed_count > 0 and dry_run:
        logger.info(f"🔍 {file_path.name}: {removed_count} image(s) seraient supprimée(s)")
    
    return removed_count


def main():
    """Fonction principale."""
    import sys
    
    dry_run = '--dry-run' in sys.argv or '-n' in sys.argv
    
    output_dir = Path("output")
    if not output_dir.exists():
        logger.error(f"Le répertoire {output_dir} n'existe pas")
        return
    
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
            removed = fix_markdown_file(md_file, dry_run=dry_run)
            total_removed += removed
            if removed > 0:
                files_processed += 1
    
    logger.info(f"\n{'[DRY RUN] ' if dry_run else ''}✅ Correction terminée:")
    logger.info(f"   - Fichiers modifiés: {files_processed}")
    logger.info(f"   - Images invalides supprimées: {total_removed}")


if __name__ == "__main__":
    main()

