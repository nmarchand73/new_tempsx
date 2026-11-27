"""Interface en ligne de commande de NEW TEMPS X (`python app.py` ou `newtempsx`)."""

import argparse
import asyncio
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from .exporters import EpisodeExporter
from .models import Episode
from .orchestrator import EpisodeOrchestrator, EpisodeRejectedError, StructuredOutputError
from .validators import NarrativeValidator

logger = logging.getLogger("newtempsx.cli")

DEFAULT_SCENARIO = (
    "Les dernières avancées en intelligence artificielle posent la question de la conscience artificielle.\n"
    "Des systèmes comme GPT-4 montrent des capacités émergentes qui ressemblent à de la compréhension.\n"
    "Que signifie vraiment 'comprendre' pour une machine ?"
)

SDK_LOGGERS = ("claude_agent_sdk", "claude_agent_sdk._internal", "claude_agent_sdk._internal.query")


class CliError(Exception):
    """Erreur utilisateur : message affiché, code de sortie 1."""


# --------------------------------------------------------------------------- utilitaires
def configure_logging(verbose: bool = False) -> None:
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S")
        if verbose
        else logging.Formatter("%(levelname)s - %(message)s")
    )
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    if verbose:
        for name in SDK_LOGGERS:
            logging.getLogger(name).setLevel(logging.DEBUG)


def create_slug_from_text(text: str, max_words: int = 4, max_length: int = 50) -> str:
    """Slug explicite (minuscules, underscores) à partir des premiers mots d'un texte."""
    if not text or not text.strip():
        return "episode"
    slug = "_".join(text.strip().split()[:max_words])
    slug = re.sub(r"[^\w\s\-_]", "", slug)
    slug = re.sub(r"[\s\-]+", "_", slug)
    slug = re.sub(r"_+", "_", slug).strip("_")[:max_length].rstrip("_")
    return slug.lower() or "episode"


def generate_explicit_run_name(scenario: str) -> str:
    return f"{create_slug_from_text(scenario, 4, 40)}_{datetime.now():%Y%m%d_%H%M%S}"


def load_episode(run_dir: Path) -> Episode:
    """Charge `episode.json` d'un run (la validation Pydantic gère les champs optionnels)."""
    episode_json = run_dir / "episode.json"
    if not episode_json.exists():
        raise CliError(f"episode.json introuvable: {episode_json}")
    return Episode.model_validate_json(episode_json.read_text(encoding="utf-8"))


def existing_run_dir(args) -> Path:
    if not args.run_name:
        raise CliError("--audio-only / --images-only nécessitent --run-name (épisode existant)")
    return Path(args.output_dir) / args.run_name


# --------------------------------------------------------------------------- étapes
async def generate_audio(episode: Episode, output_dir: Path, provider_name: str) -> int:
    from .audio_generator import AudioGenerator, TTSProvider

    provider = TTSProvider(provider_name)
    cost_optimized = os.getenv("ELEVENLABS_COST_OPTIMIZED", "false").lower() == "true"
    logger.info("🎵 Génération audio avec %s%s", provider.value, " (mode économique)" if cost_optimized else "")
    gen = AudioGenerator(output_dir=output_dir / "audio", provider=provider, cost_optimized=cost_optimized)
    files = await gen.generate_episode_audio(episode)
    count = sum(path is not None for path in files.values())
    if episode.twilight_zone_story:
        twilight = await gen.generate_twilight_zone_audio(episode.twilight_zone_story, episode.episode_title)
        count += twilight is not None
    if count:
        logger.info("✅ %d fichier(s) audio dans %s", count, output_dir / "audio")
    else:
        logger.warning("⚠️  Aucun fichier audio généré. Vérifiez vos clés API.")
    return count


