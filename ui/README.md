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

