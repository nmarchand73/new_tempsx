"""Exporteur pour les épisodes NEW TEMPS X."""

import json
import logging
import os
from pathlib import Path

from .models import Act, Episode, TwilightZoneStory

logger = logging.getLogger(__name__)


class EpisodeExporter:
    """Exporte un épisode en JSON et Markdown."""

    def __init__(self, output_dir: Path | None = None, run_name: str | None = None):
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

    def _episode_dict(self, episode: Episode) -> dict:
        """Représentation JSON de l'épisode (complet ou partiel), lue par l'UI et par --resume."""
        data = {
            "episode_title": episode.episode_title,
            "scenario_input": episode.scenario_input,
            "narrative_arc": episode.narrative_arc,
            "run_name": self.run_name,
            "themes": episode.themes,
            "cost_usd": episode.cost_usd,
            "acts": {
                act_key: {
                    "title": act.title,
                    "content": act.content,
                    "narrator": act.narrator,
                    "image_prompts": act.image_prompts,
                    "references": [ref.model_dump() for ref in act.references],
                }
                for act_key, act in episode.acts.items()
            },
        }
        if episode.twilight_zone_story:
            story = episode.twilight_zone_story
            data["twilight_zone_story"] = {
                "title": story.title,
                "story": story.story,
                "theme": story.theme,
                "image_prompts": story.image_prompts,
            }
        return data

    def export_json(self, episode: Episode, filename: str = "episode.json"):
        """Exporte l'épisode en JSON (écriture atomique : l'UI qui relit en continu ne voit jamais un fichier tronqué)."""
        output_path = self.output_dir / filename
        tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(self._episode_dict(episode), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp_path, output_path)
        logger.debug(f"JSON exporté: {output_path}")

    def export_partial_json(self, episode: Episode, filename: str = "episode.json"):
        """Exporte un JSON partiel (export progressif) - identique à export_json."""
        self.export_json(episode, filename)

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

    def export_act_markdown(self, act_key: str, act: Act, act_filename: str):
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

    def export_twilight_zone_story(self, story: TwilightZoneStory):
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
