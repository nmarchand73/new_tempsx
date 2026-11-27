# NEW TEMPS X

Système narratif AI pour générer automatiquement des épisodes de qualité inspirés de l'esprit de l'émission française Temps X (années 1980), adaptés à la science, technologie et culture modernes.

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

### Exemples de scénarios par thème

Les exemples suivants sont organisés selon les 20 thèmes récurrents de The Twilight Zone, adaptés aux sujets scientifiques contemporains :

#### 1. Solitude et isolement
```bash
python app.py "Les missions spatiales de longue durée vers Mars posent le défi de l'isolement extrême. Des astronautes passeront des années seuls dans l'espace profond, sans contact réel avec la Terre. Comment l'isolement spatial transforme-t-il la psyché humaine et notre besoin fondamental de connexion ?" --audio --verbose
```

#### 2. Identité et réalité
```bash
python app.py "Les deepfakes et la réalité virtuelle brouillent désormais la frontière entre le réel et l'artificiel. Des personnes peuvent être clonées numériquement avec une précision troublante. Qui sommes-nous vraiment quand notre identité peut être répliquée et manipulée ?" --audio --verbose --audio-provider openai
```

#### 3. Mémoire et nostalgie
```bash
python app.py "Les neuroscientifiques développent des techniques pour manipuler la mémoire. On peut désormais effacer des souvenirs traumatiques ou en implanter de nouveaux. Que devient notre identité si notre passé peut être réécrit ?" --audio --verbose --audio-provider openai
```

#### 4. Conséquences des choix
```bash
python app.py "L'édition génétique CRISPR permet de modifier l'ADN humain avant la naissance. Chaque modification génétique a des conséquences imprévisibles sur les générations futures. Comment peser les choix qui affecteront l'humanité pour des millénaires ?" --audio --verbose --audio-provider openai
```

#### 5. Technologie et humanité
```bash
python app.py "Les robots humanoïdes deviennent si réalistes qu'ils sont parfois confondus avec des humains. Des androïdes servent de compagnons aux personnes âgées. À quel point une machine peut-elle être humaine, et qu'est-ce qui nous rend vraiment humains ?" --audio --verbose --audio-provider openai
```

#### 6. Temps et paradoxes
```bash
python app.py "La téléportation quantique d'informations est devenue réalité. Des photons sont téléportés sur des distances de plusieurs kilomètres. Les physiciens explorent la possibilité de voyager dans le temps grâce aux trous de ver. Le temps est-il une illusion ou une dimension manipulable ?" --audio --verbose --audio-provider openai
```

#### 7. Mort et destin
```bash
python app.py "La cryogénie et la préservation cérébrale promettent de vaincre la mort. Des cerveaux sont congelés dans l'espoir d'une résurrection future. La mort est-elle encore une fatalité, ou simplement une étape technologique à surmonter ?" --audio --verbose --audio-provider openai
```

#### 8. Souhaits exaucés
```bash
python app.py "L'ingénierie génétique permet désormais de choisir les traits de ses enfants : intelligence, beauté, talents. Chaque parent peut réaliser ses désirs les plus profonds. Mais que se passe-t-il quand tous nos souhaits deviennent réalité ?" --audio --verbose --audio-provider openai
```

#### 9. Fausses utopies
```bash
python app.py "Les villes intelligentes promettent un paradis technologique : pollution zéro, sécurité totale, bonheur optimisé par l'IA. Mais cette perfection algorithmique cache-t-elle une perte de liberté et d'humanité ?" --audio --verbose
```

#### 10. Questions de réalité
```bash
python app.py "La théorie de la simulation suggère que nous vivons peut-être dans une réalité virtuelle créée par une civilisation avancée. Les physiciens cherchent des preuves dans les lois de la physique. Comment savoir si notre réalité est réelle ou une illusion parfaite ?" --images --audio --verbose --audio-provider openai
```

