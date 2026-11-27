# UI NEW TEMPS X

Interface web moderne pour visualiser les épisodes NEW TEMPS X.

## Fonctionnalités

- 📖 Affichage immersif des 7 actes narratifs
- 🎯 Navigation fluide entre les actes
- 📊 Vue d'ensemble avec l'arc narratif
- ⌨️ Navigation au clavier (flèches gauche/droite)
- 🎨 Design moderne inspiré de l'esprit Temps X
- 📱 Responsive design

## Utilisation

### Option 1: Serveur Python (Recommandé)

```bash
# Depuis la racine du projet
cd ui
python server.py
```

Puis ouvrez votre navigateur sur: http://localhost:8000

### Option 2: Ouverture directe

Vous pouvez aussi ouvrir directement `index.html` dans votre navigateur, mais vous devrez peut-être ajuster le chemin vers `episode.json` dans `app.js`.

## Structure

```
ui/
├── index.html      # Structure HTML
├── styles.css      # Styles et design
├── app.js          # Logique JavaScript
├── server.py       # Serveur Python simple
└── README.md       # Ce fichier
```

## Personnalisation

Les couleurs et styles peuvent être modifiés dans `styles.css` via les variables CSS dans `:root`.


## Design et dépendances front

- Aucun appel à un CDN : `marked`, DOMPurify et les polices (Fraunces, Source Serif 4, IBM Plex Mono, sous licence OFL) sont dans `ui/vendor/` — l'UI fonctionne hors ligne et sans hash SRI à maintenir.
- Thème sombre par défaut, thème clair automatique (`prefers-color-scheme`). Les couleurs et polices sont des variables CSS en tête de `styles.css`.
- Respecte `prefers-reduced-motion` et propose une feuille d'impression (navigation et boutons masqués).

## Organisation du code (`ui/js/`)

Modules ES sans étape de build, état partagé dans `state.js` :

| Module | Rôle |
|---|---|
| `main.js` | Initialisation, dialogue « Nouvel épisode » |
| `router.js` | Routage par hash (`#/`, `#/run/<nom>/acte-N`, `/bonus`), ouverture d'un run, rafraîchissement de la bibliothèque |
| `library.js` | Cartes d'épisodes, recherche, états vides |
| `runs.js` | Chargement des runs et de l'épisode, polling pendant la génération |
| `render.js` | Hero, arc narratif, cartes d'actes, histoire bonus, erreurs |
| `navigation.js` | Navigation entre actes, détection au scroll, progression, position dans l'URL |
| `audio.js` / `speech.js` | Lecture des MP3 / synthèse vocale du navigateur |
| `lightbox.js` | Images et visionneuse |
| `storage.js` | Progression de lecture (localStorage, tolérant à son absence) |
| `config.js`, `utils.js` | Constantes, Markdown assaini, échappement |

## Tests

```bash
node ui/tests/e2e.mjs                                   # E2E Playwright (démarre son propre serveur et ses données)
npx eslint -c ui/eslint.config.mjs ui/js                # contrôle statique (eslint + globals)
```
