"""Application simple pour générer un épisode NEW TEMPS X."""

import argparse
import asyncio
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from newtempsx.orchestrator import EpisodeOrchestrator
from newtempsx.exporters import EpisodeExporter
from newtempsx.validators import NarrativeValidator

# Charger les variables d'environnement depuis .env
load_dotenv()

# Configuration du logging
# Format simple par défaut, format détaillé en mode DEBUG
def configure_logging(verbose: bool = False):
    """Configure le logging selon le mode verbose."""
    # Obtenir le handler root
    root_logger = logging.getLogger()
    
    # Supprimer les handlers existants pour reconfigurer
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Créer un nouveau handler avec le format approprié
    handler = logging.StreamHandler()
    if verbose:
        # Format simplifié en mode DEBUG : timestamp court + message
        # On évite d'afficher le nom du logger complet pour plus de lisibilité
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        root_logger.setLevel(logging.DEBUG)
    else:
        # Format simple en mode INFO
        formatter = logging.Formatter('%(levelname)s - %(message)s')
        root_logger.setLevel(logging.INFO)
    
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

# Configuration initiale
configure_logging(verbose=False)

# Réduire le bruit des logs des dépendances
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def create_slug_from_text(text: str, max_words: int = 4, max_length: int = 50) -> str:
    """Crée un slug explicite à partir d'un texte.
    
    Args:
        text: Texte source
        max_words: Nombre maximum de mots à utiliser
        max_length: Longueur maximale du slug
        
    Returns:
        Slug nettoyé et formaté
    """
    if not text or not text.strip():
        return "episode"
    
    # Prendre les premiers mots
    words = text.strip().split()[:max_words]
    slug = "_".join(words)
    
    # Nettoyer : garder seulement lettres, chiffres, espaces, tirets, underscores
    slug = re.sub(r'[^\w\s\-_]', '', slug)
    # Remplacer les espaces multiples par un underscore
    slug = re.sub(r'\s+', '_', slug)
    # Remplacer les tirets par des underscores
    slug = slug.replace('-', '_')
    # Supprimer les underscores multiples
    slug = re.sub(r'_+', '_', slug)
    # Supprimer les underscores en début/fin
    slug = slug.strip('_')
    
    # Limiter la longueur
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip('_')
    
    # S'assurer qu'on a quelque chose
    if not slug:
        slug = "episode"
    
    return slug.lower()


def generate_explicit_run_name(scenario: str) -> str:
    """Génère un nom de run explicite basé sur le scénario.
    
    Args:
        scenario: Scénario d'entrée
        
    Returns:
        Nom de run explicite avec timestamp
    """
    slug = create_slug_from_text(scenario, max_words=4, max_length=40)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{slug}_{timestamp}"