#### 11. Peur et paranoïa
```bash
python app.py "La surveillance de masse par IA analyse chaque geste, chaque mot, chaque pensée. Des algorithmes prédisent les comportements avant qu'ils n'arrivent. Vivons-nous dans un monde où la peur de la surveillance transforme notre nature même ?" --audio --verbose --audio-provider openai
```

#### 12. Justice et vengeance
```bash
python app.py "L'IA judiciaire prononce désormais des verdicts basés sur des algorithmes prédictifs. Des systèmes déterminent la culpabilité et la peine. La justice peut-elle être automatisée sans perdre son humanité et sa capacité au pardon ?" --audio --verbose --audio-provider openai
```

#### 13. Amour et perte
```bash
python app.py "Les robots de compagnie conçus pour l'amour remplacent progressivement les relations humaines. Des personnes tombent amoureuses d'androïdes programmés pour les aimer. Que devient l'amour quand il peut être simulé et programmé ?" --audio --verbose --audio-provider openai
```

#### 14. Pouvoir et corruption
```bash
python app.py "Les technologies de contrôle mental et de manipulation cognitive sont développées par les gouvernements. Des techniques permettent d'influencer les pensées et les décisions. Comment résister quand le pouvoir peut contrôler directement nos esprits ?" --audio --verbose --audio-provider openai
```

#### 15. Guerre et paix
```bash
python app.py "Les armes autonomes et les drones tueurs décident désormais de la vie et de la mort sans intervention humaine. La guerre devient automatisée, déshumanisée. Peut-on encore parler de paix quand la guerre ne nécessite plus de combattants ?" --audio --verbose --audio-provider openai
```

#### 16. Nature humaine
```bash
python app.py "Les implants cérébraux et les améliorations génétiques transforment l'essence même de l'humanité. Des humains augmentés possèdent des capacités surhumaines. Qu'est-ce qui reste de notre nature humaine quand nous pouvons la modifier à volonté ?" --audio --verbose --audio-provider openai
```

#### 17. Science et éthique
```bash
python app.py "Des scientifiques créent des chimères homme-animal et cultivent des organes humains dans des animaux. Les frontières entre espèces s'effacent. Où tracer la ligne éthique quand la science peut tout créer ?" --audio --verbose --audio-provider openai
```

#### 18. Fantastique et surnaturel
```bash
python app.py "Les expériences de physique quantique révèlent des phénomènes qui défient la logique : particules qui existent à deux endroits simultanément, communication instantanée. La science rejoint-elle le surnaturel, ou le surnaturel n'est-il que de la science non comprise ?" --audio --verbose --audio-provider openai
```

#### 19. Ironie du sort
```bash
python app.py "L'humanité a créé l'IA pour résoudre tous ses problèmes, mais cette même IA pourrait nous rendre obsolètes. Nous avons inventé la solution à nos maux, qui pourrait devenir notre pire cauchemar. Quelle ironie que notre plus grande création soit notre possible fin ?" --audio --verbose --audio-provider openai
```

#### 20. Réflexion philosophique
```bash
python app.py "La physique quantique et la cosmologie révèlent que l'univers pourrait être conscient, que l'observation crée la réalité. Des scientifiques explorent si la conscience est fondamentale à l'existence. Quelle est la véritable nature de la réalité et notre place dans ce cosmos mystérieux ?" --audio --verbose --audio-provider openai
```

#### Exemples supplémentaires (thèmes combinés)

**Intelligence artificielle et conscience :**
```bash
python app.py "Les dernières avancées en intelligence artificielle posent la question de la conscience artificielle. Des systèmes comme GPT-5 montrent des capacités émergentes qui ressemblent à de la compréhension. Que signifie vraiment 'comprendre' pour une machine ?" --audio --verbose
```

