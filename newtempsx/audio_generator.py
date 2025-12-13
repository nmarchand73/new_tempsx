"""Générateur audio pour les épisodes NEW TEMPS X.

Supporte plusieurs providers TTS:
- ElevenLabs (recommandé, meilleure qualité)
- OpenAI TTS (alternative, avec traitement batch)
"""

import asyncio
import hashlib
import json
import logging
import os
from enum import Enum
from pathlib import Path
from typing import Optional

import httpx

from .models import Episode, Act, TwilightZoneStory

logger = logging.getLogger(__name__)


class TTSProvider(str, Enum):
    """Providers TTS supportés."""
    ELEVENLABS = "elevenlabs"
    OPENAI = "openai"


class AudioGenerator:
    """Génère des fichiers audio à partir des textes des épisodes."""
    
    def __init__(
        self,
        output_dir: Optional[Path] = None,
        provider: TTSProvider = TTSProvider.ELEVENLABS,
        voice_id: Optional[str] = None,
        voice_id_2: Optional[str] = None,
        model: Optional[str] = None,
        max_concurrent: int = 5,
        cost_optimized: bool = False,
    ):
        """Initialise le générateur audio.
        
        Args:
            output_dir: Répertoire de sortie pour les fichiers audio
            provider: Provider TTS à utiliser
            voice_id: ID de la voix pour narrator_1 (provider-specific)
            voice_id_2: ID de la voix pour narrator_2 (provider-specific)
            model: Modèle à utiliser (provider-specific)
            max_concurrent: Nombre maximum de requêtes parallèles pour le batch (défaut: 5)
            cost_optimized: Active le mode économique (réduit les coûts au détriment de la qualité)
        """
        if output_dir is None:
            output_dir = Path("output") / "audio"
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.provider = provider
        self.max_concurrent = max_concurrent
        self.cost_optimized = cost_optimized  # Doit être défini avant _get_default_model()
        
        self.voice_id = voice_id or self._get_default_voice_id("narrator_1")
        self.voice_id_2 = voice_id_2 or self._get_default_voice_id("narrator_2")
        self.voice_id_twilight = os.getenv("ELEVENLABS_VOICE_ID_TWILIGHT") or self._get_default_voice_id("twilight")
        self.model = model or self._get_default_model()
        
        # Clés API
        self.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        
        # Vérifier les clés API selon le provider
        if provider == TTSProvider.ELEVENLABS and not self.elevenlabs_api_key:
            logger.warning("⚠️  ELEVENLABS_API_KEY non trouvée. La génération audio ne fonctionnera pas.")
        elif provider == TTSProvider.OPENAI and not self.openai_api_key:
            logger.warning("⚠️  OPENAI_API_KEY non trouvée. La génération audio ne fonctionnera pas.")
    
    def _get_default_voice_id(self, narrator: str = "narrator_1") -> str:
        """Retourne l'ID de voix par défaut selon le provider et le narrateur.
        
        Args:
            narrator: "narrator_1" ou "narrator_2"
        """
        if self.provider == TTSProvider.ELEVENLABS:
            # Voix françaises de qualité disponibles:
            # - Charlotte (féminin, voix douce): 2EiwWnXFnvU5JabPnv8n
            # - Domi (féminin, voix claire): EXAVITQu4vr4xnSDxMaL
            # - Antoni (masculin, voix chaude): ErXwobaYiN019PkySvjV
            # - Arnold (masculin, voix profonde): VR6AewLTigWG4xSOukaG
            
            if narrator == "narrator_1":
                # Narrateur 1 par défaut: Charlotte (féminin, voix douce)
                return os.getenv("ELEVENLABS_VOICE_ID_1", "2EiwWnXFnvU5JabPnv8n")
            elif narrator == "twilight":
                # Voix spéciale pour Twilight Zone (style Rod Serling)
                # Par défaut, utilise Arnold (masculin, profonde) si pas de clone configuré
                return os.getenv("ELEVENLABS_VOICE_ID_TWILIGHT", "VR6AewLTigWG4xSOukaG")
            else:
                # Narrateur 2 par défaut: Antoni (masculin, voix chaude) pour contraste
                return os.getenv("ELEVENLABS_VOICE_ID_2", "ErXwobaYiN019PkySvjV")
        return ""
    
    def _get_default_model(self) -> str:
        """Retourne le modèle par défaut selon le provider."""
        if self.provider == TTSProvider.ELEVENLABS:
            if self.cost_optimized:
                # Mode économique : utiliser turbo (plus rapide et moins cher)
                return "eleven_turbo_v2_5"
            return "eleven_multilingual_v2"  # Support multilingue
        elif self.provider == TTSProvider.OPENAI:
            return "tts-1"  # ou "tts-1-hd" pour meilleure qualité
        return ""
    
    def _get_voice_settings(self) -> dict:
        """Retourne les paramètres de voix selon le mode (normal ou économique)."""
        if self.cost_optimized:
            # Mode économique : paramètres réduits pour économiser
            return {
                "stability": 0.4,  # Légèrement réduit
                "similarity_boost": 0.5,  # Réduit (économise des crédits)
                "style": 0.0,
                "use_speaker_boost": False  # Désactivé pour économiser
            }
        else:
            # Mode qualité : paramètres optimaux
            return {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True
            }
    
    def generate_act_audio(self, act: Act, act_key: str, episode_title: str) -> Optional[Path]:
        """Génère l'audio pour un acte (méthode synchrone pour compatibilité).
        
        Args:
            act: L'acte à convertir en audio
            act_key: Clé de l'acte (ex: "acte_1")
            episode_title: Titre de l'épisode (pour le nom de fichier)
            
        Returns:
            Chemin du fichier audio généré, ou None en cas d'erreur
        """
        # Utiliser la méthode asynchrone via asyncio si pas déjà dans une boucle
        try:
            loop = asyncio.get_running_loop()
            # Si on est déjà dans une boucle, cette méthode ne peut pas être utilisée
            # Utilisez _generate_act_audio_async() avec await à la place
            raise RuntimeError("generate_act_audio() ne peut pas être appelé depuis une fonction async. Utilisez _generate_act_audio_async() avec await.")
        except RuntimeError:
            # Pas de boucle en cours, on peut utiliser asyncio.run()
            return asyncio.run(self._generate_act_audio_async(act, act_key, episode_title))
    
    async def _generate_act_audio_async(
        self, 
        act: Act, 
        act_key: str, 
        episode_title: str
    ) -> Optional[Path]:
        """Génère l'audio pour un acte (méthode asynchrone).
        
        Args:
            act: L'acte à convertir en audio
            act_key: Clé de l'acte (ex: "acte_1")
            episode_title: Titre de l'épisode (pour le nom de fichier)
            
        Returns:
            Chemin du fichier audio généré, ou None en cas d'erreur
        """
        # Déterminer la voix selon le narrateur
        narrator = getattr(act, 'narrator', 'narrator_1')
        voice_id = self.voice_id if narrator == "narrator_1" else self.voice_id_2
        
        # Créer un hash du contenu pour le cache (inclut le narrateur pour différencier)
        content_hash = hashlib.md5(
            f"{act.title}{act.content}{narrator}".encode('utf-8')
        ).hexdigest()[:8]
        
        # Nom de fichier
        safe_title = "".join(c for c in episode_title if c.isalnum() or c in (' ', '-', '_')).strip()[:50]
        safe_title = safe_title.replace(' ', '_')
        filename = f"{act_key}_{safe_title}_{content_hash}.mp3"
        output_path = self.output_dir / filename
        
        # Vérifier le cache
        if output_path.exists():
            logger.debug(f"✅ Audio en cache: {output_path.name} (Narrateur: {narrator})")
            return output_path
        
        # Texte complet (titre + contenu)
        full_text = f"{act.title}\n\n{act.content}"
        
        logger.info(f"🎤 Génération audio pour {act_key} (Narrateur: {narrator})...")
        
        try:
            if self.provider == TTSProvider.ELEVENLABS:
                audio_path = await self._generate_elevenlabs_async(full_text, output_path, voice_id)
            elif self.provider == TTSProvider.OPENAI:
                # OpenAI utilise un paramètre voice différent
                openai_voice = "fable" if narrator == "narrator_1" else "onyx"
                audio_path = await self._generate_openai_async(full_text, output_path, openai_voice)
            else:
                raise ValueError(f"Provider non supporté: {self.provider}")
            
            if audio_path and audio_path.exists():
                logger.info(f"✅ Audio généré: {audio_path.name}")
                return audio_path
            else:
                logger.error(f"❌ Échec de génération audio pour {act_key}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erreur lors de la génération audio pour {act_key}: {e}")
            return None
    
    def _generate_elevenlabs(self, text: str, output_path: Path, voice_id: Optional[str] = None) -> Optional[Path]:
        """Génère l'audio avec ElevenLabs (synchrone, pour compatibilité)."""
        return asyncio.run(self._generate_elevenlabs_async(text, output_path, voice_id))
    
    async def _generate_elevenlabs_async(
        self, 
        text: str, 
        output_path: Path, 
        voice_id: Optional[str] = None
    ) -> Optional[Path]:
        """Génère l'audio avec ElevenLabs (asynchrone)."""
        if not self.elevenlabs_api_key:
            raise ValueError("ELEVENLABS_API_KEY non configurée")
        
        if voice_id is None:
            voice_id = self.voice_id
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.elevenlabs_api_key
        }
        
        data = {
            "text": text,
            "model_id": self.model,
            "voice_settings": self._get_voice_settings()
        }
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(url, json=data, headers=headers)
            response.raise_for_status()
            
            # Sauvegarder le fichier audio
            with open(output_path, "wb") as f:
                f.write(response.content)
        
        return output_path
    
    def _generate_openai(self, text: str, output_path: Path, voice: str = "fable") -> Optional[Path]:
        """Génère l'audio avec OpenAI TTS (synchrone, pour compatibilité)."""
        return asyncio.run(self._generate_openai_async(text, output_path, voice))
    
    async def _generate_openai_async(
        self, 
        text: str, 
        output_path: Path, 
        voice: str = "fable"
    ) -> Optional[Path]:
        """Génère l'audio avec OpenAI TTS (asynchrone)."""
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY non configurée")
        
        url = "https://api.openai.com/v1/audio/speech"
        
        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "input": text,
            "voice": voice,  # Utilise le paramètre passé au lieu de "alloy" en dur
            "response_format": "mp3"
        }
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(url, json=data, headers=headers)
            response.raise_for_status()
            
            # Sauvegarder le fichier audio
            with open(output_path, "wb") as f:
                f.write(response.content)
        
        return output_path
    
    async def generate_episode_audio(self, episode: Episode) -> dict[str, Optional[Path]]:
        """Génère l'audio pour tous les actes d'un épisode (avec traitement batch).
        
        Args:
            episode: L'épisode complet
            
        Returns:
            Dictionnaire {act_key: audio_path} pour chaque acte
        """
        logger.info(f"🎵 Génération audio complète pour l'épisode: {episode.episode_title}")
        logger.info(f"📁 Provider: {self.provider.value}")
        logger.info(f"📂 Répertoire de sortie: {self.output_dir}")
        
        # Utiliser le traitement batch asynchrone pour tous les providers
        logger.info(f"⚡ Mode batch activé: {self.max_concurrent} requêtes parallèles")
        return await self._generate_episode_audio_batch(episode)
    
    async def _generate_episode_audio_batch(self, episode: Episode) -> dict[str, Optional[Path]]:
        """Génère l'audio pour tous les actes en parallèle (batch).
        
        Args:
            episode: L'épisode complet
            
        Returns:
            Dictionnaire {act_key: audio_path} pour chaque acte
        """
        audio_files = {}
        
        # Préparer toutes les tâches
        tasks = []
        act_keys = []
        
        for act_key, act in sorted(episode.acts.items()):
            act_keys.append(act_key)
            tasks.append(
                self._generate_act_audio_async(act, act_key, episode.episode_title)
            )
        
        # Exécuter en batch avec limitation du nombre de requêtes parallèles
        logger.info(f"🚀 Lancement de {len(tasks)} générations audio en parallèle...")
        
        # Utiliser un semaphore pour limiter le nombre de requêtes simultanées
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def bounded_generate(task, act_key):
            async with semaphore:
                return act_key, await task
        
        # Créer les tâches avec semaphore
        bounded_tasks = [
            bounded_generate(task, act_key) 
            for task, act_key in zip(tasks, act_keys)
        ]
        
        # Exécuter toutes les tâches
        results = await asyncio.gather(*bounded_tasks, return_exceptions=True)
        
        # Traiter les résultats
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"❌ Erreur dans le batch: {result}")
                continue
            
            act_key, audio_path = result
            audio_files[act_key] = audio_path
        
        generated_count = sum(1 for path in audio_files.values() if path is not None)
        logger.info(f"✅ {generated_count}/{len(audio_files)} fichiers audio générés")
        
        return audio_files
    
    @staticmethod
    def load_episode_from_json(json_path: Path) -> Episode:
        """Charge un épisode depuis un fichier JSON.
        
        Args:
            json_path: Chemin vers le fichier episode.json
            
        Returns:
            Episode chargé depuis le JSON
        """
        if not json_path.exists():
            raise FileNotFoundError(f"Fichier JSON introuvable: {json_path}")
        
        with open(json_path, 'r', encoding='utf-8') as f:
            episode_dict = json.load(f)
        
        # Convertir en modèle Episode
        acts = {
            act_key: Act(**act_data)
            for act_key, act_data in episode_dict['acts'].items()
        }
        
        episode = Episode(
            episode_title=episode_dict['episode_title'],
            scenario_input=episode_dict['scenario_input'],
            narrative_arc=episode_dict['narrative_arc'],
            acts=acts
        )
        
        return episode
    
    async def generate_audio_from_json(
        self,
        json_path: Path,
        episode: Optional[Episode] = None
    ) -> dict[str, Optional[Path]]:
        """Génère l'audio à partir d'un fichier JSON existant.
        
        Args:
            json_path: Chemin vers le fichier episode.json
            episode: Episode déjà chargé (optionnel, sera chargé depuis JSON si non fourni)
            
        Returns:
            Dictionnaire {act_key: audio_path} pour chaque acte
        """
        if episode is None:
            logger.info(f"📂 Chargement de l'épisode depuis: {json_path}")
            episode = self.load_episode_from_json(json_path)
            logger.info(f"✅ Épisode chargé: {episode.episode_title}")
        
        return await self.generate_episode_audio(episode)
    
    async def generate_twilight_zone_audio(
        self,
        twilight_story: TwilightZoneStory,
        episode_title: str
    ) -> Optional[Path]:
        """Génère l'audio pour une histoire Twilight Zone avec une voix spéciale.
        
        Args:
            twilight_story: L'histoire Twilight Zone à convertir en audio
            episode_title: Titre de l'épisode (pour le nom de fichier)
            
        Returns:
            Chemin du fichier audio généré, ou None en cas d'erreur
        """
        if not twilight_story:
            logger.warning("⚠️  Aucune histoire Twilight Zone fournie")
            return None
        
        # Créer un hash du contenu pour le cache
        content_hash = hashlib.md5(
            f"{twilight_story.title}{twilight_story.story}".encode('utf-8')
        ).hexdigest()[:8]
        
        # Nom de fichier
        safe_title = "".join(c for c in episode_title if c.isalnum() or c in (' ', '-', '_')).strip()[:50]
        safe_title = safe_title.replace(' ', '_')
        filename = f"twilight_zone_{safe_title}_{content_hash}.mp3"
        output_path = self.output_dir / filename
        
        # Vérifier le cache
        if output_path.exists():
            logger.debug(f"✅ Audio Twilight Zone en cache: {output_path.name}")
            return output_path
        
        # Texte complet (titre + histoire)
        full_text = f"{twilight_story.title}\n\n{twilight_story.story}"
        
        logger.info(f"🎬 Génération audio Twilight Zone avec voix spéciale...")
        logger.info(f"   Titre: {twilight_story.title}")
        
        try:
            if self.provider == TTSProvider.ELEVENLABS:
                # Utiliser la voix spéciale Twilight Zone (Rod Serling ou similaire)
                audio_path = await self._generate_elevenlabs_async(full_text, output_path, self.voice_id_twilight)
            elif self.provider == TTSProvider.OPENAI:
                # OpenAI: utiliser "onyx" qui est une voix masculine profonde
                audio_path = await self._generate_openai_async(full_text, output_path, "onyx")
            else:
                raise ValueError(f"Provider non supporté: {self.provider}")
            
            if audio_path and audio_path.exists():
                logger.info(f"✅ Audio Twilight Zone généré: {audio_path.name}")
                return audio_path
            else:
                logger.error(f"❌ Échec de génération audio Twilight Zone")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erreur lors de la génération audio Twilight Zone: {e}")
            return None

