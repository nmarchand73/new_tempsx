// Configuration
const ACT_NAMES = {
    'acte_1': 'Le Signal',
    'acte_2': 'Le Décryptage',
    'acte_3': 'La Tension',
    'acte_4': 'La Fiction',
    'acte_5': 'Le Dialogue',
    'acte_6': 'La Mémoire',
    'acte_7': 'La Transmission'
};

const ACT_NUMBERS = {
    'acte_1': 'I',
    'acte_2': 'II',
    'acte_3': 'III',
    'acte_4': 'IV',
    'acte_5': 'V',
    'acte_6': 'VI',
    'acte_7': 'VII'
};

// État de l'application
let currentEpisode = null;
let currentActIndex = 0;
let allActs = [];
let audioPlayers = {}; // Cache des lecteurs audio
let currentRunName = null;
let availableRuns = [];
let speechSynthesis = null; // API de synthèse vocale
let currentUtterance = null; // Utterance en cours
let currentSpeechIndex = -1; // Index de l'acte en cours de lecture
let speechPaused = false; // État de pause

// Initialisation
document.addEventListener('DOMContentLoaded', async () => {
    // Vérifier le support de la synthèse vocale
    if ('speechSynthesis' in window) {
        speechSynthesis = window.speechSynthesis;
        console.log('Synthèse vocale disponible');
    } else {
        console.warn('Synthèse vocale non disponible dans ce navigateur');
    }
    
    // Initialiser la lightbox
    initializeLightbox();
    
    await loadRuns();
    setupRunSelector();
    
    // Charger l'épisode seulement si un run est disponible
    if (currentRunName) {
        await loadEpisode();
        setupNavigation();
        renderOverview();
        renderActs();
        updateNavigation();
    } else {
        showError('Aucun run disponible. Générez d\'abord un épisode avec: python app.py "Votre scénario"');
    }
});

// Charger la liste des runs disponibles
async function loadRuns() {
    try {
        const response = await fetch('/api/runs');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        availableRuns = await response.json();
        console.log('Runs disponibles:', availableRuns);
        
        // Sélectionner le run le plus récent par défaut
        if (availableRuns.length > 0) {
            currentRunName = availableRuns[0].name;
        }
    } catch (error) {
        console.error('Erreur lors du chargement des runs:', error);
        availableRuns = [];
    }
}

// Configurer le sélecteur de run
function setupRunSelector() {
    const selector = document.getElementById('run-selector');
    
    // Remplir le sélecteur avec les runs disponibles
    selector.innerHTML = '';
    if (availableRuns.length === 0) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = 'Aucun run disponible';
        selector.appendChild(option);
        selector.disabled = true;
    } else {
        selector.disabled = false;
        availableRuns.forEach((run, index) => {
            const option = document.createElement('option');
            option.value = run.name;
            
            // Formater l'affichage : titre de l'épisode en priorité
            let displayText = run.title || run.name;
            
            // Si le titre est le même que le nom, essayer d'extraire une partie plus lisible
            if (displayText === run.name && run.scenario) {
                // Utiliser le début du scénario si disponible
                const scenarioPreview = run.scenario.replace(/\.\.\.$/, '').trim();
                if (scenarioPreview.length > 0) {
                    displayText = scenarioPreview.length > 40 
                        ? scenarioPreview.substring(0, 40) + '...' 
                        : scenarioPreview;
                }
            }
            
            // Ajouter la date si disponible
            if (run.date) {
                displayText = `${displayText} (${run.date})`;
            }
            
            // Ajouter un indicateur si c'est le plus récent
            if (index === 0) {
                displayText = `⭐ ${displayText}`;
            }
            
            option.textContent = displayText;
            option.title = `Run: ${run.name}\nTitre: ${run.title || 'Sans titre'}\nDate: ${run.date || 'Inconnue'}\nScénario: ${run.scenario || 'Pas de scénario'}`;
            
            if (run.name === currentRunName) {
                option.selected = true;
            }
            selector.appendChild(option);
        });
    }
    
    // Écouter les changements de sélection
    selector.addEventListener('change', async (e) => {
        currentRunName = e.target.value;
        if (currentRunName) {
            // Réinitialiser l'état
            currentEpisode = null;
            allActs = [];
            currentActIndex = 0;
            // Arrêter tous les lecteurs audio
            Object.values(audioPlayers).forEach(audio => {
                audio.pause();
                audio.currentTime = 0;
            });
            audioPlayers = {};
            
            // Arrêter la synthèse vocale
            stopSpeech();
            
            await loadEpisode();
            if (currentEpisode) {
                renderOverview();
                renderActs();
                updateNavigation();
                renderTwilightZoneStory();
            }
        } else {
            showError('Aucun run sélectionné');
        }
    });
}