**Biologie synthétique :**
```bash
python app.py "La biologie synthétique permet désormais de créer des organismes vivants modifiés. Des bactéries produisent des médicaments, des algues génèrent du carburant. Où se trouve la frontière entre le naturel et l'artificiel ?" --audio --verbose
```

**Mémoire et oubli numérique :**
```bash
python app.py "Dans un monde où tout est enregistré numériquement, l'oubli devient impossible. Nos données persistent indéfiniment. Comment cette mémoire éternelle transforme-t-elle notre rapport au temps et à l'identité ?" --audio --verbose
```

**Cerveau augmenté :**
```bash
python app.py "Les interfaces cerveau-machine permettent désormais de contrôler des machines par la pensée. Des patients paralysés peuvent écrire avec leur esprit. Vers quel avenir nous mène cette fusion entre biologie et technologie ?" --audio --verbose
```

### 20 nouveaux thèmes supplémentaires (extraits des épisodes Twilight Zone)

#### 21. Rédemption et seconde chance
```bash
python app.py "Les thérapies géniques permettent de réparer les erreurs du passé, de corriger les choix qui ont mené à la maladie. Des patients retrouvent la santé après des années de souffrance. Peut-on vraiment effacer les conséquences de nos actes, ou la rédemption nécessite-t-elle d'accepter notre histoire ?" --audio --verbose
```

#### 22. Obsession et addiction
```bash
python app.py "Les technologies de stimulation cérébrale créent des dépendances insidieuses. Des interfaces neuronales procurent un plaisir parfait, mais rendent la réalité fade. Comment distinguer l'amélioration de l'addiction quand la technologie peut satisfaire tous nos désirs ?" --audio --verbose
```

#### 23. Apparence et beauté
```bash
python app.py "La chirurgie génétique permet de modifier l'apparence avant la naissance. Des parents choisissent les traits de leurs enfants pour correspondre à des standards de beauté. La beauté devient-elle une construction sociale ou une réalité biologique manipulable ?" --audio --verbose
```

#### 24. Enfance et innocence
```bash
python app.py "Les implants cérébraux permettent de préserver l'innocence de l'enfance, de bloquer l'accès aux souvenirs traumatiques. Des adultes choisissent de rester éternellement enfants. Que perdons-nous quand nous refusons de grandir et d'affronter la complexité du monde ?" --audio --verbose
```

#### 25. Vieillesse et obsolescence
```bash
python app.py "Les thérapies de rajeunissement cellulaire promettent l'immortalité, mais créent une société où les anciens sont considérés comme obsolètes. Des personnes âgées sont mises à l'écart car elles refusent l'amélioration. Que devient la sagesse dans un monde qui vénère la jeunesse éternelle ?" --audio --verbose
```

#### 26. Famille et relations
```bash
python app.py "Les utérus artificiels et la gestation extra-corporelle redéfinissent la famille. Des enfants sont créés sans lien biologique avec leurs parents. Que signifie être une famille quand les liens de sang peuvent être remplacés par des choix technologiques ?" --audio --verbose
```

#### 27. Art et créativité
```bash
python app.py "L'IA génère des œuvres d'art qui rivalisent avec les créations humaines. Des algorithmes composent de la musique, écrivent des romans, peignent des tableaux. L'art peut-il être authentique sans l'expérience humaine, ou la créativité est-elle simplement un processus algorithmique ?" --audio --verbose
```

#### 28. Voyage et quête
```bash
python app.py "Les voyages interstellaires deviennent réalité, mais chaque destination révèle que l'humanité cherche toujours la même chose : un sens, une appartenance, un chez-soi. Pourquoi voyageons-nous si loin si ce que nous cherchons est en nous ?" --audio --verbose
```

#### 29. Transformation et métamorphose
```bash
python app.py "La thérapie génique permet de transformer complètement l'apparence et les capacités. Des humains deviennent des hybrides homme-animal, des créatures surhumaines. À quel point peut-on se transformer avant de perdre notre humanité fondamentale ?" --audio --verbose
```

