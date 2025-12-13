"""Générateur d'images pour les épisodes NEW TEMPS X.

Utilise l'API OpenAI DALL-E pour générer des images à partir des prompts.
"""

import asyncio
import hashlib
import logging
import os
from pathlib import Path
from typing import Optional, TYPE_CHECKING

import httpx

from .models import Episode, Act, TwilightZoneStory

if TYPE_CHECKING:
    from .exporters import EpisodeExporter

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
            size: Taille de l'image ("1024x1024", "1792x1024", "1024x1792" pour dall-e-3, ou "256x256", "512x512", "1024x1024" pour dall-e-2)
            model: Modèle DALL-E à utiliser ("dall-e-3" ou "dall-e-2", par défaut "dall-e-3")
            
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
            "n": 1
        }
        
        # Le paramètre "quality" n'est supporté que par DALL-E 3
        if model == "dall-e-3":
            data["quality"] = "standard"
        
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
    
    async def generate_episode_images(
        self, 
        episode: Episode,
        exporter: Optional["EpisodeExporter"] = None
    ) -> dict[str, list[Path]]:
        """Génère toutes les images pour un épisode complet de manière progressive.
        
        Génère et intègre les images une par une, en mettant à jour le markdown
        après chaque génération.
        
        Args:
            episode: L'épisode complet
            exporter: Exporteur optionnel pour mettre à jour le markdown progressivement
            
        Returns:
            Dictionnaire {act_key: [image_paths]} pour chaque acte
        """
        if not self.openai_api_key:
            logger.warning("⚠️  OPENAI_API_KEY non configurée, génération d'images ignorée")
            return {}
        
        logger.info(f"🎨 Génération progressive des images pour l'épisode: {episode.episode_title}")
        all_images = {}
        
        # Mapping des noms de fichiers pour les actes
        act_names = {
            "acte_1": "01_le_signal",
            "acte_2": "02_le_decryptage",
            "acte_3": "03_la_tension",
            "acte_4": "04_la_fiction",
            "acte_5": "05_le_dialogue",
            "acte_6": "06_la_memoire",
            "acte_7": "07_la_transmission",
        }
        
        # Générer les images pour chaque acte de manière progressive
        for act_key, act in episode.acts.items():
            image_prompts = getattr(act, "image_prompts", [])
            if not image_prompts:
                logger.debug(f"📝 Aucun prompt d'image pour {act_key}")
                continue
            
            logger.info(f"🎨 Génération de {len(image_prompts)} image(s) pour {act_key}...")
            generated_images = []
            
            # Générer chaque image une par une
            total_prompts = len(image_prompts)
            for i, prompt in enumerate(image_prompts):
                # Créer un nom de fichier basé sur l'acte et l'index
                safe_title = "".join(c for c in episode.episode_title if c.isalnum() or c in (' ', '-', '_')).strip()[:30]
                safe_title = safe_title.replace(' ', '_')
                prompt_hash = hashlib.md5(prompt.encode('utf-8')).hexdigest()[:6]
                filename = f"{act_key}_{safe_title}_{i+1}_{prompt_hash}.png"
                output_path = self.output_dir / filename
                
                # Générer l'image
                image_path = await self.generate_image_from_prompt(prompt, output_path)
                if image_path:
                    generated_images.append(image_path)
                    logger.info(f"  ✅ Image {i+1}/{total_prompts} générée: {image_path.name}")
                    
                    # Intégrer immédiatement l'image dans le contenu de l'acte de manière harmonieuse
                    self._integrate_single_image_into_act(
                        act, 
                        image_path, 
                        act_key, 
                        i+1,
                        total_images=total_prompts,
                        prompt=prompt
                    )
                    
                    # Mettre à jour le markdown ET le JSON progressivement si un exporteur est fourni
                    if exporter:
                        act_filename = act_names.get(act_key, act_key)
                        exporter.export_act_markdown(act_key, act, act_filename)
                        # Mettre à jour aussi le JSON pour que l'UI voie les changements
                        exporter.export_json(episode)
                        logger.debug(f"  📝 Markdown et JSON mis à jour pour {act_key}")
            
            if generated_images:
                all_images[act_key] = generated_images
                logger.info(f"✅ {len(generated_images)}/{len(image_prompts)} image(s) générée(s) pour {act_key}")
        
        # Générer les images pour l'histoire Twilight Zone si disponible
        if episode.twilight_zone_story:
            image_prompts = getattr(episode.twilight_zone_story, "image_prompts", [])
            if image_prompts:
                logger.info(f"🎬 Génération de {len(image_prompts)} image(s) pour l'histoire Twilight Zone...")
                generated_images = []
                
                total_prompts = len(image_prompts)
                for i, prompt in enumerate(image_prompts):
                    safe_title = "".join(c for c in episode.episode_title if c.isalnum() or c in (' ', '-', '_')).strip()[:30]
                    safe_title = safe_title.replace(' ', '_')
                    prompt_hash = hashlib.md5(prompt.encode('utf-8')).hexdigest()[:6]
                    filename = f"twilight_zone_{safe_title}_{i+1}_{prompt_hash}.png"
                    output_path = self.output_dir / filename
                    
                    image_path = await self.generate_image_from_prompt(prompt, output_path)
                    if image_path:
                        generated_images.append(image_path)
                        logger.info(f"  ✅ Image {i+1}/{total_prompts} générée: {image_path.name}")
                        
                        # Intégrer immédiatement l'image dans l'histoire de manière harmonieuse
                        self._integrate_single_image_into_twilight_story(
                            episode.twilight_zone_story, 
                            image_path, 
                            i+1,
                            total_images=total_prompts,
                            prompt=prompt
                        )
                        
                        # Mettre à jour le markdown ET le JSON progressivement
                        if exporter:
                            exporter.export_twilight_zone_story(episode.twilight_zone_story)
                            # Mettre à jour aussi le JSON pour que l'UI voie les changements
                            exporter.export_json(episode)
                            logger.debug(f"  📝 Markdown et JSON Twilight Zone mis à jour")
                
                if generated_images:
                    all_images["twilight_zone"] = generated_images
                    logger.info(f"✅ {len(generated_images)}/{len(image_prompts)} image(s) générée(s) pour l'histoire Twilight Zone")
        
        total_generated = sum(len(images) for images in all_images.values())
        logger.info(f"✅ {total_generated} image(s) générée(s) au total pour l'épisode")
        
        return all_images
    
    def _find_best_image_position(
        self,
        content: str,
        image_index: int,
        total_images: int,
        prompt: str
    ) -> int:
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
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        
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
        self, 
        act: "Act", 
        image_path: Path, 
        act_key: str, 
        image_index: int,
        total_images: int = 1,
        prompt: str = ""
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
        position = self._find_best_image_position(
            act.content,
            image_index,
            total_images,
            prompt
        )
        
        if position >= 0:
            # Diviser le contenu en paragraphes
            paragraphs = [p.strip() for p in act.content.split('\n\n') if p.strip()]
            
            if position < len(paragraphs):
                # Insérer l'image après le paragraphe à la position trouvée
                paragraphs.insert(position + 1, image_markdown.strip())
                act.content = '\n\n'.join(paragraphs)
                logger.debug(f"📸 Image {image_index} intégrée harmonieusement à la position {position + 1}/{len(paragraphs)} dans {act_key}")
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
            alt_text = f"{act.title} - Image {i+1}"
            image_markdown += f"![{alt_text}]({relative_path})\n\n"
        
        # Ajouter les images à la fin du contenu
        act.content = act.content.rstrip() + image_markdown
        logger.debug(f"📸 {len(image_paths)} image(s) intégrée(s) dans le contenu de {act_key}")
    
    def _integrate_single_image_into_twilight_story(
        self, 
        story: "TwilightZoneStory", 
        image_path: Path, 
        image_index: int,
        total_images: int = 1,
        prompt: str = ""
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
        position = self._find_best_image_position(
            story.story,
            image_index,
            total_images,
            prompt
        )
        
        if position >= 0:
            # Diviser l'histoire en paragraphes
            paragraphs = [p.strip() for p in story.story.split('\n\n') if p.strip()]
            
            if position < len(paragraphs):
                # Insérer l'image après le paragraphe à la position trouvée
                paragraphs.insert(position + 1, image_markdown.strip())
                story.story = '\n\n'.join(paragraphs)
                logger.debug(f"📸 Image {image_index} intégrée harmonieusement à la position {position + 1}/{len(paragraphs)} dans l'histoire Twilight Zone")
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
            alt_text = f"{story.title} - Image {i+1}"
            image_markdown += f"![{alt_text}]({relative_path})\n\n"
        
        # Ajouter les images à la fin de l'histoire
        story.story = story.story.rstrip() + image_markdown
        logger.debug(f"📸 {len(image_paths)} image(s) intégrée(s) dans l'histoire Twilight Zone")