// Charger l'épisode depuis le JSON
async function loadEpisode() {
    if (!currentRunName) {
        console.warn('Aucun run sélectionné, impossible de charger l\'épisode');
        showError('Aucun run sélectionné. Sélectionnez un run dans le menu déroulant.');
        return;
    }
    
    try {
        // Construire l'URL avec le paramètre run
        const url = `/api/episode.json?run=${encodeURIComponent(currentRunName)}`;
        
        const response = await fetch(url);
        if (!response.ok) {
            if (response.status === 404) {
                throw new Error(`Run "${currentRunName}" introuvable`);
            }
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        currentEpisode = await response.json();
        
        // Vérifier que l'épisode a des actes
        if (!currentEpisode.acts || Object.keys(currentEpisode.acts).length === 0) {
            throw new Error('L\'épisode ne contient aucun acte');
        }
        
        // Préparer la liste des actes
        allActs = Object.keys(currentEpisode.acts)
            .sort((a, b) => {
                const numA = parseInt(a.replace('acte_', ''));
                const numB = parseInt(b.replace('acte_', ''));
                return numA - numB;
            });
        
        console.log('Épisode chargé:', currentEpisode);
    } catch (error) {
        console.error('Erreur lors du chargement de l\'épisode:', error);
        showError(`Impossible de charger l'épisode: ${error.message}`);
    }
}

// Afficher la vue d'ensemble
function renderOverview() {
    if (!currentEpisode) return;
    
    // Titre de l'épisode
    document.getElementById('episode-title').textContent = currentEpisode.episode_title;
    
    // Arc narratif (rendu Markdown)
    const narrativeArcEl = document.getElementById('narrative-arc');
    if (typeof marked !== 'undefined') {
        narrativeArcEl.innerHTML = marked.parse(currentEpisode.narrative_arc);
    } else {
        // Fallback si marked n'est pas disponible
        const paragraphs = currentEpisode.narrative_arc.split('\n\n').filter(p => p.trim());
        narrativeArcEl.innerHTML = paragraphs.map(p => `<p>${escapeHtml(p)}</p>`).join('');
    }
    
    // Traiter les images dans l'arc narratif
    processImages(narrativeArcEl);
    
    // Scénario
    document.getElementById('scenario-input').textContent = currentEpisode.scenario_input;
    
    // Afficher l'histoire Twilight Zone si disponible
    renderTwilightZoneStory();
}

// Rendre tous les actes
function renderActs() {
    if (!currentEpisode) return;
    
    const actsSection = document.getElementById('acts-section');
    actsSection.innerHTML = '';
    
    allActs.forEach((actKey, index) => {
        const act = currentEpisode.acts[actKey];
        const actCard = createActCard(actKey, act, index);
        actsSection.appendChild(actCard);
    });
    
    // Mettre en évidence le premier acte par défaut et scroller vers lui
    showAct(0);
}

// Créer une carte d'acte
function createActCard(actKey, act, index) {
    const card = document.createElement('div');
    card.className = 'act-card';
    card.id = `act-${index}`;
    card.dataset.actKey = actKey;
    
    const actNumber = ACT_NUMBERS[actKey] || actKey;
    const actName = ACT_NAMES[actKey] || actKey;
    
    // Header
    const header = document.createElement('div');
    header.className = 'act-header';
    
    const headerLeft = document.createElement('div');
    headerLeft.style.display = 'flex';
    headerLeft.style.alignItems = 'baseline';
    headerLeft.style.gap = 'var(--spacing-sm)';
    const narrator = act.narrator || 'narrator_1';
    const narratorLabel = narrator === 'narrator_1' ? 'Narrateur 1' : 'Narrateur 2';
    headerLeft.innerHTML = `
        <span class="act-number">ACTE ${actNumber}</span>
        <h3 class="act-title">${escapeHtml(act.title)}</h3>
        <span class="narrator-badge">${narratorLabel}</span>
    `;
    
    // Container pour les boutons audio
    const audioControls = document.createElement('div');
    audioControls.className = 'audio-controls';
    audioControls.style.display = 'flex';
    audioControls.style.gap = '0.5rem';
    
    // Bouton audio (fichier MP3)
    const audioBtn = document.createElement('button');
    audioBtn.className = 'audio-btn';
    audioBtn.id = `audio-btn-${index}`;
    audioBtn.dataset.actKey = actKey;
    audioBtn.style.display = 'none'; // Caché par défaut, sera affiché si l'audio existe
    audioBtn.innerHTML = `
        <svg class="audio-icon play" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polygon points="5 3 19 12 5 21 5 3"/>
        </svg>
        <svg class="audio-icon pause" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display: none;">
            <rect x="6" y="4" width="4" height="16"/>
            <rect x="14" y="4" width="4" height="16"/>
        </svg>
    `;
    audioBtn.title = 'Vérification de l\'audio...';
    audioBtn.disabled = true; // Désactivé par défaut jusqu'à vérification
    
    // Bouton lecture vocale (synthèse vocale)
    const speechBtn = document.createElement('button');
    speechBtn.className = 'speech-btn';
    speechBtn.id = `speech-btn-${index}`;
    speechBtn.dataset.actKey = actKey;
    speechBtn.dataset.index = index;
    speechBtn.innerHTML = `
        <svg class="speech-icon play" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
            <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
            <line x1="12" y1="19" x2="12" y2="23"/>
            <line x1="8" y1="23" x2="16" y2="23"/>
        </svg>
        <svg class="speech-icon pause" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display: none;">
            <rect x="6" y="4" width="4" height="16"/>
            <rect x="14" y="4" width="4" height="16"/>
        </svg>
    `;
    speechBtn.title = 'Lire avec la synthèse vocale';
    
    // Vérifier si la synthèse vocale est disponible
    if (speechSynthesis) {
        speechBtn.disabled = false;
        
        // Gérer les clics simples et doubles
        speechBtn.addEventListener('click', (e) => {
            const now = Date.now();
            const timeSinceLastClick = now - lastClickTime;
            
            // Si c'est un double-clic (moins de 300ms entre les clics)
            if (timeSinceLastClick < 300 && timeSinceLastClick > 0) {
                e.preventDefault();
                clearTimeout(clickTimeout);
                lastClickTime = 0;
                toggleSpeech(index, true); // Double-clic = arrêter
            } else {
                // Clic simple - attendre un peu pour voir si c'est un double-clic
                lastClickTime = now;
                clearTimeout(clickTimeout);
                clickTimeout = setTimeout(() => {
                    toggleSpeech(index, false); // Clic simple = pause/reprendre
                    lastClickTime = 0;
                }, 300);
            }
        });
    } else {
        speechBtn.disabled = true;
        speechBtn.title = 'Synthèse vocale non disponible';
        speechBtn.style.opacity = '0.5';
    }
    
    audioControls.appendChild(audioBtn);
    audioControls.appendChild(speechBtn);
    
    // Vérifier si l'audio est disponible de manière asynchrone (affichera/cachera le bouton speech selon disponibilité)
    checkAudioAvailability(actKey, audioBtn, index, speechBtn);
    
    header.appendChild(headerLeft);
    header.appendChild(audioControls);
    
    // Content (rendu Markdown)
    const content = document.createElement('div');
    content.className = 'act-content';
    if (typeof marked !== 'undefined') {
        content.innerHTML = marked.parse(act.content);
        // Traiter les images après le parsing markdown
        processImages(content);
    } else {
        // Fallback si marked n'est pas disponible
        const paragraphs = act.content.split('\n\n').filter(p => p.trim());
        content.innerHTML = paragraphs.map(p => `<p>${escapeHtml(p)}</p>`).join('');
        processImages(content);
    }
    
    // Références
    if (act.references && act.references.length > 0) {
        const referencesDiv = document.createElement('div');
        referencesDiv.className = 'act-references';
        const referencesTitle = document.createElement('h4');
        referencesTitle.textContent = 'Références';
        referencesTitle.className = 'references-title';
        referencesDiv.appendChild(referencesTitle);
        
        const referencesList = document.createElement('ul');
        referencesList.className = 'references-list';
        act.references.forEach(ref => {
            const refItem = document.createElement('li');
            const refLink = document.createElement('a');
            refLink.href = ref.url;
            refLink.target = '_blank';
            refLink.rel = 'noopener noreferrer';
            refLink.textContent = ref.title;
            refLink.className = 'reference-link';
            refItem.appendChild(refLink);
            if (ref.description) {
                const refDesc = document.createElement('span');
                refDesc.className = 'reference-description';
                refDesc.textContent = ` - ${ref.description}`;
                refItem.appendChild(refDesc);
            }
            referencesList.appendChild(refItem);
        });
        referencesDiv.appendChild(referencesList);
        card.appendChild(header);
        card.appendChild(content);
        card.appendChild(referencesDiv);
    } else {
        card.appendChild(header);
        card.appendChild(content);
    }
    
    return card;
}

// Afficher un acte spécifique (met en évidence et scroll vers l'acte)
function showAct(index) {
    // Arrêter la synthèse vocale si on change d'acte
    if (currentSpeechIndex !== index) {
        stopSpeech();
    }
    
    // Cacher la section bonus
    const twilightSection = document.getElementById('twilight-zone-section');
    if (twilightSection) {
        twilightSection.classList.add('hidden');
    }
    
    // Retirer la classe active de tous les actes
    document.querySelectorAll('.act-card').forEach(card => {
        card.classList.remove('active');
    });
    
    // Mettre en évidence l'acte sélectionné
    const actCard = document.getElementById(`act-${index}`);
    if (actCard) {
        actCard.classList.add('active');
        currentActIndex = index;
        
        // Scroll vers l'acte avec un offset pour le header sticky
        setTimeout(() => {
            const headerHeight = document.querySelector('.header')?.offsetHeight || 0;
            const navHeight = document.querySelector('.acts-navigation')?.offsetHeight || 0;
            const offset = headerHeight + navHeight + 20;
            const elementPosition = actCard.getBoundingClientRect().top;
            const offsetPosition = elementPosition + window.pageYOffset - offset;
            
            window.scrollTo({
                top: offsetPosition,
                behavior: 'smooth'
            });
        }, 100);
    }
    
    updateNavigation();
}

// Afficher l'histoire bonus
function showBonus() {
    if (!currentEpisode || !currentEpisode.twilight_zone_story) {
        return;
    }
    
    // Arrêter la synthèse vocale
    stopSpeech();
    
    // Retirer la classe active de tous les actes
    document.querySelectorAll('.act-card').forEach(card => {
        card.classList.remove('active');
    });
    
    // Afficher la section bonus
    const twilightSection = document.getElementById('twilight-zone-section');
    if (twilightSection) {
        twilightSection.classList.remove('hidden');
        currentActIndex = -1; // -1 signifie qu'on est sur le bonus
        
        // Scroll vers la section bonus avec offset
        setTimeout(() => {
            const headerHeight = document.querySelector('.header')?.offsetHeight || 0;
            const navHeight = document.querySelector('.acts-navigation')?.offsetHeight || 0;
            const offset = headerHeight + navHeight + 20;
            const elementPosition = twilightSection.getBoundingClientRect().top;
            const offsetPosition = elementPosition + window.pageYOffset - offset;
            
            window.scrollTo({
                top: offsetPosition,
                behavior: 'smooth'
            });
        }, 100);
    }
    
    updateNavigation();
}

// Mettre à jour la navigation
function updateNavigation() {
    // Boutons précédent/suivant
    const prevBtn = document.getElementById('nav-prev');
    const nextBtn = document.getElementById('nav-next');
    const bonusBtn = document.getElementById('nav-bonus');
    
    prevBtn.disabled = currentActIndex === 0;
    
    // Vérifier si on est sur le bonus ou sur le dernier acte
    const isOnBonus = currentActIndex === -1; // -1 signifie qu'on est sur le bonus
    const hasBonus = currentEpisode && currentEpisode.twilight_zone_story;
    
    if (isOnBonus) {
        nextBtn.disabled = true;
        prevBtn.disabled = false;
    } else {
        nextBtn.disabled = currentActIndex === allActs.length - 1 && !hasBonus;
    }
    
    // Afficher/masquer le bouton bonus
    if (hasBonus) {
        bonusBtn.style.display = 'flex';
        bonusBtn.classList.toggle('active', isOnBonus);
    } else {
        bonusBtn.style.display = 'none';
    }
    
    // Indicateurs d'actes
    const indicator = document.getElementById('acts-indicator');
    indicator.innerHTML = '';
    
    allActs.forEach((actKey, index) => {
        const dot = document.createElement('div');
        dot.className = `act-dot ${index === currentActIndex ? 'active' : ''}`;
        dot.dataset.index = index;
        dot.dataset.actName = ACT_NAMES[actKey] || actKey;
        dot.addEventListener('click', () => showAct(index));
        indicator.appendChild(dot);
    });
    
    // Ajouter un indicateur bonus si disponible
    if (hasBonus) {
        const bonusDot = document.createElement('div');
        bonusDot.className = `act-dot bonus-dot ${isOnBonus ? 'active' : ''}`;
        bonusDot.title = 'Histoire bonus Twilight Zone';
        bonusDot.innerHTML = '🌟';
        bonusDot.addEventListener('click', () => showBonus());
        indicator.appendChild(bonusDot);
    }
}

// Configuration de la navigation
function setupNavigation() {
    // Boutons précédent/suivant
    document.getElementById('nav-prev').addEventListener('click', () => {
        if (currentActIndex > 0) {
            showAct(currentActIndex - 1);
        }
    });
    
    document.getElementById('nav-next').addEventListener('click', () => {
        if (currentActIndex < allActs.length - 1) {
            showAct(currentActIndex + 1);
        } else if (currentActIndex === allActs.length - 1 && currentEpisode && currentEpisode.twilight_zone_story) {
            // Si on est sur le dernier acte et qu'il y a un bonus, aller au bonus
            showBonus();
        }
    });
    
    // Bouton bonus
    document.getElementById('nav-bonus').addEventListener('click', () => {
        showBonus();
    });
    
    // Navigation au clavier
    document.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowLeft') {
            if (currentActIndex === -1) {
                // Si on est sur le bonus, aller au dernier acte
                showAct(allActs.length - 1);
            } else if (currentActIndex > 0) {
                showAct(currentActIndex - 1);
            }
        } else if (e.key === 'ArrowRight') {
            if (currentActIndex < allActs.length - 1) {
                showAct(currentActIndex + 1);
            } else if (currentActIndex === allActs.length - 1 && currentEpisode && currentEpisode.twilight_zone_story) {
                // Si on est sur le dernier acte et qu'il y a un bonus, aller au bonus
                showBonus();
            }
        }
    });
}

