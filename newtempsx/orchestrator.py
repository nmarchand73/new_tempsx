"""Orchestrateur principal pour générer un épisode NEW TEMPS X."""

import json
import logging
import re
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)

from .models import Episode, Act, Reference, TwilightZoneStory

if TYPE_CHECKING:
    from .exporters import EpisodeExporter

# Configuration du logger
logger = logging.getLogger(__name__)


class EpisodeOrchestrator:
    """Orchestre la génération d'un épisode complet.
    
    Utilise Claude Agents SDK avec Skills pour générer un épisode
    suivant la structure narrative stricte en 7 actes.
    """
    
    def __init__(self, project_root: Optional[Path] = None, exporter: Optional["EpisodeExporter"] = None, debug: bool = False):
        """Initialise l'orchestrateur.
        
        Args:
            project_root: Racine du projet (pour charger les Skills). 
                          Si None, utilise le répertoire courant.
            exporter: Exporteur pour export progressif (optionnel)
            debug: Active les logs de debug du SDK Claude Agents (défaut: False)
        """
        if project_root is None:
            project_root = Path.cwd()
        self.project_root = Path(project_root)
        self.exporter = exporter
        self._is_retry = False  # Flag pour indiquer si c'est un retry
        
        # Configuration Claude Agents SDK selon les best practices
        # Référence: https://platform.claude.com/docs/en/agent-sdk/overview
        # Note: Le SDK charge automatiquement les Skills depuis .claude/skills/
        # via setting_sources=["project"]. Le code execution tool est géré automatiquement
        # par le SDK pour les Skills (contrairement à l'API Messages qui nécessite
        # un paramètre container explicite).
        # 
        # Outils activés:
        # - "Skill": Permet aux Skills d'être invoqués
        # - "Read": Permet de lire des fichiers (pour les Skills)
        # - "Browser": Permet la navigation web et la recherche (pour enrichir le contenu)
        self.options = ClaudeAgentOptions(
            setting_sources=["project"],  # Charge les Skills depuis .claude/skills/
            allowed_tools=["Skill", "Read", "Browser"],  # Active les Skills, Read et Browser pour recherche web
            cwd=str(self.project_root),
            debug_stderr=debug,  # Active les logs de debug du SDK sur stderr
        )
    
    async def generate_episode(self, scenario: str) -> Episode:
        """Génère un épisode complet à partir d'un scénario.
        
        Les Skills sont invoqués automatiquement par Claude selon leur description.
        On utilise des prompts qui guident Claude vers l'utilisation des bons Skills.
        
        Args:
            scenario: Texte du scénario d'entrée
            
        Returns:
            Episode complet avec les 7 actes
            
        Raises:
            ValueError: Si la génération ou la validation échoue après retry
        """
        max_retries = 1  # Un seul retry
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                # Réinitialiser le flag de retry au début de chaque tentative
                self._is_retry = (retry_count > 0)
                
                if retry_count > 0:
                    logger.warning(f"🔄 Tentative de régénération {retry_count}/{max_retries}...")
                    logger.warning("⚠️  L'épisode précédent a été rejeté. Régénération avec instructions renforcées.")
                    logger.warning("⚠️  IMPORTANT: Utilise uniquement des URLs réelles et vérifiables pour les références.")
                    logger.warning("⚠️  Utilise l'outil Browser pour vérifier chaque URL avant de l'inclure.")
                
                logger.info("🎬 Début de la génération d'un épisode NEW TEMPS X")
                logger.info(f"📝 Scénario: {scenario[:100]}...")
                
                episode = await self._generate_episode_internal(scenario, is_retry=(retry_count > 0))
                return episode
                
            except ValueError as e:
                error_msg = str(e)
                # Vérifier si c'est une erreur de validation
                if "Épisode rejeté" in error_msg or "Validation échouée" in error_msg:
                    if retry_count < max_retries:
                        retry_count += 1
                        logger.warning(f"❌ Validation échouée, retry {retry_count}/{max_retries}")
                        logger.warning(f"   Raison: {error_msg[:200]}...")
                        continue
                    else:
                        logger.error(f"❌ Échec après {max_retries} tentative(s) de régénération")
                        raise
                else:
                    # Autre erreur, ne pas retry
                    raise
        
        # Ne devrait jamais arriver ici
        raise ValueError("Erreur inattendue lors de la génération")
    
    def _get_retry_warning(self) -> str:
        """Retourne un message d'avertissement si c'est un retry."""
        if hasattr(self, '_is_retry') and self._is_retry:
            return "\n\n⚠️ ATTENTION - RÉGÉNÉRATION: L'épisode précédent a été rejeté car les références contenaient des URLs d'exemple non fonctionnelles. Utilise UNIQUEMENT des URLs réelles et vérifiables. Utilise l'outil Browser pour vérifier chaque URL avant de l'inclure dans les références."
        return ""
    
    async def _generate_episode_internal(self, scenario: str, is_retry: bool = False) -> Episode:
        """Génère un épisode complet (méthode interne appelée par generate_episode avec retry).
        
        Args:
            scenario: Texte du scénario d'entrée
            is_retry: True si c'est un retry après un échec de validation
            
        Returns:
            Episode complet avec les 7 actes
            
        Raises:
            ValueError: Si la génération ou la validation échoue
        """
        async with ClaudeSDKClient(options=self.options) as client:
            # Étape 1: Définir l'arc narratif
            logger.info("📐 Étape 1/7: Définition de l'arc narratif...")
            narrative_arc = await self._define_narrative_arc(client, scenario)
            logger.info(f"✅ Arc narratif défini: {narrative_arc.get('episode_title', 'Sans titre')}")
            
            # Créer un épisode partiel pour l'export progressif
            episode_title = narrative_arc.get("episode_title", "Épisode NEW TEMPS X")
            partial_episode = Episode(
                episode_title=episode_title,
                scenario_input=scenario,
                narrative_arc=narrative_arc.get("narrative_arc", ""),
                acts={}
            )
            # Exporter l'arc narratif
            if self.exporter:
                self.exporter.export_partial_json(partial_episode)
            
            # Étape 2: Générer Actes I-III
            logger.info("🔬 Étape 2/7: Génération des Actes I, II et III (Science Editor)...")
            acts_1_3 = await self._generate_acts_1_3(client, scenario, narrative_arc)
            logger.info("✅ Actes I-III générés")
            logger.debug(f"  - Acte I: {acts_1_3['acte_1'].title}")
            logger.debug(f"  - Acte II: {acts_1_3['acte_2'].title}")
            logger.debug(f"  - Acte III: {acts_1_3['acte_3'].title}")
            
            # Exporter les actes I-III progressivement
            if self.exporter:
                partial_episode.acts.update(acts_1_3)
                act_names = {
                    "acte_1": "01_le_signal",
                    "acte_2": "02_le_decryptage",
                    "acte_3": "03_la_tension",
                }
                for act_key, act in acts_1_3.items():
                    self.exporter.export_act_markdown(act_key, act, act_names[act_key])
                self.exporter.export_partial_json(partial_episode)
            
            # Étape 3: Générer Acte IV
            logger.info("✍️  Étape 3/7: Génération de l'Acte IV (Fiction Writer)...")
            act_4 = await self._generate_act_4(client, scenario, narrative_arc, acts_1_3)
            logger.info(f"✅ Acte IV généré: {act_4.title}")
            
            # Exporter l'acte IV
            if self.exporter:
                partial_episode.acts["acte_4"] = act_4
                self.exporter.export_act_markdown("acte_4", act_4, "04_la_fiction")
                self.exporter.export_partial_json(partial_episode)
            
            # Étape 4: Générer Acte V
            logger.info("💭 Étape 4/7: Génération de l'Acte V (Dialogue/Reflect)...")
            act_5 = await self._generate_act_5(client, scenario, narrative_arc, acts_1_3, act_4)
            logger.info(f"✅ Acte V généré: {act_5.title}")
            
            # Exporter l'acte V
            if self.exporter:
                partial_episode.acts["acte_5"] = act_5
                self.exporter.export_act_markdown("acte_5", act_5, "05_le_dialogue")
                self.exporter.export_partial_json(partial_episode)
            
            # Étape 5: Générer Acte VI
            logger.info("📚 Étape 5/7: Génération de l'Acte VI (Archivist)...")
            act_6 = await self._generate_act_6(client, scenario, narrative_arc, acts_1_3, act_4, act_5)
            logger.info(f"✅ Acte VI généré: {act_6.title}")
            
            # Exporter l'acte VI
            if self.exporter:
                partial_episode.acts["acte_6"] = act_6
                self.exporter.export_act_markdown("acte_6", act_6, "06_la_memoire")
                self.exporter.export_partial_json(partial_episode)
            
            # Étape 6: Générer Acte VII
            logger.info("🎯 Étape 6/7: Génération de l'Acte VII (Audience)...")
            act_7 = await self._generate_act_7(client, scenario, narrative_arc, acts_1_3, act_4, act_5, act_6)
            logger.info(f"✅ Acte VII généré: {act_7.title}")
            
            # Exporter l'acte VII
            if self.exporter:
                partial_episode.acts["acte_7"] = act_7
                self.exporter.export_act_markdown("acte_7", act_7, "07_la_transmission")
                self.exporter.export_partial_json(partial_episode)
            
            # Construire l'épisode
            logger.info("📦 Assemblage de l'épisode complet...")
            episode_title = narrative_arc.get("episode_title", "Épisode NEW TEMPS X")
            arc_description = narrative_arc.get("narrative_arc", "")
            
            episode = Episode(
                episode_title=episode_title,
                scenario_input=scenario,
                narrative_arc=arc_description,
                acts={
                    "acte_1": acts_1_3["acte_1"],
                    "acte_2": acts_1_3["acte_2"],
                    "acte_3": acts_1_3["acte_3"],
                    "acte_4": act_4,
                    "acte_5": act_5,
                    "acte_6": act_6,
                    "acte_7": act_7,
                }
            )
            logger.info(f"✅ Épisode assemblé: {episode_title}")
            
            # Étape 7: Validation complète
            logger.info("🔍 Étape 7/7: Validation narrative complète...")
            await self._validate_episode(client, episode)
            logger.info("✅ Validation réussie - Épisode prêt")
            
            # Bonus: Générer l'histoire Twilight Zone
            logger.info("🌟 Bonus: Génération de l'histoire Twilight Zone...")
            twilight_story = await self._generate_twilight_zone_story(client, scenario, narrative_arc, episode)
            if twilight_story:
                episode.twilight_zone_story = twilight_story
                logger.info(f"✅ Histoire Twilight Zone générée: {twilight_story.title}")
                # Exporter l'histoire bonus
                if self.exporter:
                    self.exporter.export_twilight_zone_story(twilight_story)
                    self.exporter.export_partial_json(episode)
            else:
                logger.warning("⚠️  Histoire Twilight Zone non générée")
            
            return episode
    
    async def _define_narrative_arc(self, client: ClaudeSDKClient, scenario: str) -> dict:
        """Définit l'arc narratif.
        
        Le Skill "narrative-conductor" sera invoqué automatiquement par Claude
        car le prompt correspond à sa description.
        """
        logger.debug("Invocation du Skill 'narrative-conductor' pour définir l'arc narratif")
        # Schéma JSON pour structured output
        arc_schema = {
            "type": "object",
            "properties": {
                "episode_title": {"type": "string"},
                "narrative_arc": {"type": "string"},
                "themes": {
                    "type": "object",
                    "properties": {
                        "acte_1": {"type": "string"},
                        "acte_2": {"type": "string"},
                        "acte_3": {"type": "string"},
                        "acte_4": {"type": "string"},
                        "acte_5": {"type": "string"},
                        "acte_6": {"type": "string"},
                        "acte_7": {"type": "string"},
                    },
                    "required": ["acte_1", "acte_2", "acte_3", "acte_4", "acte_5", "acte_6", "acte_7"],
                    "additionalProperties": False,
                },
            },
            "required": ["episode_title", "narrative_arc", "themes"],
            "additionalProperties": False,
        }
        
        prompt = f"""Utilise le Skill narrative-conductor pour définir l'arc narratif complet pour cet épisode NEW TEMPS X.

Scénario: {scenario}

Le Skill contient toutes les instructions nécessaires. Réponds en JSON selon le schéma fourni."""
        
        # Utiliser le client existant pour maintenir le contexte
        await client.query(prompt)
        logger.debug("Réponse reçue, extraction du texte...")
        response_text = await self._extract_text_response(client)
        logger.debug("Parsing de la réponse JSON...")
        result = self._parse_json_response(response_text)
        logger.debug("Arc narratif parsé avec succès")
        return result
    
    async def _generate_acts_1_3(self, client: ClaudeSDKClient, scenario: str, narrative_arc: dict) -> dict:
        """Génère les Actes I, II et III.
        
        Le Skill "science-editor" sera invoqué automatiquement.
        """
        logger.debug("Invocation du Skill 'science-editor' pour générer les Actes I-III")
        themes = narrative_arc.get("themes", {})
        
        acts_schema = {
            "type": "object",
            "properties": {
                "acte_1": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "content": {"type": "string"},
                        "image_prompts": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Liste des prompts DALL-E pour générer des images (1-3 prompts recommandés)"
                        }
                    },
                    "required": ["title", "content"],
                    "additionalProperties": False,
                },
                "acte_2": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "content": {"type": "string"},
                        "image_prompts": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Liste des prompts DALL-E pour générer des images (1-3 prompts recommandés)"
                        }
                    },
                    "required": ["title", "content"],
                    "additionalProperties": False,
                },
                "acte_3": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "content": {"type": "string"},
                        "image_prompts": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Liste des prompts DALL-E pour générer des images (1-3 prompts recommandés)"
                        }
                    },
                    "required": ["title", "content"],
                    "additionalProperties": False,
                },
            },
            "required": ["acte_1", "acte_2", "acte_3"],
            "additionalProperties": False,
        }
        
        prompt = f"""Utilise le Skill science-editor pour générer les Actes I, II et III pour cet épisode NEW TEMPS X.

Scénario: {scenario}
Arc narratif: {narrative_arc.get('narrative_arc', '')}
Thèmes:
- Acte I (Le Signal): {themes.get('acte_1', '')}
- Acte II (Le Décryptage): {themes.get('acte_2', '')}
- Acte III (La Tension): {themes.get('acte_3', '')}
{self._get_retry_warning()}

Le Skill contient toutes les instructions nécessaires. Réponds en JSON selon le schéma fourni."""
        
        await client.query(prompt)
        logger.debug("Réponse reçue pour les Actes I-III, extraction...")
        response_text = await self._extract_text_response(client)
        acts_data = self._parse_json_response(response_text)
        logger.debug("Actes I-III parsés avec succès")
        
        # Assigner les narrateurs de manière alternée (style Temps X)
        # Narrateur 1: Actes I, III, V, VII (impairs)
        # Narrateur 2: Actes II, IV, VI (pairs)
        # Convertir les références en objets Reference
        def process_act_data(act_data, narrator):
            act_dict = {"narrator": narrator}
            act_dict.update(act_data)
            # Convertir les références si présentes
            if "references" in act_dict and act_dict["references"]:
                act_dict["references"] = [Reference(**ref) for ref in act_dict["references"]]
            else:
                act_dict["references"] = []
            # S'assurer que image_prompts est présent (peut être vide)
            if "image_prompts" not in act_dict:
                act_dict["image_prompts"] = []
            return Act(**act_dict)
        
        return {
            "acte_1": process_act_data(acts_data["acte_1"], "narrator_1"),
            "acte_2": process_act_data(acts_data["acte_2"], "narrator_2"),
            "acte_3": process_act_data(acts_data["acte_3"], "narrator_1"),
        }
    
    async def _generate_act_4(self, client: ClaudeSDKClient, scenario: str, narrative_arc: dict, acts_1_3: dict) -> Act:
        """Génère l'Acte IV.
        
        Le Skill "fiction-writer" sera invoqué automatiquement.
        """
        logger.debug("Invocation du Skill 'fiction-writer' pour générer l'Acte IV")
        themes = narrative_arc.get("themes", {})
        
        act_schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "references": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "url": {"type": "string"},
                            "description": {"type": "string"}
                        },
                        "required": ["title", "url"]
                    }
                },
                "image_prompts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Liste des prompts DALL-E pour générer des images (1-3 prompts recommandés)"
                }
            },
            "required": ["title", "content"],
            "additionalProperties": False,
        }
        
        prompt = f"""Utilise le Skill fiction-writer pour générer l'Acte IV (La Fiction) pour cet épisode NEW TEMPS X.

Scénario: {scenario}
Arc narratif: {narrative_arc.get('narrative_arc', '')}
Thème Acte IV: {themes.get('acte_4', '')}
Actes précédents:
- Acte I: {acts_1_3['acte_1'].title}
- Acte II: {acts_1_3['acte_2'].title}
- Acte III: {acts_1_3['acte_3'].title}
{self._get_retry_warning()}

Le Skill contient toutes les instructions nécessaires. Réponds en JSON selon le schéma fourni."""
        
        await client.query(prompt)
        logger.debug("Réponse reçue pour l'Acte IV, extraction...")
        response_text = await self._extract_text_response(client)
        parsed_json = self._parse_json_response(response_text)
        act_data = self._extract_act_from_json(parsed_json, "acte_4")
        # Acte IV = narrateur 2 (pair)
        act_data["narrator"] = "narrator_2"
        # Convertir les références si présentes
        if "references" in act_data and act_data["references"]:
            act_data["references"] = [Reference(**ref) for ref in act_data["references"]]
        else:
            act_data["references"] = []
        # S'assurer que image_prompts est présent (peut être vide)
        if "image_prompts" not in act_data:
            act_data["image_prompts"] = []
        logger.debug(f"Acte IV parsé: {act_data.get('title', 'Sans titre')}")
        return Act(**act_data)
    
    async def _generate_act_5(self, client: ClaudeSDKClient, scenario: str, narrative_arc: dict, 
                              acts_1_3: dict, act_4: Act) -> Act:
        """Génère l'Acte V (Dialogue/Reflect).
        
        Le Skill "dialogue" sera invoqué automatiquement.
        """
        logger.debug("Invocation du Skill 'dialogue' pour générer l'Acte V")
        themes = narrative_arc.get("themes", {})
        
        act_schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "references": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "url": {"type": "string"},
                            "description": {"type": "string"}
                        },
                        "required": ["title", "url"]
                    }
                },
                "image_prompts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Liste des prompts DALL-E pour générer des images (1-3 prompts recommandés)"
                }
            },
            "required": ["title", "content"],
            "additionalProperties": False,
        }
        
        prompt = f"""Utilise le Skill dialogue pour générer l'Acte V (Le Dialogue) pour cet épisode NEW TEMPS X.

Scénario: {scenario}
Arc narratif: {narrative_arc.get('narrative_arc', '')}
Thème Acte V: {themes.get('acte_5', '')}
Actes précédents:
- Acte I: {acts_1_3['acte_1'].title}
- Acte II: {acts_1_3['acte_2'].title}
- Acte III: {acts_1_3['acte_3'].title}
- Acte IV: {act_4.title}
{self._get_retry_warning()}

Le Skill contient toutes les instructions nécessaires. Réponds en JSON selon le schéma fourni."""
        
        await client.query(prompt)
        logger.debug("Réponse reçue pour l'Acte V, extraction...")
        response_text = await self._extract_text_response(client)
        parsed_json = self._parse_json_response(response_text)
        act_data = self._extract_act_from_json(parsed_json, "acte_5")
        # Acte V = narrateur 1 (impair)
        act_data["narrator"] = "narrator_1"
        # Convertir les références si présentes
        if "references" in act_data and act_data["references"]:
            act_data["references"] = [Reference(**ref) for ref in act_data["references"]]
        else:
            act_data["references"] = []
        # S'assurer que image_prompts est présent (peut être vide)
        if "image_prompts" not in act_data:
            act_data["image_prompts"] = []
        logger.debug(f"Acte V parsé: {act_data.get('title', 'Sans titre')}")
        return Act(**act_data)
    
    async def _generate_act_6(self, client: ClaudeSDKClient, scenario: str, narrative_arc: dict,
                              acts_1_3: dict, act_4: Act, act_5: Act) -> Act:
        """Génère l'Acte VI.
        
        Le Skill "archivist" sera invoqué automatiquement.
        """
        logger.debug("Invocation du Skill 'archivist' pour générer l'Acte VI")
        themes = narrative_arc.get("themes", {})
        
        act_schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "references": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "url": {"type": "string"},
                            "description": {"type": "string"}
                        },
                        "required": ["title", "url"]
                    }
                },
                "image_prompts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Liste des prompts DALL-E pour générer des images (1-3 prompts recommandés)"
                }
            },
            "required": ["title", "content"],
            "additionalProperties": False,
        }
        
        prompt = f"""Utilise le Skill archivist pour générer l'Acte VI (La Mémoire) pour cet épisode NEW TEMPS X.

Scénario: {scenario}
Arc narratif: {narrative_arc.get('narrative_arc', '')}
Thème Acte VI: {themes.get('acte_6', '')}
Actes précédents:
- Actes I-III: {acts_1_3['acte_1'].title}, {acts_1_3['acte_2'].title}, {acts_1_3['acte_3'].title}
- Acte IV: {act_4.title}
- Acte V: {act_5.title}
{self._get_retry_warning()}

Le Skill contient toutes les instructions nécessaires. Réponds en JSON selon le schéma fourni."""
        
        await client.query(prompt)
        logger.debug("Réponse reçue pour l'Acte VI, extraction...")
        response_text = await self._extract_text_response(client)
        parsed_json = self._parse_json_response(response_text)
        act_data = self._extract_act_from_json(parsed_json, "acte_6")
        # Acte VI = narrateur 2 (pair)
        act_data["narrator"] = "narrator_2"
        # Convertir les références si présentes
        if "references" in act_data and act_data["references"]:
            act_data["references"] = [Reference(**ref) for ref in act_data["references"]]
        else:
            act_data["references"] = []
        # S'assurer que image_prompts est présent (peut être vide)
        if "image_prompts" not in act_data:
            act_data["image_prompts"] = []
        logger.debug(f"Acte VI parsé: {act_data.get('title', 'Sans titre')}")
        return Act(**act_data)
    
    async def _generate_act_7(self, client: ClaudeSDKClient, scenario: str, narrative_arc: dict,
                              acts_1_3: dict, act_4: Act, act_5: Act, act_6: Act) -> Act:
        """Génère l'Acte VII.
        
        Le Skill "audience" sera invoqué automatiquement.
        """
        logger.debug("Invocation du Skill 'audience' pour générer l'Acte VII")
        themes = narrative_arc.get("themes", {})
        
        act_schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "references": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "url": {"type": "string"},
                            "description": {"type": "string"}
                        },
                        "required": ["title", "url"]
                    }
                },
                "image_prompts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Liste des prompts DALL-E pour générer des images (1-3 prompts recommandés)"
                }
            },
            "required": ["title", "content"],
            "additionalProperties": False,
        }
        
        prompt = f"""Utilise le Skill audience pour générer l'Acte VII (La Transmission) pour cet épisode NEW TEMPS X.

Scénario: {scenario}
Arc narratif: {narrative_arc.get('narrative_arc', '')}
Thème Acte VII: {themes.get('acte_7', '')}
Actes précédents:
- Acte I: {acts_1_3['acte_1'].title}
- Acte II: {acts_1_3['acte_2'].title}
- Acte III: {acts_1_3['acte_3'].title}
- Acte IV: {act_4.title}
- Acte V: {act_5.title}
- Acte VI: {act_6.title}
{self._get_retry_warning()}

Le Skill contient toutes les instructions nécessaires. Réponds en JSON selon le schéma fourni."""
        
        await client.query(prompt)
        logger.debug("Réponse reçue pour l'Acte VII, extraction...")
        response_text = await self._extract_text_response(client)
        parsed_json = self._parse_json_response(response_text)
        act_data = self._extract_act_from_json(parsed_json, "acte_7")
        # Acte VII = narrateur 1 (impair)
        act_data["narrator"] = "narrator_1"
        # Convertir les références si présentes
        if "references" in act_data and act_data["references"]:
            act_data["references"] = [Reference(**ref) for ref in act_data["references"]]
        else:
            act_data["references"] = []
        # S'assurer que image_prompts est présent (peut être vide)
        if "image_prompts" not in act_data:
            act_data["image_prompts"] = []
        logger.debug(f"Acte VII parsé: {act_data.get('title', 'Sans titre')}")
        return Act(**act_data)
    
    async def _validate_episode(self, client: ClaudeSDKClient, episode: Episode):
        """Valide l'épisode complet.
        
        Le Skill "narrative-validator" sera invoqué automatiquement.
        """
        logger.debug("Invocation du Skill 'narrative-validator' pour valider l'épisode")
        episode_json = episode.model_dump_json(indent=2)
        
        validation_schema = {
            "type": "object",
            "properties": {
                "validated": {"type": "boolean"},
                "message": {"type": "string"},
                "issues": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["validated", "message"],
            "additionalProperties": False,
        }
        
        prompt = f"""Utilise le Skill narrative-validator pour valider cet épisode complet NEW TEMPS X.

Épisode:
{episode_json}

Le Skill contient toutes les instructions nécessaires. Réponds en JSON selon le schéma fourni."""
        
        await client.query(prompt)
        logger.debug("Réponse de validation reçue, extraction...")
        try:
            response_text = await self._extract_text_response(client)
            if not response_text or not response_text.strip():
                logger.error("❌ Réponse vide lors de la validation")
                logger.warning("⚠️  La validation a échoué car aucune réponse n'a été reçue")
                raise ValueError("Réponse vide lors de la validation - le Skill narrative-validator n'a pas répondu")
            
            validation_result = self._parse_json_response(response_text)
        except ValueError as e:
            if "Pas de JSON trouvé" in str(e) or "Réponse vide" in str(e):
                logger.error(f"❌ Erreur lors de la validation: {e}")
                logger.warning("⚠️  Le Skill narrative-validator n'a peut-être pas retourné de JSON valide")
                logger.warning("⚠️  L'épisode sera considéré comme non validé")
                raise
            raise
        
        if not validation_result.get("validated", False):
            issues = validation_result.get("issues", [])
            message = validation_result.get("message", "Validation échouée")
            logger.error(f"❌ Validation échouée: {message}")
            if issues:
                logger.error(f"Problèmes détectés: {', '.join(issues)}")
            raise ValueError(f"Épisode rejeté: {message}\nProblèmes: {', '.join(issues) if issues else 'Aucun détail'}")
        
        logger.debug("Validation réussie")
    
    async def _generate_twilight_zone_story(self, client: ClaudeSDKClient, scenario: str, 
                                            narrative_arc: dict, episode: Episode) -> Optional[TwilightZoneStory]:
        """Génère une histoire complète style Twilight Zone.
        
        Le Skill "twilight-zone-writer" sera invoqué automatiquement.
        """
        logger.debug("Invocation du Skill 'twilight-zone-writer' pour générer l'histoire bonus")
        
        story_schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "story": {"type": "string"},
                "theme": {"type": "string"},
                "image_prompts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Liste des prompts DALL-E pour générer des images (2-4 prompts recommandés)"
                }
            },
            "required": ["title", "story", "theme"],
            "additionalProperties": False,
        }
        
        # Résumer les actes pour l'inspiration
        acts_summary = "\n".join([
            f"- {act_key}: {act.title}" 
            for act_key, act in episode.acts.items()
        ])
        
        prompt = f"""Utilise le Skill twilight-zone-writer pour générer une nouvelle complète (novelette, 8000-15000 mots) EN FRANÇAIS inspirée par cet épisode NEW TEMPS X.

Contexte de l'épisode:
- Scénario: {scenario}
- Titre: {episode.episode_title}
- Arc narratif: {narrative_arc.get('narrative_arc', '')}
- Actes: {acts_summary}

Le Skill contient toutes les instructions nécessaires. Réponds en JSON selon le schéma fourni."""
        
        await client.query(prompt)
        logger.debug("Réponse reçue pour l'histoire Twilight Zone, extraction...")
        response_text = await self._extract_text_response(client)
        story_data = self._parse_json_response(response_text)
        logger.debug(f"Histoire Twilight Zone parsée: {story_data.get('title', 'Sans titre')}")
        return TwilightZoneStory(**story_data)
    
    async def generate_twilight_zone_story_only(self, scenario: str) -> Optional[TwilightZoneStory]:
        """Génère uniquement une histoire Twilight Zone sans générer l'épisode complet.
        
        Args:
            scenario: Texte du scénario d'entrée
            
        Returns:
            Histoire Twilight Zone ou None en cas d'erreur
        """
        logger.info("🌟 Génération d'une histoire Twilight Zone standalone...")
        logger.info(f"📝 Scénario: {scenario[:100]}...")
        
        async with ClaudeSDKClient(options=self.options) as client:
            # Générer directement l'histoire sans arc narratif ni actes
            story = await self._generate_twilight_zone_story_standalone(client, scenario)
            return story
    
    async def _generate_twilight_zone_story_standalone(self, client: ClaudeSDKClient, scenario: str) -> Optional[TwilightZoneStory]:
        """Génère une histoire Twilight Zone standalone (sans contexte d'épisode).
        
        Le Skill "twilight-zone-writer" sera invoqué automatiquement.
        """
        logger.debug("Invocation du Skill 'twilight-zone-writer' pour générer l'histoire standalone")
        
        story_schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "story": {"type": "string"},
                "theme": {"type": "string"},
                "image_prompts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Liste des prompts DALL-E pour générer des images (2-4 prompts recommandés)"
                }
            },
            "required": ["title", "story", "theme"],
            "additionalProperties": False,
        }
        
        prompt = f"""Utilise le Skill twilight-zone-writer pour générer une nouvelle complète (novelette, 8000-15000 mots) EN FRANÇAIS inspirée par ce scénario.

Scénario: {scenario}

Le Skill contient toutes les instructions nécessaires. Réponds en JSON selon le schéma fourni."""
        
        await client.query(prompt)
        logger.debug("Réponse reçue pour l'histoire Twilight Zone standalone, extraction...")
        response_text = await self._extract_text_response(client)
        story_data = self._parse_json_response(response_text)
        logger.debug(f"Histoire Twilight Zone standalone parsée: {story_data.get('title', 'Sans titre')}")
        return TwilightZoneStory(**story_data)
    
    async def _extract_text_response(self, client: ClaudeSDKClient) -> str:
        """Extrait le texte de la réponse de Claude.
        
        Récupère tous les TextBlock et ToolResultBlock pour obtenir la réponse complète.
        Les ToolUseBlock sont ignorés car ils représentent des appels d'outils, pas des réponses.
        """
        response_parts = []
        message_count = 0
        block_count = 0
        text_block_count = 0
        tool_result_count = 0
        tool_use_count = 0
        
        try:
            async for message in client.receive_response():
                message_count += 1
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        block_count += 1
                        if isinstance(block, TextBlock):
                            text_block_count += 1
                            response_parts.append(block.text)
                            # Afficher un aperçu du contenu (premiers 200 caractères)
                            preview = block.text[:200].replace('\n', ' ')
                            if len(block.text) > 200:
                                preview += "..."
                            logger.debug(f"TextBlock reçu ({len(block.text)} caractères): {preview}")
                        elif isinstance(block, ToolResultBlock):
                            tool_result_count += 1
                            # Vérifier si c'est une erreur
                            if hasattr(block, 'is_error') and block.is_error:
                                logger.warning(f"⚠️  ToolResultBlock avec erreur ignoré")
                                continue
                            
                            # Les ToolResultBlock peuvent contenir du JSON dans leur contenu
                            if hasattr(block, 'content') and block.content:
                                if isinstance(block.content, str):
                                    response_parts.append(block.content)
                                    logger.debug(f"ToolResultBlock texte reçu ({len(block.content)} caractères)")
                                elif isinstance(block.content, (dict, list)):
                                    # Si c'est un dict ou list, le convertir en JSON
                                    try:
                                        json_str = json.dumps(block.content, ensure_ascii=False, indent=2)
                                        response_parts.append(json_str)
                                        logger.debug(f"ToolResultBlock JSON reçu ({len(json_str)} caractères)")
                                    except Exception as e:
                                        logger.debug(f"Impossible de convertir ToolResultBlock en JSON: {e}")
                                else:
                                    # Autre type, convertir en string
                                    response_parts.append(str(block.content))
                                    logger.debug(f"ToolResultBlock autre type converti en string ({len(str(block.content))} caractères)")
                            else:
                                logger.debug(f"ToolResultBlock sans contenu ou contenu vide")
                        elif isinstance(block, ToolUseBlock):
                            tool_use_count += 1
                            # Afficher des détails sur l'appel d'outil
                            tool_name = "inconnu"
                            tool_input_preview = ""
                            
                            if hasattr(block, 'name'):
                                tool_name = block.name
                            elif hasattr(block, 'tool_name'):
                                tool_name = block.tool_name
                            
                            if hasattr(block, 'input'):
                                input_str = str(block.input)
                                tool_input_preview = input_str[:150].replace('\n', ' ')
                                if len(input_str) > 150:
                                    tool_input_preview += "..."
                            
                            logger.debug(f"🔧 ToolUseBlock: appel de l'outil '{tool_name}' {f'avec: {tool_input_preview}' if tool_input_preview else ''}")
                        else:
                            # Autres types de blocs
                            block_type = type(block).__name__
                            logger.debug(f"Bloc ignoré: {block_type}")
                else:
                    # Ne pas logger les messages système/user en mode debug pour réduire le bruit
                    # Ces messages font partie du flux normal de communication
                    pass
            
            response_text = "\n".join(response_parts)
            logger.debug(
                f"Réponse extraite: {len(response_text)} caractères, "
                f"{message_count} messages, {block_count} blocs "
                f"(TextBlock: {text_block_count}, ToolResult: {tool_result_count}, ToolUse: {tool_use_count})"
            )
            
            if not response_text.strip():
                logger.warning("⚠️  Réponse vide reçue de Claude")
                logger.warning(
                    f"Détails: {message_count} messages, {block_count} blocs, "
                    f"TextBlock: {text_block_count}, ToolResult: {tool_result_count}, ToolUse: {tool_use_count}"
                )
            
            return response_text
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'extraction de la réponse: {e}")
            logger.debug(
                f"Messages reçus avant l'erreur: {message_count}, Blocs: {block_count}, "
                f"TextBlock: {text_block_count}, ToolResult: {tool_result_count}"
            )
            raise
    
    def _parse_json_response(self, response_text: str) -> dict:
        """Parse une réponse JSON, même si elle contient du markdown."""
        if not response_text or not response_text.strip():
            logger.error("Réponse vide reçue")
            raise ValueError("Réponse vide - pas de JSON trouvé")
        
        try:
            # Essayer de parser directement si c'est du JSON pur
            try:
                parsed = json.loads(response_text.strip())
                logger.debug("JSON parsé directement (réponse pure JSON)")
                return parsed
            except json.JSONDecodeError:
                pass
            
            # Chercher le JSON dans un bloc de code markdown (```json ... ```)
            json_block_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
            json_block_match = re.search(json_block_pattern, response_text, re.DOTALL)
            if json_block_match:
                json_str = json_block_match.group(1)
                parsed = json.loads(json_str)
                logger.debug("JSON extrait d'un bloc de code markdown")
                return parsed
            
            # Chercher le JSON dans la réponse (entre { et })
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                # Essayer de trouver le JSON complet en comptant les accolades
                brace_count = 0
                actual_end = json_start
                for i, char in enumerate(response_text[json_start:], start=json_start):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            actual_end = i + 1
                            break
                
                if actual_end > json_start:
                    json_str = response_text[json_start:actual_end]
                    parsed = json.loads(json_str)
                    logger.debug(f"JSON parsé avec succès ({len(json_str)} caractères)")
                    return parsed
            
            # Si on arrive ici, pas de JSON trouvé
            logger.error("Aucun JSON trouvé dans la réponse")
            logger.error(f"Longueur de la réponse: {len(response_text)} caractères")
            logger.error(f"Réponse complète (premiers 2000 caractères):\n{response_text[:2000]}")
            if len(response_text) > 2000:
                logger.error(f"... (tronqué, {len(response_text) - 2000} caractères restants)")
            raise ValueError("Pas de JSON trouvé dans la réponse")
            
        except json.JSONDecodeError as e:
            logger.error(f"Erreur de parsing JSON: {e}")
            logger.debug(f"Réponse reçue (premiers 1000 caractères):\n{response_text[:1000]}")
            raise ValueError(f"Erreur lors du parsing JSON: {e}\nRéponse: {response_text[:1000]}")
    
    def _extract_act_from_json(self, parsed_json: dict, act_key: str) -> dict:
        """Extrait les données d'un acte depuis un JSON parsé.
        
        Gère différents formats de réponse :
        - {"title": ..., "content": ...} (format direct)
        - {"acte_4": {"title": ..., "content": ...}} (format imbriqué)
        - {"acte_iv": {"title": ..., "content": ...}} (format alternatif)
        
        Args:
            parsed_json: JSON parsé
            act_key: Clé de l'acte (ex: "acte_4")
            
        Returns:
            Dictionnaire avec 'title' et 'content'
        """
        # Si le JSON contient directement title et content
        if "title" in parsed_json and "content" in parsed_json:
            return parsed_json
        
        # Si le JSON contient une clé acte_X
        if act_key in parsed_json:
            return parsed_json[act_key]
        
        # Essayer les variantes (acte_iv, acte_IV, etc.)
        act_variants = [
            act_key.replace("_", "_").lower(),
            act_key.replace("_", "_").upper(),
            act_key.replace("acte_", "acte_iv_") if "4" in act_key else act_key,
        ]
        
        for variant in act_variants:
            if variant in parsed_json:
                return parsed_json[variant]
        
        # Si aucune clé trouvée, essayer de trouver n'importe quelle clé qui contient title/content
        for key, value in parsed_json.items():
            if isinstance(value, dict) and "title" in value and "content" in value:
                logger.debug(f"Acte trouvé sous la clé '{key}' au lieu de '{act_key}'")
                return value
        
        # Si toujours rien, retourner le JSON tel quel (peut-être que c'est déjà le bon format)
        logger.warning(f"Format JSON inattendu pour {act_key}, utilisation directe")
        return parsed_json