async def generate_images(episode: Episode, output_dir: Path, exporter: EpisodeExporter) -> int:
    from .image_generator import ImageGenerator

    logger.info("🎨 Génération des images à partir des prompts...")
    gen = ImageGenerator(output_dir=output_dir / "images")
    images = await gen.generate_episode_images(episode, exporter=exporter)
    total = sum(len(v) for v in images.values())
    if total:
        exporter.export_json(episode)
        logger.info("✅ %d image(s) dans %s (JSON mis à jour)", total, output_dir / "images")
    else:
        logger.warning("⚠️  Aucune image générée. Vérifiez OPENAI_API_KEY et les image_prompts des actes.")
    return total


async def run_twilight_only(orchestrator, exporter, scenario: str, output_dir: Path) -> None:
    story = await orchestrator.generate_twilight_zone_story_only(scenario)
    exporter.export_twilight_zone_story(story)
    exporter.export_json(
        Episode(
            episode_title=f"Histoire Twilight Zone: {story.title}",
            scenario_input=scenario,
            narrative_arc="Histoire bonus générée indépendamment",
            acts={},
            twilight_zone_story=story,
        )
    )
    logger.info("✅ Histoire générée: %s (thème: %s)", story.title, story.theme)
    logger.info("📁 Fichiers dans: %s", output_dir.absolute())


def rename_run_after_title(episode: Episode, base_dir: Path, output_dir: Path, exporter: EpisodeExporter) -> Path:
    """Renomme le dossier du run d'après le titre de l'épisode. Retourne le dossier final."""
    new_name = f"{create_slug_from_text(episode.episode_title, 5, 50)}_{datetime.now():%Y%m%d_%H%M%S}"
    new_dir = base_dir / new_name
    try:
        output_dir.rename(new_dir)
    except OSError as exc:
        logger.warning("⚠️  Impossible de renommer le dossier (%s), il reste: %s", exc, output_dir.name)
        return output_dir
    exporter.output_dir = new_dir
    exporter.run_name = new_name
    exporter.export_json(episode)
    logger.info("📁 Dossier renommé: %s", new_name)
    return new_dir


async def run_full_episode(
    args, scenario: str, orchestrator, exporter, base_dir: Path, output_dir: Path, resume: Episode | None = None
) -> None:
    episode = await orchestrator.generate_episode(scenario, resume=resume)

    ok, message = NarrativeValidator().validate_episode(episode)
    if not ok:
        raise CliError(f"Validation structurelle échouée: {message}")

    exporter.export_all(episode)
    if not args.run_name and not args.resume:
        output_dir = rename_run_after_title(episode, base_dir, output_dir, exporter)

    # Audio et images sont optionnels : un échec ne fait pas perdre l'épisode.
    if args.audio:
        try:
            await generate_audio(episode, output_dir, args.audio_provider)
        except Exception as exc:
            logger.warning("⚠️  Audio non généré (épisode conservé): %s", exc)
    if args.images:
        try:
            await generate_images(episode, output_dir, exporter)
        except Exception as exc:
            logger.warning("⚠️  Images non générées (épisode conservé): %s", exc)

    logger.info("\n✅ Épisode généré: %s", episode.episode_title)
    logger.info("📁 Fichiers dans: %s", output_dir.absolute())