// Échapper le HTML pour éviter les injections
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Afficher une erreur
function showError(message) {
    const mainContent = document.querySelector('.main-content');
    if (!mainContent) {
        console.error('Erreur:', message);
        return;
    }
    mainContent.innerHTML = `
        <div style="text-align: center; padding: 3rem; color: #ff6b6b;">
            <h2>⚠️ Erreur</h2>
            <p style="margin-top: 1rem; font-size: 1.1rem;">${escapeHtml(message)}</p>
            <p style="margin-top: 2rem; color: var(--color-text-secondary); font-size: 0.9rem;">
                Vérifiez que vous avez généré un épisode avec: <code>python app.py "Votre scénario"</code>
            </p>
        </div>
    `;
    
    // Réinitialiser la navigation
    const actsNav = document.getElementById('acts-nav');
    if (actsNav) {
        const indicator = document.getElementById('acts-indicator');
        if (indicator) indicator.innerHTML = '';
        const prevBtn = document.getElementById('nav-prev');
        const nextBtn = document.getElementById('nav-next');
        if (prevBtn) prevBtn.disabled = true;
        if (nextBtn) nextBtn.disabled = true;
    }
}

// Vérifier si l'audio est disponible
async function checkAudioAvailability(actKey, audioBtn, index, speechBtn = null) {
    if (!currentRunName) {
        // Cacher le bouton audio si aucun run n'est sélectionné
        audioBtn.style.display = 'none';
        return;
    }
    
    const audioUrl = `/api/audio/${actKey}?run=${encodeURIComponent(currentRunName)}`;
    
    try {
        // Faire une requête HEAD pour vérifier si le fichier existe
        const response = await fetch(audioUrl, { method: 'HEAD' });
        
        if (response.ok) {
            // Audio disponible - afficher le bouton
            audioBtn.style.display = 'flex';
            audioBtn.disabled = false;
            audioBtn.title = 'Lire l\'audio';
            audioBtn.style.opacity = '1';
            audioBtn.addEventListener('click', () => toggleAudio(actKey, index));
        } else {
            // Audio non disponible - cacher le bouton
            audioBtn.style.display = 'none';
        }
    } catch (error) {
        console.warn(`Audio non disponible pour ${actKey}:`, error);
        // Cacher le bouton si l'audio n'existe pas
        audioBtn.style.display = 'none';
    }
}

