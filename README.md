# NEW TEMPS X

Système narratif AI pour générer automatiquement des épisodes de qualité inspirés de l'esprit de l'émission française Temps X (années 1980), adaptés à la science, technologie et culture modernes.

## Démarrage rapide

```bash
git clone https://github.com/nmarchand73/new_tempsx.git && cd new_tempsx
uv sync --extra dev            # ou: pip install -e ".[dev]"
python app.py "Votre scénario" # génère output/<run>/ (JSON + Markdown)
python ui/server.py            # visualisation sur http://127.0.0.1:8000
```

Options utiles : `--audio` (TTS), `--images`, `--twilight-only`, `--audio-only --run-name <run>`, `--verbose`.
Qualité : `uv run ruff check . && uv run pytest`. Le détail de l'installation et de la configuration suit.

## 📦 Dépôt GitHub

Le projet est disponible sur GitHub : [https://github.com/nmarchand73/new_tempsx](https://github.com/nmarchand73/new_tempsx)

Pour cloner le projet :
```bash
git clone https://github.com/nmarchand73/new_tempsx.git
cd new_tempsx
```

## Prérequis

Le SDK utilise **Claude Code comme runtime**. Vous avez deux options d'authentification :

### Option A : Utiliser Claude Code avec souscription (Recommandé) ⭐

Si vous avez une **souscription Claude Code active**, vous n'avez **pas besoin** de configurer une API key. Le SDK utilisera automatiquement votre souscription.

**Installation de Claude Code :**

**macOS/Linux/WSL:**
```bash
curl -fsSL https://claude.ai/install.sh | bash
```

**Homebrew:**
```bash
brew install --cask claude-code
```

**npm:**
```bash
npm install -g @anthropic-ai/claude-code
```

Voir [Claude Code setup](https://docs.anthropic.com/en/docs/claude-code/setup) pour Windows et autres options.

**Avantages :**
- ✅ Pas besoin de gérer une API key
- ✅ Utilise votre quota de souscription
- ✅ Configuration plus simple

### Option B : Utiliser une API Key

Si vous préférez utiliser une API key (ou n'avez pas de souscription Claude Code), vous pouvez configurer `ANTHROPIC_API_KEY` dans votre fichier `.env` (voir section Configuration ci-dessous).

**Note** : Les Skills utilisent les outils **WebFetch** et **WebSearch** pour rechercher et vérifier du contenu web (`allowed_tools=["Skill", "Read", "WebFetch", "WebSearch"]`). Chaque étape retourne une sortie structurée (JSON Schema) et les étapes sont chaînées dans une même session. Variables optionnelles : `NEWTEMPSX_MODEL` (modèle Claude) et `NEWTEMPSX_MAX_BUDGET_USD` (budget max par étape). Le coût total est affiché en fin de génération.

Le serveur UI (`python ui/server.py`) écoute par défaut sur `127.0.0.1` uniquement (`--host`, `--port` pour changer). Tests : `pip install -e ".[dev]" && pytest`.

Audio/images : les appels OpenAI/ElevenLabs sont réessayés automatiquement (429/5xx, backoff), exécutés en parallèle (3 simultanés) et les MP3 longs sont concaténés avec **ffmpeg** s'il est installé (recommandé). Modèles configurables via `OPENAI_IMAGE_MODEL` et `OPENAI_TTS_MODEL`.

## Installation

```bash
pip install -e .
```

## Configuration

### Option 1 : Utiliser Claude Code avec souscription (Recommandé)

Si vous avez **Claude Code installé avec une souscription active**, vous n'avez **pas besoin** de configurer une API key. Le SDK utilisera automatiquement votre souscription Claude Code.

**Avantages :**
- Pas besoin de gérer une API key
- Utilise votre quota de souscription Claude Code
- Plus simple à configurer

**Vérification :** Assurez-vous que Claude Code est installé et que vous êtes connecté avec une souscription active.

### Option 2 : Utiliser une API Key

Si vous préférez utiliser une API key (ou si vous n'avez pas de souscription Claude Code) :

1. Créez un fichier `.env` à la racine du projet :
```bash
# Sur Linux/Mac
cp env.example .env

# Sur Windows PowerShell
Copy-Item env.example .env
```

2. Éditez `.env` et ajoutez votre clé API Anthropic :
```
ANTHROPIC_API_KEY=your-api-key-here
```

Vous pouvez obtenir votre clé sur [console.anthropic.com](https://console.anthropic.com/).

**Alternative :** Vous pouvez aussi définir la variable d'environnement directement :
```bash
export ANTHROPIC_API_KEY=your-api-key
```

**Note :** Si vous avez à la fois une souscription Claude Code active ET une API key configurée, le SDK utilisera l'API key en priorité.

## Usage

### Génération d'un épisode (sans audio)

Pour générer uniquement l'épisode (texte et structure, sans audio) :

```bash
# Avec scénario personnalisé
python app.py "Votre scénario ici"

# Sans scénario (utilise le scénario par défaut)
python app.py

# Avec logs détaillés
python app.py "Votre scénario ici" --verbose

# Avec répertoire de sortie personnalisé
python app.py "Votre scénario ici" --output-dir custom_output
```

Cela génère :
- ✅ L'épisode complet avec 7 actes
- ✅ L'histoire bonus Twilight Zone
- ✅ Les fichiers JSON et Markdown
- ❌ Pas de fichiers audio (plus rapide, pas besoin de clés API TTS)

### Génération d'un épisode avec audio

Pour générer l'épisode avec les fichiers audio :

```bash
# Avec ElevenLabs (meilleure qualité, recommandé)
python app.py "Votre scénario ici" --audio

# Avec OpenAI TTS (alternative économique)
python app.py "Votre scénario ici" --audio --audio-provider openai

# Avec toutes les options
python app.py "Scénario" --output-dir custom_output --audio --verbose

# Avec nom de run personnalisé
python app.py "Scénario" --run-name mon-episode-personnalise --audio

# Génération uniquement de l'histoire Twilight Zone
python app.py "Scénario" --twilight-only
```

**Options disponibles :**
- `scenario` : Texte du scénario (positionnel, optionnel) - Si non fourni, utilise le scénario par défaut
- `--output-dir, -o` : Répertoire de sortie (défaut: `output`)
- `--project-root, -p` : Racine du projet pour charger les Skills (défaut: répertoire courant)
- `--verbose, -v` : Affiche les logs détaillés (mode DEBUG)
- `--audio, -a` : Génère également les fichiers audio pour chaque acte
- `--audio-provider` : Provider TTS (`elevenlabs` ou `openai`, défaut: `elevenlabs`)
- `--run-name` : Nom personnalisé pour ce run (défaut: généré automatiquement à partir du scénario)
- `--twilight-only` : Génère uniquement l'histoire bonus Twilight Zone (sans générer l'épisode complet)
- `--audio-only` : Génère uniquement les fichiers audio pour un épisode existant (nécessite `--run-name`)

Cela génère un épisode complet avec 7 actes et une histoire bonus Twilight Zone dans un répertoire de run nommé explicitement (ex: `output/intelligence_artificielle_conscience_20241213_182524/`).

**Structure d'un run :**
```
output/nom-du-run/
├── episode.json          # Épisode complet avec métadonnées
├── episode.md            # Version Markdown complète
├── act-I.md              # Acte I (exporté progressivement)
├── act-II.md             # Acte II
├── ...
├── act-VII.md            # Acte VII
├── twilight-zone-story.md # Histoire bonus Twilight Zone
└── audio/                # Fichiers audio (si --audio activé)
    ├── act-I.mp3
    ├── act-II.mp3
    └── ...
```

**Aide complète :**
```bash
python app.py --help
```

Cette commande affiche toutes les options disponibles avec leurs descriptions détaillées.

### Visualisation de l'épisode (UI)

Une interface web moderne est disponible pour visualiser les épisodes générés :

```bash
cd ui
python server.py
```

Puis ouvrez votre navigateur sur **http://localhost:8000**

L'UI offre :
- 📖 Affichage immersif des 7 actes narratifs
- 🎯 Navigation fluide entre les actes
- 📊 Vue d'ensemble avec l'arc narratif
- ⌨️ Navigation au clavier (flèches gauche/droite)
- 🎨 Design moderne inspiré de l'esprit Temps X
- 📁 **Sélection de runs** : Chaque génération crée un run avec un nom explicite basé sur le scénario
- 🎧 **Audio intelligent** : Les boutons audio sont automatiquement désactivés si le fichier n'est pas disponible
- 🌟 **Histoire bonus Twilight Zone** : Chaque épisode inclut une nouvelle complète (2000-4000 mots) style Twilight Zone, accessible via le bouton "🌟 Bonus"

**Gestion des runs :**
- Chaque génération crée un répertoire de run avec un nom explicite basé sur le scénario (ex: `intelligence_artificielle_conscience_20241213_182524`)
- Les runs sont organisés dans `output/` (ou le répertoire spécifié avec `--output-dir`)
- Le nom du run est généré automatiquement à partir du scénario, ou peut être personnalisé avec `--run-name`
- L'UI permet de sélectionner et visualiser n'importe quel run précédent
- Les runs affichent le titre de l'épisode, la date de création et un indicateur pour le plus récent

Voir `ui/README.md` pour plus de détails.

### Génération uniquement de l'histoire Twilight Zone

Pour générer uniquement l'histoire bonus Twilight Zone (sans générer l'épisode complet) :

```bash
# Génère uniquement l'histoire Twilight Zone
python app.py "Votre scénario ici" --twilight-only

# Avec logs détaillés
python app.py "Votre scénario ici" --twilight-only --verbose
```

Cela génère uniquement :
- ✅ L'histoire bonus Twilight Zone (2000-4000 mots)
- ✅ Un fichier JSON minimal pour l'UI
- ❌ Pas d'épisode complet (plus rapide)

### Génération Audio (optionnel)

Vous pouvez générer des versions audio de chaque acte avec les meilleures APIs TTS du marché :

```bash
# Avec ElevenLabs (meilleure qualité, recommandé)
python app.py "Votre scénario ici" --audio

# Avec OpenAI TTS (alternative économique)
python app.py "Votre scénario ici" --audio --audio-provider openai

# Avec nom de run personnalisé
python app.py "Votre scénario ici" --audio --run-name mon-episode
```

**Configuration :**
- **ElevenLabs** : Ajoutez `ELEVENLABS_API_KEY=your-key` dans `.env`
- **OpenAI** : Ajoutez `OPENAI_API_KEY=your-key` dans `.env`

**Réduction des coûts ElevenLabs :**
Pour réduire les coûts (~40% d'économie), ajoutez dans `.env` :
```bash
ELEVENLABS_COST_OPTIMIZED=true
```
Cela active le mode économique qui :
- Utilise le modèle `eleven_turbo_v2_5` (plus rapide et moins cher)
- Réduit `similarity_boost` (économise des crédits)
- Désactive `use_speaker_boost` (économise des crédits)
- Qualité légèrement réduite mais toujours excellente

**Autres stratégies pour réduire les coûts :**
1. **Utiliser le cache** : Les fichiers audio sont mis en cache automatiquement
2. **Utiliser OpenAI TTS** : Alternative économique (~20x moins cher) avec `--audio-provider openai`
3. **Générer uniquement certains actes** : Modifiez le code pour générer seulement les actes importants
4. **Optimiser le texte** : Réduire les répétitions et phrases longues avant génération

Les fichiers audio sont générés dans `output/nom-du-run/audio/` et peuvent être lus directement dans l'UI.

**Générer l'audio pour un épisode existant :**

La méthode recommandée est d'utiliser l'option `--audio-only` :

```bash
# Génère uniquement l'audio pour un épisode existant
python app.py --audio-only --run-name nom-de-l-episode

# Avec provider spécifique
python app.py --audio-only --run-name nom-de-l-episode --audio-provider openai

# Avec répertoire de sortie personnalisé
python app.py --audio-only --run-name nom-de-l-episode --output-dir custom_output
```

**Note :** L'option `--audio-only` nécessite que l'épisode existe déjà dans le répertoire spécifié. Le nom du run doit correspondre au nom du dossier contenant `episode.json`.

**Alternative (régénération complète) :**
```bash
# Régénère l'épisode complet avec audio (si vous avez le scénario original)
python app.py "Votre scénario" --audio --run-name nom-de-l-episode
```

Voir `README_AUDIO.md` pour plus de détails.

### Progression affichée

Les logs affichent la progression de chaque étape :
- 📐 Définition de l'arc narratif
- 🔬 Génération des Actes I-III
- ✍️ Génération de l'Acte IV (Fiction)
- 💭 Génération de l'Acte V (Dialogue)
- 📚 Génération de l'Acte VI (Mémoire)
- 🎯 Génération de l'Acte VII (Transmission)
- 🌟 Génération de l'histoire bonus Twilight Zone
- 🔍 Validation narrative
- 💾 Export progressif des fichiers (JSON, Markdown, Audio)

**Export progressif :** Les fichiers sont créés au fur et à mesure de la génération :
- L'arc narratif est exporté dès qu'il est défini
- Chaque acte est exporté en Markdown dès qu'il est généré
- Le JSON est mis à jour progressivement
- L'histoire bonus Twilight Zone est exportée séparément

### Exemples de scénarios

40 exemples de scénarios par thème : voir [docs/scenarios.md](docs/scenarios.md).


## Structure

Chaque épisode suit une structure narrative stricte en 7 actes :

1. **Acte I — Le Signal (Awaken)** - Introduction, réveil de l'intérêt
2. **Acte II — Le Décryptage (Explain)** - Explication scientifique
3. **Acte III — La Tension (Question)** - Questions, tensions
4. **Acte IV — La Fiction (Feel)** - Segment fictionnel
5. **Acte V — Le Dialogue (Reflect)** - Réflexion
6. **Acte VI — La Mémoire (Remember)** - Connexion passé/présent
7. **Acte VII — La Transmission (Open)** - Question ouverte finale

## Architecture

```
app.py                   point d'entrée mince -> newtempsx/cli.py
newtempsx/cli.py         arguments, modes (épisode, twilight-only, audio-only, images-only), codes de sortie
newtempsx/orchestrator.py pipeline en 7 étapes: sorties structurées + session chaînée, retry sur rejet
newtempsx/models.py      modèles Pydantic (Episode, Act, schémas des sorties structurées)
newtempsx/audio_generator.py / image_generator.py   TTS et images (retries, parallélisme borné)
newtempsx/http_utils.py  retries HTTP avec backoff
ui/server.py + ui/app.js visualisation locale (lecture seule)
```

Le système utilise Claude Agents SDK avec des Skills spécialisés :
- `narrative-conductor` - Orchestre l'arc narratif (utilise recherche web/YouTube)
- `science-editor` - Explique les concepts scientifiques pour les Actes I-III (utilise recherche web/YouTube)
- `fiction-writer` - Écrit la fiction pour l'Acte IV (utilise recherche web/YouTube pour inspiration)
- `dialogue` - Crée la réflexion intime et le dialogue intérieur pour l'Acte V (utilise recherche web/YouTube)
- `archivist` - Connecte passé/présent pour l'Acte VI (utilise recherche web/YouTube pour archives)
- `audience` - Crée la question ouverte finale pour l'Acte VII (utilise recherche web/YouTube pour actualité)
- `narrative-validator` - Valide la cohérence narrative
- `twilight-zone-writer` - Génère une nouvelle complète (2000-4000 mots) style Twilight Zone inspirée par le sujet de l'épisode

**Recherche et enrichissement** : Chaque Skill utilise des outils de recherche web et YouTube pour :
- Actualiser les informations scientifiques
- Trouver des exemples concrets et applications réelles
- Accéder aux archives et prédictions passées
- Identifier les débats et questions ouvertes actuels

**Histoire bonus Twilight Zone :**
- Chaque épisode inclut une nouvelle complète et autonome (2000-4000 mots)
- Inspirée par le sujet scientifique/technologique de l'épisode
- Explore les implications philosophiques et humaines
- Style authentique de Rod Serling avec twist inattendu
- Référence obligatoire : `twilight_zone_episodes.json` (156 épisodes authentiques)
- Accessible dans l'UI via le bouton "🌟 Bonus"

## 🤝 Contribution

Les contributions sont les bienvenues ! Pour contribuer au projet :

1. Forkez le dépôt
2. Créez une branche pour votre fonctionnalité (`git checkout -b feature/ma-fonctionnalite`)
3. Committez vos changements (`git commit -m 'Ajout d'une nouvelle fonctionnalité'`)
4. Poussez vers la branche (`git push origin feature/ma-fonctionnalite`)
5. Ouvrez une Pull Request

## 📝 Licence

Ce projet est un projet personnel. Pour toute question ou demande d'utilisation, veuillez contacter le propriétaire du dépôt.

## 🐛 Support

Pour signaler un bug ou proposer une amélioration, veuillez ouvrir une [issue](https://github.com/nmarchand73/new_tempsx/issues) sur GitHub.