async def main():
    """Fonction principale pour générer un épisode."""
    
    # Parser les arguments en ligne de commande
    parser = argparse.ArgumentParser(
        description="Génère un épisode NEW TEMPS X",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python app.py "Votre scénario ici"
  python app.py "Scénario" --output-dir custom_output --audio
  python app.py "Scénario" --audio --audio-provider openai --verbose
  python app.py "Scénario" --twilight-only
        """
    )
    
    parser.add_argument(
        'scenario',
        type=str,
        nargs='?',
        help='Texte du scénario d\'entrée (ou utilisez le scénario par défaut si non fourni)'
    )
    
    parser.add_argument(
        '--output-dir', '-o',
        type=str,
        default='output',
        help='Répertoire de sortie (défaut: output)'
    )
    
    parser.add_argument(
        '--project-root', '-p',
        type=str,
        default=None,
        help='Racine du projet (pour charger les Skills, défaut: répertoire courant)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Affiche les logs détaillés (mode DEBUG)'
    )
    
    parser.add_argument(
        '--audio', '-a',
        action='store_true',
        help='Génère également les fichiers audio pour chaque acte'
    )
    
    parser.add_argument(
        '--audio-provider',
        type=str,
        choices=['elevenlabs', 'openai'],
        default='elevenlabs',
        help='Provider TTS pour la génération audio (défaut: elevenlabs)'
    )
    
    parser.add_argument(
        '--run-name',
        type=str,
        default=None,
        help='Nom personnalisé pour ce run (défaut: timestamp automatique)'
    )
    
    parser.add_argument(
        '--twilight-only',
        action='store_true',
        help='Génère uniquement l\'histoire bonus Twilight Zone (sans générer l\'épisode complet)'
    )
    
    parser.add_argument(
        '--audio-only',
        action='store_true',
        help='Génère uniquement les fichiers audio pour un épisode existant (nécessite --run-name ou --output-dir avec un épisode existant)'
    )
    
    args = parser.parse_args()
    
    # Configurer le logging selon verbose (doit être fait avant tout autre logging)
    configure_logging(verbose=args.verbose)
    
    # Reconfigurer selon verbose pour les loggers spécifiques
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        
        # Activer les logs de debug du SDK Claude Agents
        # Note: Le SDK utilise principalement debug_stderr dans ClaudeAgentOptions
        # Les loggers Python sont activés en complément
        claude_loggers = [
            'claude_agent_sdk',
            'claude_agent_sdk._internal',
            'claude_agent_sdk._internal.message_parser',
            'claude_agent_sdk._internal.query',
            'claude_agent_sdk._internal.transport',
            'claude_agent_sdk._internal.transport.subprocess_cli',
        ]
        for logger_name in claude_loggers:
            logging.getLogger(logger_name).setLevel(logging.DEBUG)
        
        # Optionnel: activer les logs HTTP pour voir les requêtes/réponses détaillées
        # Décommentez ces lignes pour voir toutes les requêtes HTTP (peut être très verbeux)
        # logging.getLogger('httpx').setLevel(logging.DEBUG)
        # logging.getLogger('httpcore').setLevel(logging.DEBUG)
        
        logger.info("🔍 Mode DEBUG activé")
        logger.info("   - Logs détaillés de l'application activés")
        logger.info("   - Logs du SDK Claude Agents activés (debug_stderr)")
        logger.info("   - Les logs du SDK apparaîtront sur stderr pendant l'exécution")
    
    # Scénario : utiliser celui fourni en argument ou le défaut
    if args.scenario:
        scenario = args.scenario
    else:
        # Scénario par défaut si aucun n'est fourni
        scenario = """Les dernières avancées en intelligence artificielle posent la question de la conscience artificielle. 
Des systèmes comme GPT-4 montrent des capacités émergentes qui ressemblent à de la compréhension. 
Que signifie vraiment 'comprendre' pour une machine ?"""
        logger.info("ℹ️  Aucun scénario fourni, utilisation du scénario par défaut")
        logger.info("   Utilisez: python app.py \"Votre scénario\" pour fournir un scénario personnalisé")
    
    # Vérifier l'authentification (API key ou souscription Claude Code)
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        logger.info("ℹ️  ANTHROPIC_API_KEY non trouvée.")
        logger.info("   Le SDK tentera d'utiliser votre souscription Claude Code si disponible.")
        logger.info("   Si vous préférez utiliser une API key, configurez-la dans .env :")
        logger.info("   ANTHROPIC_API_KEY=your-api-key")
        logger.info("   (Obtenez votre clé sur https://console.anthropic.com/)")
    else:
        logger.debug("✅ API key trouvée, utilisation de l'API Anthropic")
    
    # Mode audio-only : générer uniquement l'audio pour un épisode existant
    if args.audio_only:
        if not args.run_name:
            logger.error("❌ --audio-only nécessite --run-name pour spécifier l'épisode existant")
            logger.error("   Exemple: python app.py --audio-only --run-name nom_de_l_episode")
            sys.exit(1)
        
        run_name = args.run_name
        base_output_dir = Path(args.output_dir)
        output_dir = base_output_dir / run_name
        episode_json = output_dir / "episode.json"
        
        if not episode_json.exists():
            logger.error(f"❌ Fichier episode.json introuvable: {episode_json}")
            logger.error(f"   Vérifiez que l'épisode existe dans: {output_dir}")
            sys.exit(1)
        
        logger.info("🎵 Mode audio-only: génération uniquement des fichiers audio")
        logger.info(f"📁 Épisode: {run_name}")
        logger.info(f"📁 Répertoire: {output_dir}")
        
        try:
            from newtempsx.audio_generator import AudioGenerator, TTSProvider
            from newtempsx.models import Episode
            import json
            
            # Charger l'épisode depuis le JSON
            logger.info("📂 Chargement de l'épisode depuis episode.json...")
            with open(episode_json, 'r', encoding='utf-8') as f:
                episode_dict = json.load(f)
            
            # Convertir en modèle Episode
            from newtempsx.models import Act, Reference, TwilightZoneStory
            acts = {}
            for act_key, act_data in episode_dict.get('acts', {}).items():
                # Convertir les références
                references = []
                for ref_data in act_data.get('references', []):
                    references.append(Reference(**ref_data))
                act_data['references'] = references
                acts[act_key] = Act(**act_data)
            
            episode = Episode(
                episode_title=episode_dict.get('episode_title', 'Épisode'),
                scenario_input=episode_dict.get('scenario_input', ''),
                narrative_arc=episode_dict.get('narrative_arc', ''),
                acts=acts
            )
            
            # Charger l'histoire Twilight Zone si présente
            if 'twilight_zone_story' in episode_dict and episode_dict['twilight_zone_story']:
                twilight_data = episode_dict['twilight_zone_story']
                episode.twilight_zone_story = TwilightZoneStory(**twilight_data)
            
            logger.info(f"✅ Épisode chargé: {episode.episode_title}")
            
            # Générer l'audio
            provider = TTSProvider.ELEVENLABS if args.audio_provider == 'elevenlabs' else TTSProvider.OPENAI
            cost_optimized = os.getenv("ELEVENLABS_COST_OPTIMIZED", "false").lower() == "true"
            
            logger.info(f"🎵 Génération des fichiers audio avec {provider.value}...")
            if cost_optimized:
                logger.info("💰 Mode économique activé (réduction des coûts)")
            
            audio_gen = AudioGenerator(
                output_dir=output_dir / "audio",
                provider=provider,
                cost_optimized=cost_optimized
            )
            
            audio_files = await audio_gen.generate_episode_audio(episode)
            generated_count = sum(1 for path in audio_files.values() if path is not None)
            
            # Générer l'audio pour l'histoire Twilight Zone si disponible
            if episode.twilight_zone_story:
                logger.info("🎬 Génération audio pour l'histoire Twilight Zone...")
                twilight_audio = await audio_gen.generate_twilight_zone_audio(
                    episode.twilight_zone_story,
                    episode.episode_title
                )
                if twilight_audio:
                    logger.info(f"✅ Audio Twilight Zone généré: {twilight_audio.name}")
                    generated_count += 1
            
            if generated_count > 0:
                logger.info(f"✅ {generated_count} fichiers audio générés dans {output_dir / 'audio'}")
            else:
                logger.warning("⚠️  Aucun fichier audio généré. Vérifiez vos clés API.")
            
            logger.info(f"\n✅ Génération audio terminée!")
            logger.info(f"📁 Fichiers audio dans: {(output_dir / 'audio').absolute()}")
            return
        
        except Exception as e:
            logger.exception("❌ Erreur lors de la génération audio")
            logger.error(f"Erreur: {e}")
            sys.exit(1)
    
    if args.twilight_only:
        logger.info("🌟 Génération d'une histoire Twilight Zone uniquement...")
    else:
        logger.info("🎬 Génération d'un épisode NEW TEMPS X...")
    logger.info(f"📝 Scénario: {scenario[:100]}...")
    
    # Déterminer la racine du projet
    if args.project_root:
        project_root = Path(args.project_root)
    else:
        project_root = Path.cwd()
    
    # Générer un nom de run unique et explicite
    if args.run_name:
        run_name = args.run_name
    else:
        # Créer un nom explicite basé sur le scénario
        run_name = generate_explicit_run_name(scenario)
    
    # Organiser les fichiers par run
    base_output_dir = Path(args.output_dir)
    output_dir = base_output_dir / run_name
    
    logger.info(f"📁 Run: {run_name}")
    logger.info(f"📁 Répertoire de sortie: {output_dir}")
    
    # Vérifier que les Skills existent
    skills_dir = project_root / ".claude" / "skills"
    if not skills_dir.exists():
        logger.error(f"❌ Répertoire des Skills introuvable: {skills_dir}")
        logger.error("   Assurez-vous d'exécuter depuis la racine du projet.")
        return
    
    logger.debug(f"Racine du projet: {project_root}")
    logger.debug(f"Répertoire de sortie: {output_dir}")
    logger.debug(f"Répertoire des Skills: {skills_dir}")
    
    try:
        # Créer l'exporteur (sera utilisé pour l'export progressif)
        exporter = EpisodeExporter(output_dir=output_dir, run_name=run_name)
        
        # Créer l'orchestrateur avec l'exporteur pour export progressif
        logger.info("🔧 Initialisation de l'orchestrateur...")
        orchestrator = EpisodeOrchestrator(
            project_root=project_root, 
            exporter=exporter,
            debug=args.verbose  # Active les logs de debug du SDK Claude Agents
        )
        if args.verbose:
            logger.debug("Orchestrateur initialisé avec debug activé (logs SDK sur stderr)")
        else:
            logger.debug("Orchestrateur initialisé")
        
        if args.twilight_only:
            # Générer uniquement l'histoire Twilight Zone
            logger.info("🌟 Génération de l'histoire Twilight Zone...")
            twilight_story = await orchestrator.generate_twilight_zone_story_only(scenario)
            
            if twilight_story:
                # Exporter l'histoire
                exporter.export_twilight_zone_story(twilight_story)
                
                # Créer un JSON minimal pour l'UI
                from newtempsx.models import Episode
                minimal_episode = Episode(
                    episode_title=f"Histoire Twilight Zone: {twilight_story.title}",
                    scenario_input=scenario,
                    narrative_arc="Histoire bonus générée indépendamment",
                    acts={},
                    twilight_zone_story=twilight_story
                )
                exporter.export_json(minimal_episode)
                
                logger.info(f"✅ Histoire Twilight Zone générée: {twilight_story.title}")
                logger.info(f"📁 Fichiers dans: {output_dir.absolute()}")
                logger.info(f"📄 Titre: {twilight_story.title}")
                logger.info(f"🎭 Thème: {twilight_story.theme}")
                
                # Terminer ici pour le mode twilight-only
                return
            else:
                logger.error("❌ Échec de la génération de l'histoire Twilight Zone")
                sys.exit(1)
        else:
            # Générer l'épisode complet (avec export progressif)
            logger.info("🚀 Démarrage de la génération...")
            episode = await orchestrator.generate_episode(scenario)
            
            # Valider structurellement
            logger.info("🔍 Validation structurelle...")
            validator = NarrativeValidator()
            is_valid, message = validator.validate_episode(episode)
            if not is_valid:
                logger.error(f"❌ Validation structurelle échouée: {message}")
                return
            logger.info("✅ Validation structurelle réussie")
            
            # Exporter l'épisode complet (pour compatibilité, mais déjà fait progressivement)
            logger.info("💾 Export final des fichiers...")
            exporter.export_all(episode)
            logger.info("✅ Export terminé")
        
            # Renommer le dossier avec un nom basé sur le titre de l'épisode
            if not args.run_name:  # Seulement si le nom n'était pas explicite
                episode_slug = create_slug_from_text(episode.episode_title, max_words=5, max_length=50)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                new_run_name = f"{episode_slug}_{timestamp}"
                
                # Vérifier que le nouveau nom est différent
                if new_run_name != run_name:
                    new_output_dir = base_output_dir / new_run_name
                    try:
                        if output_dir.exists():
                            output_dir.rename(new_output_dir)
                            output_dir = new_output_dir
                            run_name = new_run_name
                            # Mettre à jour le run_name dans l'exporteur
                            exporter.run_name = run_name
                            # Mettre à jour le JSON avec le nouveau run_name
                            exporter.export_json(episode)
                            logger.info(f"📁 Dossier renommé: {run_name}")
                    except Exception as e:
                        logger.warning(f"⚠️  Impossible de renommer le dossier: {e}")
                        logger.warning(f"   Le dossier reste: {run_name}")
            
            logger.info(f"\n✅ Épisode généré avec succès!")
            logger.info(f"📁 Fichiers dans: {output_dir.absolute()}")
            logger.info(f"📄 Titre: {episode.episode_title}")
        
            # Génération audio (optionnelle)
            if args.audio:
                try:
                    from newtempsx.audio_generator import AudioGenerator, TTSProvider
                    
                    # Utiliser le provider spécifié en argument
                    provider = TTSProvider.ELEVENLABS if args.audio_provider == 'elevenlabs' else TTSProvider.OPENAI
                    
                    logger.info(f"🎵 Génération des fichiers audio avec {provider.value}...")
                    # Mode économique activé via variable d'environnement
                    cost_optimized = os.getenv("ELEVENLABS_COST_OPTIMIZED", "false").lower() == "true"
                    if cost_optimized:
                        logger.info("💰 Mode économique activé (réduction des coûts)")
                    audio_gen = AudioGenerator(
                        output_dir=output_dir / "audio",
                        provider=provider,
                        cost_optimized=cost_optimized
                    )
                    audio_files = await audio_gen.generate_episode_audio(episode)
                    generated_count = sum(1 for path in audio_files.values() if path is not None)
                    
                    # Générer l'audio pour l'histoire Twilight Zone si disponible
                    if episode.twilight_zone_story:
                        logger.info("🎬 Génération audio pour l'histoire Twilight Zone...")
                        twilight_audio = await audio_gen.generate_twilight_zone_audio(
                            episode.twilight_zone_story,
                            episode.episode_title
                        )
                        if twilight_audio:
                            logger.info(f"✅ Audio Twilight Zone généré: {twilight_audio.name}")
                            generated_count += 1
                    
                    if generated_count > 0:
                        logger.info(f"✅ {generated_count} fichiers audio générés dans {output_dir / 'audio'}")
                    else:
                        logger.warning("⚠️  Aucun fichier audio généré. Vérifiez vos clés API.")
                except Exception as e:
                    logger.warning(f"⚠️  Erreur lors de la génération audio: {e}")
                    logger.warning("   L'épisode a été généré, mais l'audio n'a pas pu être créé.")
            else:
                # Vérifier si l'épisode existe déjà et proposer de générer l'audio
                episode_json = output_dir / "episode.json"
                if episode_json.exists():
                    logger.info("💡 Pour générer l'audio, utilisez:")
                    logger.info(f"   python app.py \"{scenario[:50]}...\" --audio")
                    logger.info(f"   ou utilisez directement le module Python (voir README_AUDIO.md)")
            
            logger.info(f"\n✅ Épisode généré avec succès!")
            logger.info(f"📁 Fichiers dans: {output_dir.absolute()}")
            logger.info(f"📄 Titre: {episode.episode_title}")
        
    except ValueError as e:
        logger.error(f"❌ Erreur de validation narrative: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception("❌ Erreur lors de la génération")
        logger.error(f"Erreur: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