// Gestion audio
async function toggleAudio(actKey, index) {
    const btn = document.getElementById(`audio-btn-${index}`);
    const playIcon = btn.querySelector('.audio-icon.play');
    const pauseIcon = btn.querySelector('.audio-icon.pause');
    
    // Si un lecteur existe déjà pour cet acte
    if (audioPlayers[actKey]) {
        const audio = audioPlayers[actKey];
        if (audio.paused) {
            // Reprendre la lecture
            audio.play();
            playIcon.style.display = 'none';
            pauseIcon.style.display = 'block';
            btn.classList.add('playing');
        } else {
            // Pause
            audio.pause();
            playIcon.style.display = 'block';
            pauseIcon.style.display = 'none';
            btn.classList.remove('playing');
        }
        return;
    }
    
    // Créer un nouveau lecteur audio
    try {
        // Chercher le fichier audio (plusieurs chemins possibles)
        const audioPaths = [
            `/api/audio/${actKey}.mp3`,
            `../output/audio/${actKey}_*.mp3`,
            `../output/audio/${actKey}*.mp3`
        ];
        
        // Construire l'URL audio avec le paramètre run
        const audioUrl = currentRunName 
            ? `/api/audio/${actKey}?run=${encodeURIComponent(currentRunName)}`
            : `/api/audio/${actKey}`;
        
        const audio = new Audio();
        audio.src = audioUrl;
        
        audio.addEventListener('loadeddata', () => {
            audio.play();
            playIcon.style.display = 'none';
            pauseIcon.style.display = 'block';
            btn.classList.add('playing');
        });
        
        audio.addEventListener('ended', () => {
            playIcon.style.display = 'block';
            pauseIcon.style.display = 'none';
            btn.classList.remove('playing');
        });
        
        audio.addEventListener('error', (e) => {
            console.error('Erreur audio:', e);
            console.error('URL audio:', audioUrl);
            console.error('Code erreur:', audio.error?.code);
            console.error('Message erreur:', audio.error?.message);
            btn.title = 'Audio non disponible';
            btn.disabled = true;
            btn.style.opacity = '0.5';
        });
        
        audioPlayers[actKey] = audio;
        
        // Arrêter les autres lecteurs
        Object.keys(audioPlayers).forEach(key => {
            if (key !== actKey && audioPlayers[key]) {
                audioPlayers[key].pause();
                audioPlayers[key].currentTime = 0;
                const otherIndex = allActs.indexOf(key);
                if (otherIndex >= 0) {
                    const otherBtn = document.getElementById(`audio-btn-${otherIndex}`);
                    if (otherBtn) {
                        otherBtn.querySelector('.audio-icon.play').style.display = 'block';
                        otherBtn.querySelector('.audio-icon.pause').style.display = 'none';
                        otherBtn.classList.remove('playing');
                    }
                }
            }
        });
        
    } catch (error) {
        console.error('Erreur lors de la création du lecteur audio:', error);
        btn.title = 'Erreur de chargement audio';
    }
}