# --------------------------------------------------------------------------- CLI
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Génère un épisode NEW TEMPS X",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemples:\n"
            '  python app.py "Votre scénario ici"\n'
            '  python app.py "Scénario" --audio --audio-provider openai --verbose\n'
            '  python app.py "Scénario" --twilight-only\n'
            "  python app.py --audio-only --run-name mon_run\n"
        ),
    )
    parser.add_argument("scenario", nargs="?", help="Scénario d'entrée (scénario par défaut si omis)")
    parser.add_argument("--output-dir", "-o", default="output", help="Répertoire de sortie (défaut: output)")
    parser.add_argument("--project-root", "-p", default=None, help="Racine du projet (Skills), défaut: cwd")
    parser.add_argument("--verbose", "-v", action="store_true", help="Logs détaillés (DEBUG)")
    parser.add_argument("--audio", "-a", action="store_true", help="Génère aussi l'audio de chaque acte")
    parser.add_argument("--audio-provider", choices=["elevenlabs", "openai"], default="elevenlabs")
    parser.add_argument("--images", "-i", action="store_true", help="Génère aussi les images (OPENAI_API_KEY)")
    parser.add_argument("--run-name", default=None, help="Nom du run (défaut: auto, basé sur le titre)")
    parser.add_argument(
        "--resume", metavar="RUN", default=None, help="Reprend un run interrompu (saute les étapes déjà générées)"
    )
    parser.add_argument("--twilight-only", action="store_true", help="Uniquement l'histoire bonus Twilight Zone")
    parser.add_argument("--audio-only", action="store_true", help="Audio seul pour un run existant (--run-name)")
    parser.add_argument("--images-only", action="store_true", help="Images seules pour un run existant (--run-name)")
    return parser


async def run(args) -> None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        logger.info("ℹ️  ANTHROPIC_API_KEY absente: utilisation de votre souscription Claude Code si disponible.")

    # Modes sur un run existant (pas d'appel à Claude)
    if args.audio_only or args.images_only:
        run_dir = existing_run_dir(args)
        episode = load_episode(run_dir)
        logger.info("✅ Épisode chargé: %s", episode.episode_title)
        if args.audio_only:
            await generate_audio(episode, run_dir, args.audio_provider)
        if args.images_only:
            await generate_images(episode, run_dir, EpisodeExporter(output_dir=run_dir, run_name=args.run_name))
        return

    resume = None
    if args.resume:
        if args.twilight_only:
            raise CliError("--resume est incompatible avec --twilight-only")
        args.run_name = args.resume
        resume = load_episode(Path(args.output_dir) / args.resume)
        args.scenario = args.scenario or resume.scenario_input
        logger.info("♻️  Reprise du run %s (%d acte(s) déjà généré(s))", args.resume, len(resume.acts))

    scenario = args.scenario
    if not scenario:
        scenario = DEFAULT_SCENARIO
        logger.info('ℹ️  Aucun scénario fourni, scénario par défaut utilisé (python app.py "Votre scénario").')
    logger.info("📝 Scénario: %s...", scenario[:100])

    project_root = Path(args.project_root) if args.project_root else Path.cwd()
    if not (project_root / ".claude" / "skills").exists():
        raise CliError(f"Répertoire des Skills introuvable dans {project_root} (lancez depuis la racine du projet)")

    run_name = args.run_name or generate_explicit_run_name(scenario)
    base_dir = Path(args.output_dir)
    output_dir = base_dir / run_name
    logger.info("📁 Run: %s -> %s", run_name, output_dir)

    exporter = EpisodeExporter(output_dir=output_dir, run_name=run_name)
    orchestrator = EpisodeOrchestrator(project_root=project_root, exporter=exporter, debug=args.verbose)
    if args.twilight_only:
        await run_twilight_only(orchestrator, exporter, scenario, output_dir)
    else:
        await run_full_episode(args, scenario, orchestrator, exporter, base_dir, output_dir, resume)


def cli(argv: list[str] | None = None) -> None:
    load_dotenv()
    args = build_parser().parse_args(argv)
    configure_logging(args.verbose)
    try:
        asyncio.run(run(args))
    except CliError as exc:
        logger.error("❌ %s", exc)
        sys.exit(1)
    except EpisodeRejectedError as exc:
        logger.error("❌ Épisode rejeté par la validation narrative: %s", exc)
        sys.exit(2)
    except StructuredOutputError as exc:
        logger.error("❌ Sortie du modèle inexploitable: %s", exc)
        sys.exit(3)
    except KeyboardInterrupt:
        logger.warning("Interrompu. Reprenez avec: python app.py --resume <run> (voir le dossier output/).")
        sys.exit(130)
    except Exception:
        logger.exception("❌ Erreur lors de la génération")
        sys.exit(1)
