"""Générateur d'images pour les épisodes NEW TEMPS X.

Utilise l'API OpenAI DALL-E pour générer des images à partir des prompts.
"""

import asyncio
import base64
import hashlib
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import httpx

from .http_utils import request_with_retry
from .models import Act, Episode, TwilightZoneStory

if TYPE_CHECKING:
    from .exporters import EpisodeExporter

logger = logging.getLogger(__name__)

ACT_FILE_NAMES = {
    f"acte_{n}": name
    for n, name in enumerate(
        [
            "01_le_signal",
            "02_le_decryptage",
            "03_la_tension",
            "04_la_fiction",
            "05_le_dialogue",
            "06_la_memoire",
            "07_la_transmission",
        ],
        start=1,
    )
}


class ImageGenerator:
    """Génère des images à partir de prompts DALL-E."""

    def __init__(self, output_dir: Path | None = None, max_concurrent: int = 3, model: str | None = None):
        """Initialise le générateur d'images.

        Args:
            output_dir: Répertoire de sortie pour les images
        """
        if output_dir is None:
            output_dir = Path("output") / "images"
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.model = model or os.getenv("OPENAI_IMAGE_MODEL", "dall-e-3")
        self._semaphore = asyncio.Semaphore(max(1, max_concurrent))

        # Clé API OpenAI
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            logger.warning("⚠️  OPENAI_API_KEY non trouvée. La génération d'images ne fonctionnera pas.")

    async def generate_image_from_prompt(
        self,
        prompt: str,
        output_path: Path | None = None,
        size: str | None = None,
        model: str | None = None,
    ) -> Path | None:
        """Génère une image via l'API OpenAI Images.

        Args:
            prompt: Description de l'image
            output_path: Chemin de sortie (auto si absent)
            size: Taille (défaut 1024x1024, valide pour tous les modèles)
            model: Modèle (défaut: OPENAI_IMAGE_MODEL ou "dall-e-3"; "gpt-image-1" est supporté)

        Returns:
            Chemin de l'image, ou None en cas d'erreur (après retries sur 429/5xx).
        """
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY non configurée")
        model = model or self.model

        if output_path is None:
            prompt_hash = hashlib.md5(prompt.encode("utf-8"), usedforsecurity=False).hexdigest()[:8]
            output_path = self.output_dir / f"image_{prompt_hash}.png"
        if output_path.exists():
            logger.debug("✅ Image en cache: %s", output_path.name)
            return output_path

        data = {"model": model, "prompt": prompt, "size": size or "1024x1024", "n": 1}
        if model == "dall-e-3":
            data["quality"] = "standard"
        elif model.startswith("gpt-image"):
            data["quality"] = "medium"  # low | medium | high (renvoie toujours du base64)
        headers = {"Authorization": f"Bearer {self.openai_api_key}"}

        try:
            logger.info("🎨 Génération d'image: %s...", prompt[:60])
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await request_with_retry(
                    client, "POST", "https://api.openai.com/v1/images/generations", json=data, headers=headers
                )
                item = response.json()["data"][0]
                if item.get("b64_json"):
                    content = base64.b64decode(item["b64_json"])
                else:
                    content = (await request_with_retry(client, "GET", item["url"])).content
            output_path.write_bytes(content)
            logger.info("✅ Image générée: %s", output_path.name)
            return output_path
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300]
            try:
                detail = exc.response.json().get("error", {}).get("message", detail)
            except ValueError:
                pass
            logger.error("❌ Image: HTTP %s: %s", exc.response.status_code, detail)
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            logger.error("❌ Image: %s: %s", type(exc).__name__, exc)
        return None

    def _image_path(self, prefix: str, episode_title: str, index: int, prompt: str) -> Path:
        safe_title = (
            "".join(c for c in episode_title if c.isalnum() or c in (" ", "-", "_")).strip()[:30].replace(" ", "_")
        )
        prompt_hash = hashlib.md5(prompt.encode("utf-8"), usedforsecurity=False).hexdigest()[:6]
        return self.output_dir / f"{prefix}_{safe_title}_{index}_{prompt_hash}.png"

    async def _generate_many(self, prefix: str, episode_title: str, prompts: list[str]) -> list[Path | None]:
        """Génère les images d'une liste de prompts en parallèle (borné), dans l'ordre des prompts."""

        async def one(i: int, prompt: str) -> Path | None:
            async with self._semaphore:
                return await self.generate_image_from_prompt(
                    prompt, self._image_path(prefix, episode_title, i + 1, prompt)
                )

        return list(await asyncio.gather(*(one(i, p) for i, p in enumerate(prompts))))

    async def generate_act_images(self, act: Act, act_key: str, episode_title: str) -> list[Path]:
        """Génère les images d'un acte à partir de ses prompts."""
        prompts = getattr(act, "image_prompts", [])
        results = await self._generate_many(act_key, episode_title, prompts) if prompts else []
        return [p for p in results if p]

    async def generate_twilight_zone_images(self, twilight_story: TwilightZoneStory, episode_title: str) -> list[Path]:
        """Génère les images d'une histoire Twilight Zone."""
        prompts = getattr(twilight_story, "image_prompts", [])
        results = await self._generate_many("twilight_zone", episode_title, prompts) if prompts else []
        return [p for p in results if p]

    async def generate_episode_images(
        self,
        episode: Episode,
        exporter: Optional["EpisodeExporter"] = None,
    ) -> dict[str, list[Path]]:
        """Génère les images de tout l'épisode (actes + Twilight Zone) en parallèle.

        Les générations sont concurrentes (bornées par `max_concurrent`), mais l'intégration
        dans le texte se fait dans l'ordre des prompts pour chaque cible, et les exports
        (markdown + JSON lus par l'UI) sont sérialisés.
        """
        if not self.openai_api_key:
            logger.warning("⚠️  OPENAI_API_KEY non configurée, génération d'images ignorée")
            return {}

        logger.info("🎨 Génération des images pour l'épisode: %s", episode.episode_title)
        export_lock = asyncio.Lock()
        all_images: dict[str, list[Path]] = {}

        async def process(key: str, prefix: str, prompts: list[str], integrate, export) -> None:
            if not prompts:
                return
            paths = await self._generate_many(prefix, episode.episode_title, prompts)
            generated = []
            async with export_lock:
                for i, (prompt, path) in enumerate(zip(prompts, paths), start=1):
                    if not path:
                        continue
                    generated.append(path)
                    integrate(path, i, len(prompts), prompt)
                if generated and exporter:
                    export()
                    exporter.export_json(episode)
            if generated:
                all_images[key] = generated
            logger.info("✅ %d/%d image(s) pour %s", len(generated), len(prompts), key)

        tasks = []
        for act_key, act in episode.acts.items():
            tasks.append(
                process(
                    act_key,
                    act_key,
                    getattr(act, "image_prompts", []),
                    lambda path, i, n, prompt, act=act, act_key=act_key: self._integrate_single_image_into_act(
                        act, path, act_key, i, total_images=n, prompt=prompt
                    ),
                    lambda act=act, act_key=act_key: exporter.export_act_markdown(
                        act_key, act, ACT_FILE_NAMES.get(act_key, act_key)
                    ),
                )
            )
        story = episode.twilight_zone_story
        if story:
            tasks.append(
                process(
                    "twilight_zone",
                    "twilight_zone",
                    getattr(story, "image_prompts", []),
                    lambda path, i, n, prompt: self._integrate_single_image_into_twilight_story(
                        story, path, i, total_images=n, prompt=prompt
                    ),
                    lambda: exporter.export_twilight_zone_story(story),
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, BaseException):
                logger.error("❌ Génération d'images: %s", res)

        total = sum(len(v) for v in all_images.values())
        logger.info("✅ %d image(s) générée(s) au total", total)
        return {k: all_images[k] for k in sorted(all_images)}

    def _find_best_image_position(self, content: str, image_index: int, total_images: int, prompt: str) -> int:
        """Trouve la meilleure position pour insérer une image dans le contenu.

        Args:
            content: Le contenu de l'acte
            image_index: Index de l'image (1, 2, 3, etc.)
            total_images: Nombre total d'images pour cet acte
            prompt: Le prompt de l'image (pour contexte)

        Returns:
            Index du paragraphe où insérer l'image (-1 pour la fin)
        """
        # Diviser le contenu en paragraphes
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]

        if not paragraphs:
            return -1

        # Si une seule image, la placer après le premier tiers du contenu
        if total_images == 1:
            return min(len(paragraphs) // 3, len(paragraphs) - 1)

        # Distribuer les images de manière équilibrée
        # Diviser le contenu en sections égales
        section_size = len(paragraphs) / (total_images + 1)

        # Positionner chaque image dans sa section
        position = int(section_size * image_index)

        # S'assurer que l'image n'est pas au tout début ou à la toute fin
        position = max(1, min(position, len(paragraphs) - 2))

        return position

    def _integrate_single_image_into_act(
        self, act: "Act", image_path: Path, act_key: str, image_index: int, total_images: int = 1, prompt: str = ""
    ):
        """Intègre une seule image dans le contenu markdown de l'acte de manière harmonieuse.

        Place l'image à un emplacement contextuel approprié dans le contenu plutôt qu'à la fin.
        Utilise des chemins compatibles avec le serveur web (/api/images/) et les fichiers markdown (../images/).

        Args:
            act: L'acte à modifier
            image_path: Chemin de l'image générée
            act_key: Clé de l'acte (ex: "acte_1")
            image_index: Index de l'image (1, 2, 3, etc.)
            total_images: Nombre total d'images pour cet acte
            prompt: Le prompt de l'image (pour contexte)
        """
        # Chemin relatif pour les fichiers markdown
        relative_path = f"../images/{image_path.name}"
        # Créer un texte alternatif basé sur le titre de l'acte et l'index
        alt_text = f"{act.title} - Image {image_index}"
        image_markdown = f"\n\n![{alt_text}]({relative_path})\n\n"

        # Trouver la meilleure position pour l'image
        position = self._find_best_image_position(act.content, image_index, total_images, prompt)

        if position >= 0:
            # Diviser le contenu en paragraphes
            paragraphs = [p.strip() for p in act.content.split("\n\n") if p.strip()]

            if position < len(paragraphs):
                # Insérer l'image après le paragraphe à la position trouvée
                paragraphs.insert(position + 1, image_markdown.strip())
                act.content = "\n\n".join(paragraphs)
                logger.debug(
                    f"📸 Image {image_index} intégrée harmonieusement à la position {position + 1}/{len(paragraphs)} dans {act_key}"
                )
            else:
                # Fallback : ajouter à la fin si la position est invalide
                act.content = act.content.rstrip() + image_markdown
                logger.debug(f"📸 Image {image_index} intégrée à la fin (fallback) dans {act_key}")
        else:
            # Ajouter à la fin si aucune position valide n'est trouvée
            act.content = act.content.rstrip() + image_markdown
            logger.debug(f"📸 Image {image_index} intégrée à la fin dans {act_key}")

    def _integrate_images_into_act(self, act: "Act", image_paths: list[Path], act_key: str):
        """Intègre plusieurs images générées dans le contenu markdown de l'acte.

        Méthode de compatibilité pour l'intégration en lot.

        Args:
            act: L'acte à modifier
            image_paths: Liste des chemins des images générées
            act_key: Clé de l'acte (ex: "acte_1")
        """
        if not image_paths:
            return

        # Pour le markdown : chemin relatif depuis markdown/ vers images/
        # Pour le web : chemin API /api/images/filename.png?run=run_name
        # On utilise le chemin relatif pour le markdown, le serveur web gérera l'API
        image_markdown = "\n\n"
        for i, image_path in enumerate(image_paths):
            # Chemin relatif pour les fichiers markdown
            relative_path = f"../images/{image_path.name}"
            # Créer un texte alternatif basé sur le titre de l'acte et l'index
            alt_text = f"{act.title} - Image {i + 1}"
            image_markdown += f"![{alt_text}]({relative_path})\n\n"

        # Ajouter les images à la fin du contenu
        act.content = act.content.rstrip() + image_markdown
        logger.debug(f"📸 {len(image_paths)} image(s) intégrée(s) dans le contenu de {act_key}")

    def _integrate_single_image_into_twilight_story(
        self, story: "TwilightZoneStory", image_path: Path, image_index: int, total_images: int = 1, prompt: str = ""
    ):
        """Intègre une seule image dans l'histoire Twilight Zone de manière harmonieuse.

        Place l'image à un emplacement contextuel approprié dans l'histoire.

        Args:
            story: L'histoire Twilight Zone à modifier
            image_path: Chemin de l'image générée
            image_index: Index de l'image (1, 2, 3, etc.)
            total_images: Nombre total d'images pour cette histoire
            prompt: Le prompt de l'image (pour contexte)
        """
        relative_path = f"../images/{image_path.name}"
        alt_text = f"{story.title} - Image {image_index}"
        image_markdown = f"\n\n![{alt_text}]({relative_path})\n\n"

        # Trouver la meilleure position pour l'image
        position = self._find_best_image_position(story.story, image_index, total_images, prompt)

        if position >= 0:
            # Diviser l'histoire en paragraphes
            paragraphs = [p.strip() for p in story.story.split("\n\n") if p.strip()]

            if position < len(paragraphs):
                # Insérer l'image après le paragraphe à la position trouvée
                paragraphs.insert(position + 1, image_markdown.strip())
                story.story = "\n\n".join(paragraphs)
                logger.debug(
                    f"📸 Image {image_index} intégrée harmonieusement à la position {position + 1}/{len(paragraphs)} dans l'histoire Twilight Zone"
                )
            else:
                # Fallback : ajouter à la fin si la position est invalide
                story.story = story.story.rstrip() + image_markdown
                logger.debug(f"📸 Image {image_index} intégrée à la fin (fallback) dans l'histoire Twilight Zone")
        else:
            # Ajouter à la fin si aucune position valide n'est trouvée
            story.story = story.story.rstrip() + image_markdown
            logger.debug(f"📸 Image {image_index} intégrée à la fin dans l'histoire Twilight Zone")

    def _integrate_images_into_twilight_story(self, story: "TwilightZoneStory", image_paths: list[Path]):
        """Intègre plusieurs images générées dans l'histoire Twilight Zone.

        Méthode de compatibilité pour l'intégration en lot.

        Args:
            story: L'histoire Twilight Zone à modifier
            image_paths: Liste des chemins des images générées
        """
        if not image_paths:
            return

        # Calculer le chemin relatif depuis le répertoire markdown vers le répertoire images
        image_markdown = "\n\n"
        for i, image_path in enumerate(image_paths):
            relative_path = f"../images/{image_path.name}"
            alt_text = f"{story.title} - Image {i + 1}"
            image_markdown += f"![{alt_text}]({relative_path})\n\n"

        # Ajouter les images à la fin de l'histoire
        story.story = story.story.rstrip() + image_markdown
        logger.debug(f"📸 {len(image_paths)} image(s) intégrée(s) dans l'histoire Twilight Zone")