// Afficher l'histoire Twilight Zone
function renderTwilightZoneStory() {
    if (!currentEpisode || !currentEpisode.twilight_zone_story) {
        const section = document.getElementById('twilight-zone-section');
        if (section) {
            section.classList.add('hidden');
        }
        return;
    }
    
    const section = document.getElementById('twilight-zone-section');
    const storyEl = document.getElementById('twilight-zone-story');
    
    if (!section || !storyEl) return;
    
    const story = currentEpisode.twilight_zone_story;
    
    // Afficher la section
    section.classList.remove('hidden');
    
    // Formater l'histoire avec Markdown
    let storyHTML = '';
    if (typeof marked !== 'undefined') {
        storyHTML = `
            <div class="twilight-zone-header">
                <h3>${escapeHtml(story.title)}</h3>
                <p class="twilight-zone-theme">Thème: ${escapeHtml(story.theme)}</p>
            </div>
            <div class="twilight-zone-content">
                ${marked.parse(story.story)}
            </div>
        `;
    } else {
        // Fallback si marked n'est pas disponible
        const paragraphs = story.story.split('\n\n').filter(p => p.trim());
        storyHTML = `
            <div class="twilight-zone-header">
                <h3>${escapeHtml(story.title)}</h3>
                <p class="twilight-zone-theme">Thème: ${escapeHtml(story.theme)}</p>
            </div>
            <div class="twilight-zone-content">
                ${paragraphs.map(p => `<p>${escapeHtml(p)}</p>`).join('')}
            </div>
        `;
    }
    
    storyEl.innerHTML = storyHTML;
    
    // Traiter les images dans l'histoire Twilight Zone
    const twilightContent = storyEl.querySelector('.twilight-zone-content');
    if (twilightContent) {
        processImages(twilightContent);
    }
}

// Extraire le texte brut depuis le HTML (sans les balises)
function extractTextFromHTML(htmlElement) {
    // Créer un élément temporaire pour extraire le texte
    const temp = document.createElement('div');
    temp.innerHTML = htmlElement.innerHTML;
    
    // Récupérer tout le texte
    let text = temp.textContent || temp.innerText || '';
    
    // Nettoyer le texte : enlever les espaces multiples, sauts de ligne excessifs
    text = text.replace(/\s+/g, ' ').trim();
    
    // Améliorer la prononciation pour une meilleure qualité
    text = text.replace(/«/g, '"');
    text = text.replace(/»/g, '"');
    text = text.replace(/—/g, ' - ');
    text = text.replace(/–/g, ' - ');
    
    // Ajouter des pauses pour une meilleure compréhension
    text = text.replace(/\.\s+/g, '. '); // Espace après les points
    text = text.replace(/\?\s+/g, '? '); // Espace après les points d'interrogation
    text = text.replace(/!\s+/g, '! '); // Espace après les points d'exclamation
    
    // Améliorer la prononciation des nombres et acronymes
    text = text.replace(/(\d+)\s*km/g, '$1 kilomètres');
    text = text.replace(/(\d+)\s*m/g, '$1 mètres');
    text = text.replace(/AI/g, 'A I');
    text = text.replace(/TTS/g, 'T T S');
    
    // Ajouter des pauses après les deux-points
    text = text.replace(/:\s*/g, ': ');
    
    return text;
}

