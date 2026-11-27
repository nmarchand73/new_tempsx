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
