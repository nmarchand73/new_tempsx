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
import re
import shutil
from enum import Enum
from pathlib import Path

import httpx

from .http_utils import request_with_retry
from .models import Act, Episode, TwilightZoneStory

logger = logging.getLogger(__name__)


class TTSProvider(str, Enum):
    """Providers TTS supportés."""

    ELEVENLABS = "elevenlabs"
    OPENAI = "openai"


class AudioGenerator:
    """Génère des fichiers audio à partir des textes des épisodes."""

    # Voix OpenAI pour Twilight Zone - TOUJOURS utiliser "onyx" (voix masculine profonde, parfaite pour l'ambiance)
    # Cette voix est optimale et ne doit PAS être changée
    OPENAI_TWILIGHT_VOICE = "onyx"

    # Limites de caractères par requête TTS
    OPENAI_MAX_CHARS = 4096
    ELEVENLABS_MAX_CHARS = 9500

    def __init__(
        self,
        output_dir: Path | None = None,
        provider: TTSProvider = TTSProvider.ELEVENLABS,
        voice_id: str | None = None,
        voice_id_2: str | None = None,
        model: str | None = None,
        max_concurrent: int = 3,
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
            return os.getenv("OPENAI_TTS_MODEL", "tts-1")  # ex: tts-1-hd
        return ""

    def _get_voice_settings(self) -> dict:
        """Retourne les paramètres de voix selon le mode (normal ou économique)."""
        if self.cost_optimized:
            # Mode économique : paramètres réduits pour économiser
            return {
                "stability": 0.4,  # Légèrement réduit
                "similarity_boost": 0.5,  # Réduit (économise des crédits)
                "style": 0.0,
                "use_speaker_boost": False,  # Désactivé pour économiser
            }
        else:
            # Mode qualité : paramètres optimaux
            return {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True}

    def _clean_text_for_tts(self, text: str) -> str:
        """Nettoie le texte pour la synthèse vocale en supprimant les éléments markdown non lisibles.

        Supprime:
        - Les images markdown: ![alt](url)
        - Les liens markdown: [text](url) (garde seulement le texte)
        - Les éléments de formatage excessifs

        Args:
            text: Texte à nettoyer

        Returns:
            Texte nettoyé, prêt pour la synthèse vocale
        """
        # Supprimer les images markdown: ![alt text](url)
        text = re.sub(r"!\[([^\]]*)\]\([^\)]+\)", r"\1", text)

        # Remplacer les liens markdown par leur texte: [text](url) -> text
        text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)

        # Supprimer les URLs brutes (http://, https://)
        text = re.sub(r"https?://[^\s]+", "", text)

        # Nettoyer les espaces multiples
        text = re.sub(r"\s+", " ", text)

        # Nettoyer les sauts de ligne multiples
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

        return text.strip()

    def generate_act_audio(self, act: Act, act_key: str, episode_title: str) -> Path | None:
        """Génère l'audio pour un acte (méthode synchrone pour compatibilité).

        Args:
            act: L'acte à convertir en audio
            act_key: Clé de l'acte (ex: "acte_1")
            episode_title: Titre de l'épisode (pour le nom de fichier)

        Returns:
            Chemin du fichier audio généré, ou None en cas d'erreur
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._generate_act_audio_async(act, act_key, episode_title))
        raise RuntimeError(
            "generate_act_audio() ne peut pas être appelé depuis du code async : utilisez "
            "`await _generate_act_audio_async(...)`."
        )

    async def _generate_act_audio_async(self, act: Act, act_key: str, episode_title: str) -> Path | None:
        """Génère l'audio pour un acte (méthode asynchrone).

        Args:
            act: L'acte à convertir en audio
            act_key: Clé de l'acte (ex: "acte_1")
            episode_title: Titre de l'épisode (pour le nom de fichier)

        Returns:
            Chemin du fichier audio généré, ou None en cas d'erreur
        """
        # Déterminer la voix selon le narrateur
        narrator = getattr(act, "narrator", "narrator_1")
        voice_id = self.voice_id if narrator == "narrator_1" else self.voice_id_2

        # Créer un hash du contenu pour le cache (inclut le narrateur pour différencier)
        content_hash = hashlib.md5(f"{act.title}{act.content}{narrator}".encode()).hexdigest()[:8]

        # Nom de fichier
        safe_title = "".join(c for c in episode_title if c.isalnum() or c in (" ", "-", "_")).strip()[:50]
        safe_title = safe_title.replace(" ", "_")
        filename = f"{act_key}_{safe_title}_{content_hash}.mp3"
        output_path = self.output_dir / filename

        # Vérifier le cache
        if output_path.exists():
            logger.debug(f"✅ Audio en cache: {output_path.name} (Narrateur: {narrator})")
            return output_path

        # Texte complet (titre + contenu)
        full_text = f"{act.title}\n\n{act.content}"

        # Nettoyer le texte pour la synthèse vocale (supprimer images markdown, liens, etc.)
        cleaned_text = self._clean_text_for_tts(full_text)

        # Logger la longueur du texte pour debug
        logger.debug(f"📏 Longueur du texte pour {act_key}: {len(cleaned_text)} caractères")

        logger.info(f"🎤 Génération audio pour {act_key} (Narrateur: {narrator})...")

        try:
            if self.provider == TTSProvider.ELEVENLABS:
                audio_path = await self._generate_elevenlabs_async(cleaned_text, output_path, voice_id)
            elif self.provider == TTSProvider.OPENAI:
                # OpenAI utilise un paramètre voice différent
                openai_voice = "fable" if narrator == "narrator_1" else "onyx"
                audio_path = await self._generate_openai_async(cleaned_text, output_path, openai_voice)
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

    async def _generate_elevenlabs_single(self, text: str, output_path: Path, voice_id: str | None = None) -> Path:
        """Un appel ElevenLabs (texte <= ELEVENLABS_MAX_CHARS)."""
        if not self.elevenlabs_api_key:
            raise ValueError("ELEVENLABS_API_KEY non configurée")
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id or self.voice_id}"
        headers = {"Accept": "audio/mpeg", "xi-api-key": self.elevenlabs_api_key}
        data = {"text": text, "model_id": self.model, "voice_settings": self._get_voice_settings()}
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await request_with_retry(client, "POST", url, json=data, headers=headers)
        output_path.write_bytes(response.content)
        return output_path

    async def _generate_openai_single(self, text: str, output_path: Path, voice: str = "fable") -> Path:
        """Un appel OpenAI TTS (texte <= OPENAI_MAX_CHARS)."""
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY non configurée")
        headers = {"Authorization": f"Bearer {self.openai_api_key}"}
        data = {"model": self.model, "input": text, "voice": voice, "response_format": "mp3"}
        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                response = await request_with_retry(
                    client, "POST", "https://api.openai.com/v1/audio/speech", json=data, headers=headers
                )
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "❌ OpenAI TTS HTTP %s (modèle %s, voix %s, %d car.): %s",
                    exc.response.status_code,
                    self.model,
                    voice,
                    len(text),
                    exc.response.text[:300],
                )
                raise
        output_path.write_bytes(response.content)
        return output_path

    async def _generate_elevenlabs_async(self, text: str, output_path: Path, voice_id: str | None = None) -> Path:
        return await self._synthesize_chunked(
            text,
            output_path,
            self.ELEVENLABS_MAX_CHARS,
            lambda chunk, path: self._generate_elevenlabs_single(chunk, path, voice_id),
        )

    async def _generate_openai_async(self, text: str, output_path: Path, voice: str = "fable") -> Path:
        return await self._synthesize_chunked(
            text,
            output_path,
            self.OPENAI_MAX_CHARS,
            lambda chunk, path: self._generate_openai_single(chunk, path, voice),
        )

    async def _synthesize_chunked(self, text: str, output_path: Path, max_chars: int, synth) -> Path:
        """Découpe le texte si besoin, synthétise chaque segment, puis concatène les MP3."""
        chunks = self._split_text_into_chunks(text, max_chars)
        if len(chunks) == 1:
            return await synth(chunks[0], output_path)

        logger.info("📝 Texte long (%d car.): %d segments de %d car. max", len(text), len(chunks), max_chars)
        temp_files = [
            output_path.with_name(f"{output_path.stem}_chunk_{i}{output_path.suffix}") for i in range(len(chunks))
        ]
        try:
            for chunk, temp in zip(chunks, temp_files):
                await synth(chunk, temp)
            await self._concatenate_audio_files(temp_files, output_path)
            return output_path
        except BaseException:
            output_path.unlink(missing_ok=True)  # pas de fichier partiel pris pour du cache
            raise
        finally:
            for temp in temp_files:
                temp.unlink(missing_ok=True)

    def _split_text_into_chunks(self, text: str, max_chars: int = 4096) -> list[str]:
        """Découpe un texte en segments de taille maximale, en respectant les phrases.

        Args:
            text: Texte à découper
            max_chars: Nombre maximum de caractères par segment

        Returns:
            Liste de segments de texte
        """
        if len(text) <= max_chars:
            return [text]

        chunks = []
        remaining_text = text

        while len(remaining_text) > max_chars:
            # Prendre un segment de la taille maximale
            chunk = remaining_text[:max_chars]

            # Chercher le dernier point de phrase dans les 80% finaux du segment
            search_start = int(max_chars * 0.8)
            last_sentence_end = -1

            for i in range(len(chunk) - 1, search_start - 1, -1):
                if chunk[i] in ".!?":
                    # Vérifier que c'est bien une fin de phrase (suivie d'un espace ou fin de texte)
                    if i == len(chunk) - 1 or chunk[i + 1] in " \n":
                        last_sentence_end = i
                        break

            if last_sentence_end > search_start:
                # Couper à la fin de phrase
                chunk = chunk[: last_sentence_end + 1]
                remaining_text = remaining_text[last_sentence_end + 1 :].lstrip()
            else:
                # Couper à un espace si possible
                last_space = chunk.rfind(" ", search_start)
                if last_space > search_start:
                    chunk = chunk[:last_space]
                    remaining_text = remaining_text[last_space:].lstrip()
                else:
                    # Dernier recours: couper brutalement
                    remaining_text = remaining_text[max_chars:]

            chunks.append(chunk)

        # Ajouter le reste
        if remaining_text:
            chunks.append(remaining_text)

        return chunks

    async def _concatenate_audio_files(self, audio_files: list[Path], output_path: Path) -> Path:
        """Concatène des MP3 avec ffmpeg (concat demuxer, sans ré-encodage).

        Sans ffmpeg, repli sur une concaténation binaire : lisible par la plupart des lecteurs
        mais avec des en-têtes en double (durée affichée et navigation parfois inexactes).
        """
        if not audio_files:
            raise ValueError("Aucun fichier audio à concaténer")
        if len(audio_files) == 1:
            shutil.copy2(audio_files[0], output_path)
            return output_path

        if shutil.which("ffmpeg"):
            list_file = output_path.with_suffix(".concat.txt")
            list_file.write_text(
                "".join(
                    f"file '{f.resolve().as_posix().replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'\n"
                    for f in audio_files
                ),
                encoding="utf-8",
            )
            try:
                proc = await asyncio.create_subprocess_exec(
                    "ffmpeg",
                    "-y",
                    "-loglevel",
                    "error",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(list_file),
                    "-c",
                    "copy",
                    str(output_path),
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await proc.communicate()
            finally:
                list_file.unlink(missing_ok=True)
            if proc.returncode == 0:
                return output_path
            logger.warning("⚠️  ffmpeg a échoué (%s), repli sur concaténation binaire", stderr.decode()[:200])
        else:
            logger.warning("⚠️  ffmpeg introuvable: concaténation binaire (installez ffmpeg pour de meilleurs MP3)")

        with open(output_path, "wb") as out:
            for f in audio_files:
                out.write(f.read_bytes())
        return output_path

    async def generate_episode_audio(self, episode: Episode) -> dict[str, Path | None]:
        """Génère l'audio pour tous les actes d'un épisode (séquentiel).

        Args:
            episode: L'épisode complet

        Returns:
            Dictionnaire {act_key: audio_path} pour chaque acte
        """
        logger.info(f"🎵 Génération audio complète pour l'épisode: {episode.episode_title}")
        logger.info(f"📁 Provider: {self.provider.value}")
        logger.info(f"📂 Répertoire de sortie: {self.output_dir}")

        # Utiliser le traitement séquentiel pour éviter les erreurs 400
        logger.info("🔄 Mode séquentiel activé: génération un acte à la fois")
        return await self._generate_episode_audio_sequential(episode)

    async def _generate_episode_audio_sequential(self, episode: Episode) -> dict[str, Path | None]:
        """Génère l'audio de tous les actes, `max_concurrent` en parallèle (nom conservé pour compatibilité)."""
        acts = sorted(episode.acts.items())
        semaphore = asyncio.Semaphore(max(1, self.max_concurrent))

        async def one(act_key: str, act: Act) -> Path | None:
            async with semaphore:
                return await self._generate_act_audio_async(act, act_key, episode.episode_title)

        logger.info("🔄 Génération de %d fichiers audio (%d en parallèle)...", len(acts), self.max_concurrent)
        results = await asyncio.gather(*(one(k, a) for k, a in acts), return_exceptions=True)
        audio_files: dict[str, Path | None] = {}
        for (act_key, _), result in zip(acts, results):
            if isinstance(result, BaseException):
                logger.error("❌ Audio %s: %s", act_key, result)
                result = None
            audio_files[act_key] = result
        logger.info("✅ %d/%d fichiers audio générés", sum(r is not None for r in audio_files.values()), len(acts))
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

        with open(json_path, encoding="utf-8") as f:
            episode_dict = json.load(f)

        # Convertir en modèle Episode
        acts = {act_key: Act(**act_data) for act_key, act_data in episode_dict["acts"].items()}

        episode = Episode(
            episode_title=episode_dict["episode_title"],
            scenario_input=episode_dict["scenario_input"],
            narrative_arc=episode_dict["narrative_arc"],
            acts=acts,
        )

        return episode

    async def generate_audio_from_json(self, json_path: Path, episode: Episode | None = None) -> dict[str, Path | None]:
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

    async def generate_twilight_zone_audio(self, twilight_story: TwilightZoneStory, episode_title: str) -> Path | None:
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
        content_hash = hashlib.md5(f"{twilight_story.title}{twilight_story.story}".encode()).hexdigest()[:8]

        # Nom de fichier
        safe_title = "".join(c for c in episode_title if c.isalnum() or c in (" ", "-", "_")).strip()[:50]
        safe_title = safe_title.replace(" ", "_")
        filename = f"twilight_zone_{safe_title}_{content_hash}.mp3"
        output_path = self.output_dir / filename

        # Vérifier le cache
        if output_path.exists():
            logger.debug(f"✅ Audio Twilight Zone en cache: {output_path.name}")
            return output_path

        # Texte complet (titre + histoire)
        full_text = f"{twilight_story.title}\n\n{twilight_story.story}"

        # Nettoyer le texte pour la synthèse vocale (supprimer images markdown, liens, etc.)
        cleaned_text = self._clean_text_for_tts(full_text)

        logger.info("🎬 Génération audio Twilight Zone avec voix spéciale...")
        logger.info(f"   Titre: {twilight_story.title}")

        try:
            if self.provider == TTSProvider.ELEVENLABS:
                # Utiliser la voix spéciale Twilight Zone (Rod Serling ou similaire)
                audio_path = await self._generate_elevenlabs_async(cleaned_text, output_path, self.voice_id_twilight)
            elif self.provider == TTSProvider.OPENAI:
                # OpenAI: TOUJOURS utiliser la voix définie dans OPENAI_TWILIGHT_VOICE ("onyx")
                # Cette voix masculine profonde est optimale pour l'ambiance Twilight Zone - NE PAS CHANGER
                audio_path = await self._generate_openai_async(cleaned_text, output_path, self.OPENAI_TWILIGHT_VOICE)
                logger.info(f"   Voix utilisée: {self.OPENAI_TWILIGHT_VOICE} (voix fixe pour Twilight Zone)")
            else:
                raise ValueError(f"Provider non supporté: {self.provider}")

            if audio_path and audio_path.exists():
                logger.info(f"✅ Audio Twilight Zone généré: {audio_path.name}")
                return audio_path
            else:
                logger.error("❌ Échec de génération audio Twilight Zone")
                return None

        except Exception as e:
            logger.error(f"❌ Erreur lors de la génération audio Twilight Zone: {e}")
            return None