// Obtenir une voix française selon le narrateur
function getFrenchVoice(narrator = 'narrator_1') {
    if (!speechSynthesis) return null;
    
    const voices = speechSynthesis.getVoices();
    
    // Chercher une voix française
    const frenchVoices = voices.filter(voice => 
        voice.lang.startsWith('fr') || 
        voice.name.toLowerCase().includes('french') ||
        voice.name.toLowerCase().includes('français')
    );
    
    if (frenchVoices.length > 0) {
        // Narrateur 1 : préférer voix féminine
        if (narrator === 'narrator_1') {
            // Priorité 1: Voix neurales/premium féminines
            const neuralVoices = frenchVoices.filter(v => 
                (v.name.toLowerCase().includes('neural') ||
                 v.name.toLowerCase().includes('premium') ||
                 v.name.toLowerCase().includes('enhanced') ||
                 v.name.toLowerCase().includes('natural') ||
                 v.name.toLowerCase().includes('wavenet') ||
                 v.name.toLowerCase().includes('standard')) &&
                (v.name.toLowerCase().includes('female') || 
                 v.name.toLowerCase().includes('féminin') ||
                 v.name.toLowerCase().includes('denise') ||
                 v.name.toLowerCase().includes('julie') ||
                 v.name.toLowerCase().includes('thomas'))
            );
            
            if (neuralVoices.length > 0) {
                // Préférer Denise ou voix féminine
                const denise = neuralVoices.find(v => v.name.toLowerCase().includes('denise'));
                if (denise) return denise;
                const female = neuralVoices.find(v => 
                    v.name.toLowerCase().includes('female') || 
                    v.name.toLowerCase().includes('féminin')
                );
                if (female) return female;
                return neuralVoices[0];
            }
            
            // Priorité 2: Voix féminines de qualité
            const femaleVoices = frenchVoices.filter(v => 
                v.name.toLowerCase().includes('denise') ||
                v.name.toLowerCase().includes('julie') ||
                v.name.toLowerCase().includes('female') ||
                v.name.toLowerCase().includes('féminin')
            );
            
            if (femaleVoices.length > 0) {
                return femaleVoices[0];
            }
        } else {
            // Narrateur 2 : préférer voix masculine
            // Priorité 1: Voix neurales/premium masculines
            const neuralVoices = frenchVoices.filter(v => 
                (v.name.toLowerCase().includes('neural') ||
                 v.name.toLowerCase().includes('premium') ||
                 v.name.toLowerCase().includes('enhanced') ||
                 v.name.toLowerCase().includes('natural') ||
                 v.name.toLowerCase().includes('wavenet') ||
                 v.name.toLowerCase().includes('standard')) &&
                (v.name.toLowerCase().includes('thomas') ||
                 v.name.toLowerCase().includes('paul') ||
                 v.name.toLowerCase().includes('arnold') ||
                 v.name.toLowerCase().includes('male') ||
                 (!v.name.toLowerCase().includes('female') && 
                  !v.name.toLowerCase().includes('féminin')))
            );
            
            if (neuralVoices.length > 0) {
                // Préférer Thomas ou voix masculine
                const thomas = neuralVoices.find(v => v.name.toLowerCase().includes('thomas'));
                if (thomas) return thomas;
                const male = neuralVoices.find(v => 
                    v.name.toLowerCase().includes('male') ||
                    (!v.name.toLowerCase().includes('female') && 
                     !v.name.toLowerCase().includes('féminin'))
                );
                if (male) return male;
                return neuralVoices[0];
            }
            
            // Priorité 2: Voix masculines de qualité
            const maleVoices = frenchVoices.filter(v => 
                v.name.toLowerCase().includes('thomas') ||
                v.name.toLowerCase().includes('paul') ||
                v.name.toLowerCase().includes('arnold') ||
                (!v.name.toLowerCase().includes('female') && 
                 !v.name.toLowerCase().includes('féminin') &&
                 !v.name.toLowerCase().includes('denise') &&
                 !v.name.toLowerCase().includes('julie'))
            );
            
            if (maleVoices.length > 0) {
                return maleVoices[0];
            }
        }
        
        // Fallback: Prendre la première voix française disponible
        return frenchVoices[0];
    }
    
    // Si pas de voix française, prendre la première voix disponible
    return voices.length > 0 ? voices[0] : null;
}

// Gérer la synthèse vocale
let lastClickTime = 0;
let clickTimeout = null;

