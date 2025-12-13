"""Générateur d'images pour les épisodes NEW TEMPS X.

Utilise l'API OpenAI DALL-E pour générer des images à partir des prompts.
"""

import asyncio
import hashlib
import logging
import os
from pathlib import Path
from typing import Optional

import httpx

from .models import Episode, Act, TwilightZoneStory

logger = logging.getLogger(__name__)


class ImageGenerator:
    """Génère des images à partir de prompts DALL-E."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        """Initialise le générateur d'images.
        
        Args:
            output_dir: Répertoire de sortie pour les images
        """
        if output_dir is None:
            output_dir = Path("output") / "images"
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Clé API OpenAI
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            logger.warning("⚠️  OPENAI_API_KEY non trouvée. La génération d'images ne fonctionnera pas.")
    
    async def generate_image_from_prompt(
        self,
        prompt: str,
        output_path: Optional[Path] = None,
        size: str = "1024x1024",
        model: str = "dall-e-3"
    ) -> Optional[Path]:
        """Génère une image à partir d'un prompt DALL-E.
        
        Args:
            prompt: Prompt de description de l'image
            output_path: Chemin de sortie (optionnel, généré automatiquement si non fourni)
            size: Taille de l'image ("1024x1024", "1792x1024", "1024x1792")
            model: Modèle DALL-E à utiliser ("dall-e-3" ou "dall-e-2")
            
        Returns:
            Chemin du fichier image généré, ou None en cas d'erreur
        """
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY non configurée")
        
        # Générer un nom de fichier si non fourni
        if output_path is None:
            prompt_hash = hashlib.md5(prompt.encode('utf-8')).hexdigest()[:8]
            output_path = self.output_dir / f"image_{prompt_hash}.png"
        
        # Vérifier le cache
        if output_path.exists():
            logger.debug(f"✅ Image en cache: {output_path.name}")
            return output_path
        
        url = "https://api.openai.com/v1/images/generations"
        
        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "quality": "standard",
            "n": 1
        }
        
        try:
            logger.info(f"🎨 Génération d'image: {prompt[:60]}...")
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=data, headers=headers)
                response.raise_for_status()
                
                result = response.json()
                image_url = result["data"][0]["url"]
                
                # Télécharger l'image
                async with httpx.AsyncClient(timeout=30.0) as download_client:
                    image_response = await download_client.get(image_url)
                    image_response.raise_for_status()
                    
                    # Sauvegarder l'image
                    with open(output_path, "wb") as f:
                        f.write(image_response.content)
            
            logger.info(f"✅ Image générée: {output_path.name}")
            return output_path
            
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Erreur HTTP {e.response.status_code} lors de la génération d'image: {e}")
            if e.response.status_code == 400:
                try:
                    error_json = e.response.json()
                    error_detail = error_json.get("error", {}).get("message", "Erreur inconnue")
                    logger.error(f"   Message d'erreur: {error_detail}")
                except:
                    logger.error(f"   Réponse brute: {e.response.text[:500]}")
            return None
        except Exception as e:
            logger.error(f"❌ Erreur lors de la génération d'image: {e}")
            return None
    
    async def generate_act_images(self, act: Act, act_key: str, episode_title: str) -> list[Path]:
        """Génère les images pour un acte à partir de ses prompts.
        
        Args:
            act: L'acte contenant les image_prompts
            act_key: Clé de l'acte (ex: "acte_1")
            episode_title: Titre de l'épisode (pour le nom de fichier)
            
        Returns:
            Liste des chemins des images générées
        """
        image_prompts = getattr(act, "image_prompts", [])
        if not image_prompts:
            logger.debug(f"📝 Aucun prompt d'image pour {act_key}")
            return []
        
        logger.info(f"🎨 Génération de {len(image_prompts)} image(s) pour {act_key}...")
        generated_images = []
        
        for i, prompt in enumerate(image_prompts):
            # Créer un nom de fichier basé sur l'acte et l'index
            safe_title = "".join(c for c in episode_title if c.isalnum() or c in (' ', '-', '_')).strip()[:30]
            safe_title = safe_title.replace(' ', '_')
            prompt_hash = hashlib.md5(prompt.encode('utf-8')).hexdigest()[:6]
            filename = f"{act_key}_{safe_title}_{i+1}_{prompt_hash}.png"
            output_path = self.output_dir / filename
            
            image_path = await self.generate_image_from_prompt(prompt, output_path)
            if image_path:
                generated_images.append(image_path)
        
        logger.info(f"✅ {len(generated_images)}/{len(image_prompts)} image(s) générée(s) pour {act_key}")
        return generated_images
    
    async def generate_twilight_zone_images(
        self,
        twilight_story: TwilightZoneStory,
        episode_title: str
    ) -> list[Path]:
        """Génère les images pour une histoire Twilight Zone.
        
        Args:
            twilight_story: L'histoire Twilight Zone contenant les image_prompts
            episode_title: Titre de l'épisode (pour le nom de fichier)
            
        Returns:
            Liste des chemins des images générées
        """
        image_prompts = getattr(twilight_story, "image_prompts", [])
        if not image_prompts:
            logger.debug("📝 Aucun prompt d'image pour l'histoire Twilight Zone")
            return []
        
        logger.info(f"🎬 Génération de {len(image_prompts)} image(s) pour l'histoire Twilight Zone...")
        generated_images = []
        
        for i, prompt in enumerate(image_prompts):
            # Créer un nom de fichier basé sur l'histoire
            safe_title = "".join(c for c in episode_title if c.isalnum() or c in (' ', '-', '_')).strip()[:30]
            safe_title = safe_title.replace(' ', '_')
            prompt_hash = hashlib.md5(prompt.encode('utf-8')).hexdigest()[:6]
            filename = f"twilight_zone_{safe_title}_{i+1}_{prompt_hash}.png"
            output_path = self.output_dir / filename
            
            image_path = await self.generate_image_from_prompt(prompt, output_path)
            if image_path:
                generated_images.append(image_path)
        
        logger.info(f"✅ {len(generated_images)}/{len(image_prompts)} image(s) générée(s) pour l'histoire Twilight Zone")
        return generated_images
    
    async def generate_episode_images(self, episode: Episode) -> dict[str, list[Path]]:
        """Génère toutes les images pour un épisode complet.
        
        Args:
            episode: L'épisode complet
            
        Returns:
            Dictionnaire {act_key: [image_paths]} pour chaque acte
        """
        if not self.openai_api_key:
            logger.warning("⚠️  OPENAI_API_KEY non configurée, génération d'images ignorée")
            return {}
        
        logger.info(f"🎨 Génération des images pour l'épisode: {episode.episode_title}")
        all_images = {}
        
        # Générer les images pour chaque acte
        for act_key, act in episode.acts.items():
            images = await self.generate_act_images(act, act_key, episode.episode_title)
            if images:
                all_images[act_key] = images
                # Intégrer les images dans le contenu markdown de l'acte
                self._integrate_images_into_act(act, images, act_key)
        
        # Générer les images pour l'histoire Twilight Zone si disponible
        if episode.twilight_zone_story:
            twilight_images = await self.generate_twilight_zone_images(
                episode.twilight_zone_story,
                episode.episode_title
            )
            if twilight_images:
                all_images["twilight_zone"] = twilight_images
                # Intégrer les images dans l'histoire Twilight Zone
                self._integrate_images_into_twilight_story(episode.twilight_zone_story, twilight_images)
        
        total_generated = sum(len(images) for images in all_images.values())
        logger.info(f"✅ {total_generated} image(s) générée(s) au total pour l'épisode")
        
        return all_images
    
    def _integrate_images_into_act(self, act: "Act", image_paths: list[Path], act_key: str):
        """Intègre les images générées dans le contenu markdown de l'acte.
        
        Ajoute les balises markdown ![alt](path) à la fin du contenu de l'acte.
        Utilise des chemins compatibles avec le serveur web (/api/images/) et les fichiers markdown (../images/).
        
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
            alt_text = f"{act.title} - Image {i+1}"
            image_markdown += f"![{alt_text}]({relative_path})\n\n"
        
        # Ajouter les images à la fin du contenu
        act.content = act.content.rstrip() + image_markdown
        logger.debug(f"📸 {len(image_paths)} image(s) intégrée(s) dans le contenu de {act_key}")
    
    def _integrate_images_into_twilight_story(self, story: "TwilightZoneStory", image_paths: list[Path]):
        """Intègre les images générées dans l'histoire Twilight Zone.
        
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
            alt_text = f"{story.title} - Image {i+1}"
            image_markdown += f"![{alt_text}]({relative_path})\n\n"
        
        # Ajouter les images à la fin de l'histoire
        story.story = story.story.rstrip() + image_markdown
        logger.debug(f"📸 {len(image_paths)} image(s) intégrée(s) dans l'histoire Twilight Zone")