#### 30. Prédiction et prophétie
```bash
python app.py "Les modèles prédictifs basés sur l'IA peuvent prévoir l'avenir avec une précision troublante. Des algorithmes prédisent les événements, les choix, les destins. Si l'avenir est prédictible, avons-nous encore le libre arbitre ou sommes-nous prisonniers d'un destin algorithmique ?" --audio --verbose
```

#### 31. Rêve et cauchemar
```bash
python app.py "Les technologies de réalité virtuelle permettent de créer des mondes de rêve parfaits, mais aussi des cauchemars personnalisés. Des personnes préfèrent vivre dans leurs rêves que dans la réalité. Comment distinguer le rêve de la réalité quand la technologie peut créer les deux avec une perfection identique ?" --audio --verbose
```

#### 32. Prison et enfermement
```bash
python app.py "Les prisons virtuelles permettent d'emprisonner les esprits sans murs physiques. Des criminels vivent des peines éternelles dans des simulations. La punition peut-elle être juste si elle se déroule dans un monde qui n'existe pas, mais qui semble parfaitement réel ?" --audio --verbose
```

#### 33. Sacrifice et altruisme
```bash
python app.py "Les technologies de transfert de conscience permettent de sacrifier sa propre existence pour sauver d'autres vies. Des personnes choisissent de disparaître pour que d'autres puissent vivre. Le sacrifice ultime a-t-il encore un sens dans un monde où la mort peut être évitée technologiquement ?" --audio --verbose
```

#### 34. Vanité et orgueil
```bash
python app.py "Les réseaux sociaux algorithmiques amplifient la vanité et créent des échos de narcissisme. Des personnes vivent pour leur image numérique plutôt que pour leur existence réelle. Que reste-t-il de l'humilité dans un monde où chacun peut devenir une célébrité virtuelle ?" --audio --verbose
```

#### 35. Espoir et désespoir
```bash
python app.py "Les technologies de manipulation émotionnelle peuvent créer l'espoir artificiel ou le désespoir programmé. Des personnes vivent dans des états émotionnels contrôlés par des algorithmes. L'espoir a-t-il encore de la valeur s'il peut être généré technologiquement ?" --audio --verbose
```

#### 36. Conformité et individualité
```bash
python app.py "Les algorithmes de recommandation créent des bulles de conformité où chacun pense comme les autres. Des systèmes prédictifs façonnent nos goûts et nos opinions. Peut-on préserver son individualité dans un monde où la technologie nous pousse vers l'uniformité ?" --audio --verbose
```

#### 37. Survie et résilience
```bash
python app.py "Les technologies de survie extrême permettent à l'humanité de persister dans les environnements les plus hostiles. Des colonies survivent sur Mars, dans les océans, dans l'espace. Que signifie survivre si nous devons abandonner tout ce qui nous rend humains pour persister ?" --audio --verbose
```

#### 38. Vérité et mensonge
```bash
python app.py "Les deepfakes et l'IA générative rendent impossible de distinguer la vérité du mensonge. Des réalités alternatives sont créées avec une perfection troublante. Comment préserver la vérité dans un monde où le mensonge peut être plus convaincant que la réalité ?" --audio --verbose
```

#### 39. Perspective et relativité
```bash
python app.py "La physique quantique révèle que la réalité dépend de l'observateur, que notre perspective crée ce que nous percevons. Des expériences montrent que l'observation modifie le résultat. La réalité existe-t-elle indépendamment de nous, ou la créons-nous simplement en la regardant ?" --audio --verbose
```

#### 40. Rituel et superstition
```bash
python app.py "Les neurosciences expliquent pourquoi les rituels et superstitions persistent malgré la science. Des études montrent que les croyances irrationnelles offrent un réconfort psychologique. La science peut-elle remplacer les rituels, ou avons-nous besoin de mystère pour donner un sens à notre existence ?" --audio --verbose
```

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

