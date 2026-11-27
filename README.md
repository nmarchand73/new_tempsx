# NEW TEMPS X

Système narratif AI qui génère des épisodes inspirés de l'émission française **Temps X** (années 1980), adaptés à la science, à la technologie et à la culture d'aujourd'hui.

À partir d'un simple scénario, il produit un épisode en **7 actes**, une **nouvelle bonus** façon Twilight Zone, et optionnellement les **voix** et les **images** — le tout consultable dans un lecteur web local.

## Démarrage rapide

```bash
git clone https://github.com/nmarchand73/new_tempsx.git && cd new_tempsx
uv sync --extra dev                # ou : pip install -e ".[dev]"
python app.py "Votre scénario"     # génère output/<run>/
python ui/server.py                # lecteur sur http://127.0.0.1:8000
```

Il faut une authentification Claude (voir [Prérequis](#prérequis)). Audio et images sont optionnels : `--audio`, `--images`.

## Fonctionnalités

- **Épisode en 7 actes** produit par des Skills spécialisés (arc narratif, science, fiction, dialogue, mémoire, transmission) puis relu par un Skill de validation.
- **Sorties structurées** : chaque étape renvoie un JSON validé par un schéma, les étapes sont chaînées dans une même session.
- **Histoire bonus Twilight Zone** (novelette de 8 000 à 15 000 mots).
- **Audio** (ElevenLabs ou OpenAI TTS) avec deux narrateurs alternés, **images** (OpenAI) intégrées au texte.
- **Reprise** d'un run interrompu (`--resume`) et **suivi du coût** de génération.
- **Lecteur web** local : thème sombre/clair, navigation par acte, lecture audio, lightbox d'images.

## Prérequis

- **Python 3.11+**
- **Claude Code** comme runtime du SDK, avec l'une de ces authentifications :
  - une **souscription Claude Code** active (aucune clé à configurer, recommandé) ;
  - ou une clé `ANTHROPIC_API_KEY` dans `.env` (prioritaire si les deux existent).
- *Optionnel* : **ffmpeg** (concaténation propre des MP3 longs), clés **OpenAI** et/ou **ElevenLabs** pour les images et l'audio.

Installation de Claude Code : voir la [documentation officielle](https://docs.anthropic.com/en/docs/claude-code/setup).

## Installation et configuration

```bash
uv sync                            # ou : pip install -e .
cp env.example .env                # Windows PowerShell : Copy-Item env.example .env
```

Toutes les variables sont optionnelles (les clés ne sont nécessaires que pour la fonctionnalité correspondante). Ne commitez jamais `.env`.

| Variable | Rôle | Défaut |
|---|---|---|
| `ANTHROPIC_API_KEY` | Clé API Anthropic (sinon souscription Claude Code) | — |
| `NEWTEMPSX_MODEL` | Modèle Claude utilisé pour le texte | celui du SDK/CLI |
| `NEWTEMPSX_MAX_BUDGET_USD` | Budget maximal **par étape** de génération | illimité |
| `OPENAI_API_KEY` | Images et/ou TTS OpenAI | — |
| `OPENAI_IMAGE_MODEL` | Modèle d'image (`dall-e-3`, `gpt-image-1`) | `dall-e-3` |
| `OPENAI_TTS_MODEL` | Modèle TTS OpenAI (`tts-1`, `tts-1-hd`…) | `tts-1` |
| `ELEVENLABS_API_KEY` | Audio ElevenLabs | — |
| `ELEVENLABS_VOICE_ID_1` / `_2` | Voix des narrateurs 1 et 2 | Charlotte / Antoni |
| `ELEVENLABS_VOICE_ID_TWILIGHT` | Voix de l'histoire bonus | Arnold |
| `ELEVENLABS_COST_OPTIMIZED` | `true` : modèle turbo et réglages réduits (≈ −40 % de coût) | `false` |

## Usage

```bash
python app.py "Votre scénario"                          # épisode seul (texte)
python app.py "Votre scénario" --audio                  # + audio ElevenLabs
python app.py "Votre scénario" --audio --audio-provider openai
python app.py "Votre scénario" --images                 # + images
python app.py "Votre scénario" --twilight-only          # uniquement l'histoire bonus
python app.py                                           # scénario par défaut
python app.py --help
```

Le script est aussi disponible sous le nom `newtempsx` après installation.

### Options

| Option | Description |
|---|---|
| `scenario` | Scénario d'entrée (positionnel, optionnel) |
| `--output-dir`, `-o` | Répertoire de sortie (défaut : `output`) |
| `--project-root`, `-p` | Racine du projet contenant `.claude/skills/` (défaut : répertoire courant) |
| `--verbose`, `-v` | Logs détaillés (DEBUG, y compris SDK) |
| `--audio`, `-a` | Génère l'audio de chaque acte (et de l'histoire bonus) |
| `--audio-provider` | `elevenlabs` (défaut) ou `openai` |
| `--images`, `-i` | Génère les images à partir des prompts des actes (`OPENAI_API_KEY`) |
| `--run-name` | Nom du run (défaut : dérivé du titre de l'épisode + horodatage) |
| `--resume RUN` | Reprend un run interrompu |
| `--twilight-only` | Génère uniquement l'histoire bonus |
| `--audio-only` | Audio seul pour un run existant (nécessite `--run-name`) |
| `--images-only` | Images seules pour un run existant (nécessite `--run-name`) |

Codes de sortie : `0` succès · `1` erreur d'usage ou d'exécution · `2` épisode rejeté par la validation narrative · `3` sortie du modèle inexploitable · `130` interruption (Ctrl+C).

### Structure d'un run

```
output/<run>/
├── episode.json                 # épisode complet (+ themes, cost_usd)
├── markdown/
│   ├── 01_le_signal.md … 07_la_transmission.md
│   └── twilight_zone_story.md
├── audio/                       # avec --audio : acte_N_<titre>_<hash>.mp3, twilight_zone_*.mp3
└── images/                      # avec --images : images PNG insérées dans le texte
```

Les fichiers sont écrits **au fil de la génération** : l'arc, puis chaque acte, dès qu'ils existent. Le lecteur web les affiche en direct.

### Reprendre un run interrompu

```bash
python app.py --resume <run>
```

Les étapes déjà faites (arc, actes, histoire bonus) sont sautées ; seules les manquantes sont générées, puis la validation. Les actes existants ne sont jamais écrasés et le dossier n'est pas renommé. Le coût cumulé s'additionne d'une reprise à l'autre.

Limites : les runs créés **avant** cette fonctionnalité n'ont pas les thèmes par acte et ne sont pas reprenables (refus explicite). La conversation du modèle n'est pas reprise : seuls les titres des actes déjà écrits servent de contexte.

### Audio

```bash
python app.py "Scénario" --audio                           # pendant la génération
python app.py --audio-only --run-name <run>                # sur un épisode existant
python app.py --audio-only --run-name <run> --audio-provider openai
```

- Deux narrateurs alternés (actes impairs / pairs) et une voix dédiée à l'histoire bonus (`onyx` pour OpenAI).
- Les textes longs sont **découpés** (4 096 caractères pour OpenAI, 9 500 pour ElevenLabs), synthétisés puis **concaténés avec ffmpeg** (repli binaire, moins précis, sans ffmpeg).
- Appels **réessayés** (429/5xx, backoff), **3 actes en parallèle**, résultats mis en cache (un fichier existant n'est pas régénéré).
- Pour réduire le coût : `ELEVENLABS_COST_OPTIMIZED=true`, ou `--audio-provider openai` (bien moins cher).

### Images

```bash
python app.py "Scénario" --images
python app.py --images-only --run-name <run>
```

Chaque acte peut fournir 1 à 3 prompts d'image ; les images sont générées en parallèle (3 max), puis insérées à un endroit pertinent du texte (JSON et Markdown mis à jour au fur et à mesure). `OPENAI_IMAGE_MODEL=gpt-image-1` est supporté.

### Lecteur web

```bash
python ui/server.py                      # http://127.0.0.1:8000
python ui/server.py --port 9000
```

- Écoute **uniquement en local** par défaut (`--host` pour changer, à vos risques).
- **Bibliothèque** : une carte par épisode (couverture, avancement sur 7 actes, médias, coût, badge « En cours » pendant la génération), recherche, et « Reprendre à l'acte N ».
- **Lecteur** : navigation par acte (flèches du clavier), barre de progression, arc narratif et scénario d'origine, sources, histoire bonus, lecteur audio et lecture vocale du navigateur.
- **Liens partageables** : `#/` (bibliothèque), `#/run/<nom>/acte-3`, `#/run/<nom>/bonus`. La position de lecture est mémorisée dans le navigateur.
- Aucune dépendance CDN : `marked`, DOMPurify et les polices sont dans `ui/vendor/`. Le contenu généré est assaini avant affichage.

Détails : [`ui/README.md`](ui/README.md).

## Structure d'un épisode

| Acte | Titre | Rôle |
|---|---|---|
| I | Le Signal | Introduction, réveil de l'intérêt |
| II | Le Décryptage | Explication scientifique |
| III | La Tension | Questions et tensions |
| IV | La Fiction | Segment fictionnel |
| V | Le Dialogue | Dialogue intérieur, réflexion |
| VI | La Mémoire | Pont entre les prédictions d'hier et le présent |
| VII | La Transmission | Question ouverte laissée au public |

Exemples de scénarios par thème : [`docs/scenarios.md`](docs/scenarios.md).

## Architecture

```
app.py                      point d'entrée → newtempsx/cli.py
newtempsx/
  cli.py                    arguments, modes, codes de sortie
  orchestrator.py           pipeline en 7 étapes (sorties structurées, session chaînée, retry, reprise)
  models.py                 modèles Pydantic (Episode, Act, schémas de sortie)
  exporters.py              JSON (écriture atomique) et Markdown
  audio_generator.py        TTS ElevenLabs / OpenAI
  image_generator.py        images OpenAI et intégration au texte
  http_utils.py             retries HTTP avec backoff
  validators.py             validation structurelle
ui/                         lecteur web local (server.py, index.html, styles.css, js/ modules ES, vendor/, tests/)
.claude/skills/             Skills de l'agent (un par rôle narratif)
tests/                      pytest
```

**Pipeline** : arc narratif → actes I-III → actes IV, V, VI, VII (un Skill chacun) → validation narrative → histoire bonus. Si la validation rejette l'épisode, **une** régénération est tentée avec des consignes renforcées (références vérifiées). Les Skills utilisent `WebFetch` et `WebSearch` pour actualiser les informations et vérifier les liens.

| Skill | Rôle |
|---|---|
| `narrative-conductor` | Arc narratif en 7 actes |
| `science-editor` | Actes I à III |
| `fiction-writer` | Acte IV |
| `dialogue` | Acte V |
| `archivist` | Acte VI |
| `audience` | Acte VII |
| `narrative-validator` | Cohérence narrative et validité des liens |
| `twilight-zone-writer` | Histoire bonus |

> **À fournir** : le Skill `twilight-zone-writer` s'appuie sur un fichier `twilight_zone_episodes.json` (référence des épisodes de la série) qui n'est pas versionné dans ce dépôt (`*.json` est ignoré par Git). Sans lui, le Skill ne peut pas lire cette référence : ajoutez-le à la racine du projet.

## Développement

```bash
uv sync --extra dev
uv run ruff check . && uv run ruff format --check .
uv run pytest
```

- La CI GitHub Actions exécute lint, format et tests sur Python 3.11 et 3.13.
- Les tests simulent les appels aux API (Claude, OpenAI, ElevenLabs) : un run complet avec de vraies clés reste la validation de bout en bout.
- Optionnel : `pre-commit install` (config ruff fournie).
- Front : `node ui/tests/e2e.mjs` (test E2E Playwright sur des données de démonstration) et `npx eslint -c ui/eslint.config.mjs ui/js` (identifiants non définis, imports).

## Dépannage

| Symptôme | Piste |
|---|---|
| Erreur d'authentification | Vérifiez Claude Code (souscription) ou `ANTHROPIC_API_KEY` |
| `Répertoire des Skills introuvable` | Lancez depuis la racine du projet ou utilisez `--project-root` |
| MP3 avec durée fausse | Installez **ffmpeg** (sinon concaténation binaire) |
| Codes de sortie 2 ou 3 | Épisode rejeté / sortie inexploitable : relancez, ou `--resume <run>` |
| Run non reprenable | Run créé avant `--resume` (pas de thèmes enregistrés) : régénérez |
| Pas d'audio dans le lecteur | Le bouton n'apparaît que si le fichier existe (`--audio` ou `--audio-only`) |

## Contribution

1. Forkez le dépôt et créez une branche (`git checkout -b feature/ma-fonctionnalite`).
2. Vérifiez `ruff` et `pytest` en local.
3. Ouvrez une Pull Request.

Bugs et idées : [issues GitHub](https://github.com/nmarchand73/new_tempsx/issues).

## Licence

Projet personnel. Pour toute demande d'utilisation, contactez le propriétaire du dépôt. Les polices embarquées dans `ui/vendor/fonts/` sont sous licence SIL OFL.