function toggleSpeech(index, isDoubleClick = false) {
    const btn = document.getElementById(`speech-btn-${index}`);
    const playIcon = btn.querySelector('.speech-icon.play');
    const pauseIcon = btn.querySelector('.speech-icon.pause');
    
    // Si double-clic, arrêter complètement
    if (isDoubleClick && currentSpeechIndex === index && (currentUtterance || speechPaused)) {
        stopSpeech();
        return;
    }
    
    // Si on est en train de lire cet acte
    if (currentSpeechIndex === index && currentUtterance) {
        if (speechPaused) {
            // Reprendre
            speechSynthesis.resume();
            speechPaused = false;
            playIcon.style.display = 'none';
            if (pauseIcon) pauseIcon.style.display = 'block';
            btn.classList.add('playing');
            btn.title = 'Mettre en pause (double-clic pour arrêter)';
        } else {
            // Pause
            speechSynthesis.pause();
            speechPaused = true;
            playIcon.style.display = 'block';
            if (pauseIcon) pauseIcon.style.display = 'none';
            btn.classList.remove('playing');
            btn.title = 'Reprendre la lecture (double-clic pour arrêter)';
        }
        return;
    }
    
    // Arrêter toute lecture en cours
    stopSpeech();
    
    // Récupérer le contenu de l'acte
    const actCard = document.getElementById(`act-${index}`);
    if (!actCard) return;
    
    const contentElement = actCard.querySelector('.act-content');
    if (!contentElement) return;
    
    // Extraire le texte
    const text = extractTextFromHTML(contentElement);
    
    if (!text || text.length === 0) {
        console.warn('Aucun texte à lire');
        return;
    }
    
    // Récupérer le narrateur de l'acte
    const act = currentEpisode.acts[allActs[index]];
    const narrator = act?.narrator || 'narrator_1';
    
    // Créer l'utterance
    const utterance = new SpeechSynthesisUtterance(text);
    
    // Configurer la voix française selon le narrateur
    const voice = getFrenchVoice(narrator);
    if (voice) {
        utterance.voice = voice;
        utterance.lang = voice.lang || 'fr-FR';
        console.log(`Voix sélectionnée pour ${narrator}:`, voice.name);
    } else {
        utterance.lang = 'fr-FR';
    }
    
    // Configuration optimisée pour une meilleure qualité
    // Ajuster le pitch selon le narrateur (féminin = plus aigu, masculin = plus grave)
    if (narrator === 'narrator_1') {
        utterance.pitch = 1.1; // Légèrement plus aigu pour narrateur 1 (féminin)
    } else {
        utterance.pitch = 0.9; // Légèrement plus grave pour narrateur 2 (masculin)
    }
    utterance.rate = 0.95; // Légèrement plus lent pour une meilleure clarté
    utterance.volume = 1.0; // Volume maximum
    
    // Gestionnaires d'événements
    utterance.onstart = () => {
        currentSpeechIndex = index;
        currentUtterance = utterance;
        speechPaused = false;
        playIcon.style.display = 'none';
        if (pauseIcon) pauseIcon.style.display = 'block';
        btn.classList.add('playing');
        btn.title = 'Mettre en pause (double-clic pour arrêter)';
        
        // Mettre en évidence l'acte en cours de lecture
        actCard.classList.add('speaking');
    };
    
    utterance.onend = () => {
        playIcon.style.display = 'block';
        if (pauseIcon) pauseIcon.style.display = 'none';
        btn.classList.remove('playing');
        btn.title = 'Lire avec la synthèse vocale';
        actCard.classList.remove('speaking');
        currentSpeechIndex = -1;
        currentUtterance = null;
        speechPaused = false;
        lastClickTime = 0;
    };
    
    utterance.onerror = (event) => {
        console.error('Erreur de synthèse vocale:', event);
        playIcon.style.display = 'block';
        if (pauseIcon) pauseIcon.style.display = 'none';
        btn.classList.remove('playing');
        btn.title = 'Erreur de lecture';
        actCard.classList.remove('speaking');
        currentSpeechIndex = -1;
        currentUtterance = null;
        speechPaused = false;
        lastClickTime = 0;
    };
    
    // Lancer la lecture
    speechSynthesis.speak(utterance);
}

// Arrêter la synthèse vocale
function stopSpeech() {
    if (speechSynthesis) {
        speechSynthesis.cancel();
    }
    
    // Réinitialiser tous les boutons
    document.querySelectorAll('.speech-btn').forEach(btn => {
        const playIcon = btn.querySelector('.speech-icon.play');
        const pauseIcon = btn.querySelector('.speech-icon.pause');
        if (playIcon) playIcon.style.display = 'block';
        if (pauseIcon) pauseIcon.style.display = 'none';
        btn.classList.remove('playing');
        btn.title = 'Lire avec la synthèse vocale';
    });
    
    // Retirer la classe speaking de tous les actes
    document.querySelectorAll('.act-card').forEach(card => {
        card.classList.remove('speaking');
    });
    
    currentSpeechIndex = -1;
    currentUtterance = null;
    speechPaused = false;
    lastClickTime = 0;
    
    // Annuler le timeout de clic simple s'il existe
    if (clickTimeout) {
        clearTimeout(clickTimeout);
        clickTimeout = null;
    }
}

// Charger les voix disponibles (nécessaire pour certains navigateurs)
if ('speechSynthesis' in window) {
    // Chrome nécessite que les voix soient chargées
    speechSynthesis.onvoiceschanged = () => {
        const voices = speechSynthesis.getVoices();
        console.log('Voix chargées:', voices.length);
        
        // Afficher les voix françaises disponibles pour debug
        const frenchVoices = voices.filter(v => v.lang.startsWith('fr'));
        if (frenchVoices.length > 0) {
            console.log('Voix françaises disponibles:', frenchVoices.map(v => `${v.name} (${v.lang})${v.default ? ' [défaut]' : ''}`));
            
            // Afficher les voix disponibles pour chaque narrateur
            const voice1 = getFrenchVoice('narrator_1');
            const voice2 = getFrenchVoice('narrator_2');
            if (voice1) {
                console.log('Voix Narrateur 1:', `${voice1.name} (${voice1.lang})`);
            }
            if (voice2) {
                console.log('Voix Narrateur 2:', `${voice2.name} (${voice2.lang})`);
            }
        }
    };
    
    // Forcer le chargement des voix en créant un utterance vide
    // Cela force Chrome à charger les voix
    const dummyUtterance = new SpeechSynthesisUtterance('');
    dummyUtterance.volume = 0;
    speechSynthesis.speak(dummyUtterance);
    speechSynthesis.cancel();
    
    // Attendre que les voix soient chargées
    setTimeout(() => {
        const voices = speechSynthesis.getVoices();
        if (voices.length > 0) {
            const frenchVoices = voices.filter(v => v.lang.startsWith('fr'));
            console.log('Voix françaises trouvées:', frenchVoices.length);
        }
    }, 500);
}

