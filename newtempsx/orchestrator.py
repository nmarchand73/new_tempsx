"""Orchestrateur principal pour générer un épisode NEW TEMPS X."""

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional, Type, TypeVar, TYPE_CHECKING

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
)
from pydantic import BaseModel, ValidationError

from .models import (
    ActOutput,
    ActsOneToThreeOutput,
    ArcOutput,
    Act,
    Episode,
    TwilightZoneStory,
    ValidationOutput,
)

if TYPE_CHECKING:
    from .exporters import EpisodeExporter

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Narrateurs alternés (style Temps X) : impairs -> narrator_1, pairs -> narrator_2
NARRATORS = {n: ("narrator_1" if n % 2 else "narrator_2") for n in range(1, 8)}

ACT_FILE_NAMES = {
    1: "01_le_signal",
    2: "02_le_decryptage",
    3: "03_la_tension",
    4: "04_la_fiction",
    5: "05_le_dialogue",
    6: "06_la_memoire",
    7: "07_la_transmission",
}


class EpisodeRejectedError(ValueError):
    """L'épisode a été rejeté par la validation narrative (déclenche une régénération)."""


class StructuredOutputError(ValueError):
    """Le modèle n'a pas retourné de sortie conforme au schéma demandé."""


class EpisodeOrchestrator:
    """Orchestre la génération d'un épisode complet en 7 actes via Claude Agent SDK + Skills.

    Chaque étape est une requête distincte avec un schéma de sortie (`output_format`).
    Les étapes sont chaînées avec `resume=<session_id>` : le contexte de la conversation
    est conservé alors que le schéma change à chaque étape.
    """

    def __init__(
        self,
        project_root: Optional[Path] = None,
        exporter: Optional["EpisodeExporter"] = None,
        debug: bool = False,
    ):
        """
        Args:
            project_root: Racine du projet (Skills dans .claude/skills/). Défaut: cwd.
            exporter: Exporteur pour l'export progressif (optionnel).
            debug: Active les logs de debug du SDK sur stderr.

        Variables d'environnement optionnelles:
            NEWTEMPSX_MODEL: modèle Claude à utiliser (défaut: celui du SDK/CLI).
            NEWTEMPSX_MAX_BUDGET_USD: budget maximal par étape (défaut: illimité).
        """
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.exporter = exporter
        self.debug = debug
        self._is_retry = False
        self._session_id: Optional[str] = None
        self.total_cost_usd = 0.0

        self.model = os.getenv("NEWTEMPSX_MODEL") or None
        budget = os.getenv("NEWTEMPSX_MAX_BUDGET_USD")
        self.max_budget_usd = float(budget) if budget else None

    # ------------------------------------------------------------------ SDK
    def _options(self, output_model: Type[BaseModel]) -> ClaudeAgentOptions:
        """Options SDK pour une étape : schéma de sortie + reprise de la session en cours."""
        return ClaudeAgentOptions(
            setting_sources=["project"],  # Charge les Skills depuis .claude/skills/
            # WebFetch/WebSearch : recherche et vérification des liens (l'outil "Browser" n'existe pas).
            allowed_tools=["Skill", "Read", "WebFetch", "WebSearch"],
            cwd=str(self.project_root),
            debug_stderr=sys.stderr if self.debug else None,
            model=self.model,
            max_budget_usd=self.max_budget_usd,
            output_format={"type": "json_schema", "schema": output_model.model_json_schema()},
            resume=self._session_id,
        )

    async def _run_step(self, prompt: str, output_model: Type[T]) -> T:
        """Exécute une étape et retourne la sortie validée par `output_model`."""
        text_parts: list[str] = []
        structured = None
        async with ClaudeSDKClient(options=self._options(output_model)) as client:
            await client.query(prompt)
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    text_parts.extend(b.text for b in message.content if isinstance(b, TextBlock))
                elif isinstance(message, ResultMessage):
                    self._session_id = message.session_id or self._session_id
                    if message.total_cost_usd:
                        self.total_cost_usd += message.total_cost_usd
                    if message.is_error:
                        raise StructuredOutputError(
                            f"Étape en erreur ({message.subtype}, HTTP {message.api_error_status}): "
                            f"{'; '.join(message.errors or []) or message.result}"
                        )
                    structured = message.structured_output

        data = structured if structured is not None else self._parse_json_response("\n".join(text_parts))
        try:
            return output_model.model_validate(data)
        except ValidationError as exc:
            raise StructuredOutputError(f"Sortie non conforme à {output_model.__name__}: {exc}") from exc

    @staticmethod
    def _parse_json_response(text: str) -> dict:
        """Repli si le SDK ne renvoie pas `structured_output` : extrait le premier objet JSON du texte."""
        if not text.strip():
            raise StructuredOutputError("Réponse vide")
        candidates = [text.strip()]
        candidates += re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        decoder = json.JSONDecoder()
        start = text.find("{")
        while start != -1:
            try:
                obj, _ = decoder.raw_decode(text[start:])
                candidates.append(obj)
                break
            except json.JSONDecodeError:
                start = text.find("{", start + 1)
        for cand in candidates:
            if isinstance(cand, dict):
                return cand
            try:
                parsed = json.loads(cand, strict=False)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        raise StructuredOutputError(f"Pas de JSON exploitable dans la réponse: {text[:300]!r}")

    def _retry_warning(self) -> str:
        if not self._is_retry:
            return ""
        return (
            "\n\n⚠️ RÉGÉNÉRATION: l'épisode précédent a été rejeté (références invalides ou non "
            "vérifiables). Utilise UNIQUEMENT des URLs réelles, vérifiées avec WebFetch avant inclusion."
        )

    # ------------------------------------------------------------ pipeline
    async def generate_episode(self, scenario: str) -> Episode:
        """Génère un épisode complet; une seule régénération en cas de rejet par la validation.

        Raises:
            EpisodeRejectedError: rejet persistant après la régénération.
            StructuredOutputError: sortie du modèle inexploitable.
        """
        max_retries = 1
        for attempt in range(max_retries + 1):
            self._is_retry = attempt > 0
            self._session_id = None  # chaque tentative repart d'une conversation neuve
            if attempt:
                logger.warning("🔄 Régénération %d/%d après rejet de l'épisode", attempt, max_retries)
            logger.info("🎬 Début de la génération d'un épisode NEW TEMPS X")
            logger.info("📝 Scénario: %s...", scenario[:100])
            try:
                episode = await self._generate_episode_internal(scenario)
                logger.info("💰 Coût total estimé: %.2f $", self.total_cost_usd)
                return episode
            except EpisodeRejectedError as exc:
                if attempt >= max_retries:
                    logger.error("❌ Échec après %d régénération(s)", max_retries)
                    raise
                logger.warning("❌ %s", str(exc)[:200])
        raise AssertionError("unreachable")

    def _export_act(self, partial: Episode, number: int, act: Act) -> None:
        partial.acts[f"acte_{number}"] = act
        if self.exporter:
            self.exporter.export_act_markdown(f"acte_{number}", act, ACT_FILE_NAMES[number])
            self.exporter.export_partial_json(partial)

    @staticmethod
    def _to_act(data: ActOutput, number: int) -> Act:
        return Act(narrator=NARRATORS[number], **data.model_dump())

    @staticmethod
    def _previous_titles(partial: Episode) -> str:
        return "\n".join(f"- Acte {key.split('_')[1]}: {act.title}" for key, act in partial.acts.items())

    async def _generate_episode_internal(self, scenario: str) -> Episode:
        logger.info("📐 Étape 1/7: Définition de l'arc narratif...")
        arc = await self._define_narrative_arc(scenario)
        themes = arc.themes.model_dump()
        partial = Episode(
            episode_title=arc.episode_title,
            scenario_input=scenario,
            narrative_arc=arc.narrative_arc,
            acts={},
        )
        if self.exporter:
            self.exporter.export_partial_json(partial)

        logger.info("🔬 Étape 2/7: Actes I, II et III (Science Editor)...")
        acts_1_3 = await self._generate_acts_1_3(scenario, arc)
        for number, data in enumerate([acts_1_3.acte_1, acts_1_3.acte_2, acts_1_3.acte_3], start=1):
            self._export_act(partial, number, self._to_act(data, number))

        # Actes IV à VII : (numéro, skill, intitulé)
        remaining = [
            (4, "fiction-writer", "La Fiction"),
            (5, "dialogue", "Le Dialogue"),
            (6, "archivist", "La Mémoire"),
            (7, "audience", "La Transmission"),
        ]
        for number, skill, label in remaining:
            logger.info("✍️  Étape %d/7: Acte %d (%s)...", number - 1, number, skill)
            prompt = (
                f"Utilise le Skill {skill} pour générer l'Acte {number} ({label}) pour cet épisode NEW TEMPS X.\n\n"
                f"Scénario: {scenario}\n"
                f"Arc narratif: {arc.narrative_arc}\n"
                f"Thème Acte {number}: {themes[f'acte_{number}']}\n"
                f"Actes précédents:\n{self._previous_titles(partial)}\n"
                f"{self._retry_warning()}\n\n"
                "Le Skill contient toutes les instructions nécessaires. Réponds selon le schéma fourni."
            )
            act = self._to_act(await self._run_step(prompt, ActOutput), number)
            logger.info("✅ Acte %d généré: %s", number, act.title)
            self._export_act(partial, number, act)

        episode = Episode(**partial.model_dump())
        logger.info("🔍 Étape 7/7: Validation narrative complète...")
        await self._validate_episode(episode)
        logger.info("✅ Validation réussie")

        logger.info("🌟 Bonus: histoire Twilight Zone...")
        try:
            episode.twilight_zone_story = await self._generate_twilight_zone_story(scenario, arc, episode)
        except StructuredOutputError as exc:  # bonus : n'invalide pas l'épisode
            logger.warning("⚠️  Histoire Twilight Zone non générée: %s", exc)
        else:
            story = episode.twilight_zone_story
            logger.info("✅ Histoire Twilight Zone générée: %s", story.title)
            if self.exporter:
                self.exporter.export_twilight_zone_story(story)
                self.exporter.export_partial_json(episode)
        return episode

    async def _define_narrative_arc(self, scenario: str) -> ArcOutput:
        prompt = (
            "Utilise le Skill narrative-conductor pour définir l'arc narratif complet pour cet épisode "
            f"NEW TEMPS X.\n\nScénario: {scenario}\n\n"
            "Le Skill contient toutes les instructions nécessaires. Réponds selon le schéma fourni."
        )
        return await self._run_step(prompt, ArcOutput)

    async def _generate_acts_1_3(self, scenario: str, arc: ArcOutput) -> ActsOneToThreeOutput:
        t = arc.themes
        prompt = (
            "Utilise le Skill science-editor pour générer les Actes I, II et III pour cet épisode NEW TEMPS X.\n\n"
            f"Scénario: {scenario}\n"
            f"Arc narratif: {arc.narrative_arc}\n"
            f"Thèmes:\n- Acte I (Le Signal): {t.acte_1}\n- Acte II (Le Décryptage): {t.acte_2}\n"
            f"- Acte III (La Tension): {t.acte_3}\n"
            f"{self._retry_warning()}\n\n"
            "Le Skill contient toutes les instructions nécessaires. Réponds selon le schéma fourni."
        )
        return await self._run_step(prompt, ActsOneToThreeOutput)

    async def _validate_episode(self, episode: Episode) -> None:
        prompt = (
            "Utilise le Skill narrative-validator pour valider cet épisode complet NEW TEMPS X.\n\n"
            f"Épisode:\n{episode.model_dump_json(indent=2)}\n\n"
            "Le Skill contient toutes les instructions nécessaires. Réponds selon le schéma fourni."
        )
        result = await self._run_step(prompt, ValidationOutput)
        if not result.validated:
            details = ", ".join(result.issues) if result.issues else "Aucun détail"
            logger.error("❌ Validation échouée: %s (%s)", result.message, details)
            raise EpisodeRejectedError(f"Épisode rejeté: {result.message}\nProblèmes: {details}")

    async def _generate_twilight_zone_story(
        self, scenario: str, arc: ArcOutput, episode: Episode
    ) -> TwilightZoneStory:
        prompt = (
            "Utilise le Skill twilight-zone-writer pour générer une nouvelle complète (novelette, "
            "8000-15000 mots) EN FRANÇAIS inspirée par cet épisode NEW TEMPS X.\n\n"
            f"- Scénario: {scenario}\n- Titre: {episode.episode_title}\n"
            f"- Arc narratif: {arc.narrative_arc}\n- Actes:\n{self._previous_titles(episode)}\n\n"
            "Le Skill contient toutes les instructions nécessaires. Réponds selon le schéma fourni."
        )
        return await self._run_step(prompt, TwilightZoneStory)

    async def generate_twilight_zone_story_only(self, scenario: str) -> Optional[TwilightZoneStory]:
        """Génère uniquement une histoire Twilight Zone (sans épisode)."""
        logger.info("🌟 Génération d'une histoire Twilight Zone standalone...")
        self._session_id = None
        prompt = (
            "Utilise le Skill twilight-zone-writer pour générer une nouvelle complète (novelette, "
            f"8000-15000 mots) EN FRANÇAIS inspirée par ce scénario.\n\nScénario: {scenario}\n\n"
            "Le Skill contient toutes les instructions nécessaires. Réponds selon le schéma fourni."
        )
        return await self._run_step(prompt, TwilightZoneStory)

