"""Exporteur pour les épisodes NEW TEMPS X."""

import json
import logging
from pathlib import Path
from typing import Optional

from .models import Episode

logger = logging.getLogger(__name__)


class EpisodeExporter:
    """Exporte un épisode en JSON et Markdown."""
    
    def __init__(self, output_dir: Optional[Path] = None, run_name: Optional[str] = None):
        """Initialise l'exporteur.
        
        Args:
            output_dir: Répertoire de sortie. Si None, utilise ./output
            run_name: Nom du run (pour organisation par run)
        """
        if output_dir is None:
            output_dir = Path("output")
        self.output_dir = Path(output_dir)
        self.run_name = run_name
        self.markdown_dir = self.output_dir / "markdown"
        self.audio_dir = self.output_dir / "audio"
        
        # Créer les répertoires si nécessaire
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.markdown_dir.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)
    
    def export_all(self, episode: Episode):
        """Exporte l'épisode en JSON et Markdown.
        
        Args:
            episode: L'épisode à exporter
        """
        self.export_json(episode)
        self.export_markdown(episode)
    
    def export_json(self, episode: Episode, filename: str = "episode.json"):
        """Exporte l'épisode en JSON.
        
        Args:
            episode: L'épisode à exporter
            filename: Nom du fichier JSON
        """
        output_path = self.output_dir / filename
        logger.debug(f"Export JSON vers: {output_path}")
        
        # Convertir en dict pour l'export JSON
        episode_dict = {
            "episode_title": episode.episode_title,
            "scenario_input": episode.scenario_input,
            "narrative_arc": episode.narrative_arc,
            "run_name": self.run_name,  # Ajouter le nom du run
            "acts": {
                act_key: {
                    "title": act.title,
                    "content": act.content,
                    "narrator": getattr(act, "narrator", "narrator_1"),
                    "image_prompts": getattr(act, "image_prompts", []),
                    "references": [
                        {
                            "title": ref.title,
                            "url": ref.url,
                            "description": ref.description
                        }
                        for ref in getattr(act, "references", [])
                    ]
                }
                for act_key, act in episode.acts.items()
            }
            }
        
        # Ajouter l'histoire Twilight Zone si disponible
        if episode.twilight_zone_story:
            episode_dict["twilight_zone_story"] = {
                "title": episode.twilight_zone_story.title,
                "story": episode.twilight_zone_story.story,
                "theme": episode.twilight_zone_story.theme,
                "image_prompts": getattr(episode.twilight_zone_story, "image_prompts", [])
            }
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(episode_dict, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ Épisode exporté en JSON: {output_path}")
    
    def export_partial_json(self, episode: Episode, filename: str = "episode.json"):
        """Exporte un JSON partiel (pour export progressif).
        
        Permet d'exporter l'épisode même si tous les actes ne sont pas encore générés.
        
        Args:
            episode: L'épisode (peut être partiel)
            filename: Nom du fichier JSON
        """
        output_path = self.output_dir / filename
        logger.debug(f"Export JSON partiel vers: {output_path}")
        
        # Convertir en dict pour l'export JSON (seulement les actes disponibles)
        episode_dict = {
            "episode_title": episode.episode_title,
            "scenario_input": episode.scenario_input,
            "narrative_arc": episode.narrative_arc,
            "run_name": self.run_name,
            "acts": {}
        }
        
        # Ajouter seulement les actes disponibles
        for act_key, act in episode.acts.items():
            episode_dict["acts"][act_key] = {
                "title": act.title,
                "content": act.content,
                "narrator": getattr(act, "narrator", "narrator_1"),
                "image_prompts": getattr(act, "image_prompts", []),
                "references": [
                    {
                        "title": ref.title,
                        "url": ref.url,
                        "description": ref.description
                    }
                    for ref in getattr(act, "references", [])
                ]
            }
        
        # Ajouter l'histoire Twilight Zone si disponible
        if episode.twilight_zone_story:
            episode_dict["twilight_zone_story"] = {
                "title": episode.twilight_zone_story.title,
                "story": episode.twilight_zone_story.story,
                "theme": episode.twilight_zone_story.theme,
                "image_prompts": getattr(episode.twilight_zone_story, "image_prompts", [])
            }
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(episode_dict, f, ensure_ascii=False, indent=2)
        
        logger.debug(f"✅ JSON partiel exporté: {output_path}")
    
    def export_markdown(self, episode: Episode):
        """Exporte chaque acte en fichier Markdown séparé.
        
        Args:
            episode: L'épisode à exporter
        """
        act_names = {
            "acte_1": "01_le_signal",
            "acte_2": "02_le_decryptage",
            "acte_3": "03_la_tension",
            "acte_4": "04_la_fiction",
            "acte_5": "05_le_dialogue",
            "acte_6": "06_la_memoire",
            "acte_7": "07_la_transmission",
        }
        
        logger.debug(f"Export Markdown vers: {self.markdown_dir}")
        
        for act_key, act in episode.acts.items():
            self.export_act_markdown(act_key, act, act_names.get(act_key, act_key))
        
        logger.info(f"✅ Tous les actes exportés dans: {self.markdown_dir}")
    
    def export_act_markdown(self, act_key: str, act: "Act", act_filename: str):
        """Exporte un acte individuel en Markdown (pour export progressif).
        
        Args:
            act_key: Clé de l'acte (ex: "acte_1")
            act: L'acte à exporter
            act_filename: Nom de fichier pour l'acte (ex: "01_le_signal")
        """
        filename = f"{act_filename}.md"
        output_path = self.markdown_dir / filename
        
        # Créer le contenu Markdown avec références
        references_section = ""
        if hasattr(act, "references") and act.references:
            references_section = "\n\n## Références\n\n"
            for ref in act.references:
                if ref.description:
                    references_section += f"- [{ref.title}]({ref.url}) - {ref.description}\n"
                else:
                    references_section += f"- [{ref.title}]({ref.url})\n"
        
        markdown_content = f"""# {act.title}

{act.content}{references_section}
"""
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        
        logger.info(f"✅ Acte exporté: {output_path}")
    
    def export_twilight_zone_story(self, story: "TwilightZoneStory"):
        """Exporte l'histoire Twilight Zone en Markdown.
        
        Args:
            story: L'histoire Twilight Zone à exporter
        """
        filename = "twilight_zone_story.md"
        output_path = self.markdown_dir / filename
        
        markdown_content = f"""# {story.title}

*Thème: {story.theme}*

---

{story.story}
"""
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        
        logger.info(f"✅ Histoire Twilight Zone exportée: {output_path}")