// ============================================
// Gestion des images : Lightbox, Lazy Loading, Erreurs
// ============================================

// État de la lightbox
let lightboxImages = [];
let currentLightboxIndex = -1;

// Traiter les images dans un conteneur
function processImages(container) {
    if (!container) return;
    
    const images = container.querySelectorAll('img');
    images.forEach((img, index) => {
        // Ajouter lazy loading
        if (!img.hasAttribute('loading')) {
            img.setAttribute('loading', 'lazy');
        }
        
        // Ajouter la classe pour le placeholder
        img.classList.add('loading');
        
        // Gérer le chargement réussi
        img.addEventListener('load', () => {
            img.classList.remove('loading');
            img.classList.add('loaded');
        });
        
        // Gérer les erreurs de chargement
        img.addEventListener('error', () => {
            img.classList.remove('loading');
            img.classList.add('error');
            console.warn('Erreur de chargement d\'image:', img.src);
        });
        
        // Ajouter le clic pour ouvrir la lightbox
        img.addEventListener('click', () => {
            openLightbox(container, index);
        });
        
        // Ajouter le style cursor pointer si pas déjà fait
        if (!img.style.cursor) {
            img.style.cursor = 'pointer';
        }
    });
}

// Ouvrir la lightbox
function openLightbox(container, imageIndex) {
    const images = Array.from(container.querySelectorAll('img')).filter(img => !img.classList.contains('error'));
    
    if (images.length === 0) return;
    
    // Stocker les images et l'index courant
    lightboxImages = images;
    currentLightboxIndex = imageIndex >= 0 && imageIndex < images.length ? imageIndex : 0;
    
    // Afficher la lightbox
    const lightbox = document.getElementById('lightbox');
    const lightboxImage = document.getElementById('lightbox-image');
    const lightboxCaption = document.getElementById('lightbox-caption');
    
    if (!lightbox || !lightboxImage) return;
    
    // Charger l'image courante
    loadLightboxImage();
    
    // Afficher le modal
    lightbox.classList.add('active');
    document.body.style.overflow = 'hidden'; // Empêcher le scroll
    
    // Mettre à jour les boutons de navigation
    updateLightboxNavigation();
}

// Charger l'image dans la lightbox
function loadLightboxImage() {
    if (currentLightboxIndex < 0 || currentLightboxIndex >= lightboxImages.length) return;
    
    const lightboxImage = document.getElementById('lightbox-image');
    const lightboxCaption = document.getElementById('lightbox-caption');
    const img = lightboxImages[currentLightboxIndex];
    
    if (!lightboxImage || !img) return;
    
    // Charger l'image
    lightboxImage.src = img.src;
    lightboxImage.alt = img.alt || '';
    
    // Afficher la légende
    if (lightboxCaption) {
        lightboxCaption.textContent = img.alt || '';
        lightboxCaption.style.display = img.alt ? 'block' : 'none';
    }
    
    // Gérer les erreurs
    lightboxImage.onerror = () => {
        if (lightboxCaption) {
            lightboxCaption.textContent = 'Erreur de chargement de l\'image';
            lightboxCaption.style.display = 'block';
        }
    };
}

// Mettre à jour les boutons de navigation
function updateLightboxNavigation() {
    const prevBtn = document.getElementById('lightbox-prev');
    const nextBtn = document.getElementById('lightbox-next');
    
    if (prevBtn) {
        prevBtn.disabled = lightboxImages.length <= 1;
    }
    
    if (nextBtn) {
        nextBtn.disabled = lightboxImages.length <= 1;
    }
}

// Navigation dans la lightbox
function navigateLightbox(direction) {
    if (lightboxImages.length <= 1) return;
    
    if (direction === 'prev') {
        currentLightboxIndex = (currentLightboxIndex - 1 + lightboxImages.length) % lightboxImages.length;
    } else if (direction === 'next') {
        currentLightboxIndex = (currentLightboxIndex + 1) % lightboxImages.length;
    }
    
    loadLightboxImage();
}

// Fermer la lightbox
function closeLightbox() {
    const lightbox = document.getElementById('lightbox');
    if (lightbox) {
        lightbox.classList.remove('active');
        document.body.style.overflow = ''; // Restaurer le scroll
    }
    
    // Réinitialiser
    lightboxImages = [];
    currentLightboxIndex = -1;
}

// Initialiser la lightbox
function initializeLightbox() {
    // Bouton fermer
    const closeBtn = document.getElementById('lightbox-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', closeLightbox);
    }
    
    // Boutons navigation
    const prevBtn = document.getElementById('lightbox-prev');
    const nextBtn = document.getElementById('lightbox-next');
    
    if (prevBtn) {
        prevBtn.addEventListener('click', () => navigateLightbox('prev'));
    }
    
    if (nextBtn) {
        nextBtn.addEventListener('click', () => navigateLightbox('next'));
    }
    
    // Fermer avec ESC et navigation clavier
    document.addEventListener('keydown', (e) => {
        const lightbox = document.getElementById('lightbox');
        if (lightbox && lightbox.classList.contains('active')) {
            if (e.key === 'Escape') {
                closeLightbox();
            } else if (e.key === 'ArrowLeft') {
                navigateLightbox('prev');
            } else if (e.key === 'ArrowRight') {
                navigateLightbox('next');
            }
        }
    });
    
    // Fermer en cliquant sur le fond
    const lightbox = document.getElementById('lightbox');
    if (lightbox) {
        lightbox.addEventListener('click', (e) => {
            if (e.target === lightbox) {
                closeLightbox();
            }
        });
    }
}

