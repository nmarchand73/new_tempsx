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
let episodePollingInterval = null; // Intervalle pour le polling de l'épisode
let lastEpisodeHash = null; // Hash du dernier épisode chargé pour détecter les changements

// Initialisation
document.addEventListener('DOMContentLoaded', async () => {
    // Vérifier le support de la synthèse vocale
    if ('speechSynthesis' in window && window.speechSynthesis) {
        try {
        speechSynthesis = window.speechSynthesis;
        console.log('Synthèse vocale disponible');
        } catch (error) {
            console.warn('Erreur lors de l\'accès à la synthèse vocale:', error);
            speechSynthesis = null;
        }
    } else {
        console.warn('Synthèse vocale non disponible dans ce navigateur');
        speechSynthesis = null;
    }
    
    // Initialiser la lightbox
    initializeLightbox();
    
    await loadRuns();
    setupRunSelector();
    
    // Charger l'épisode seulement si un run est disponible
    if (currentRunName) {
        await loadEpisode(true);
        if (currentEpisode && allActs.length > 0) {
            setupNavigation();
            renderOverview();
            renderActs();
            updateNavigation();
            // Démarrer le polling pour les mises à jour progressives
            startEpisodePolling();
        } else {
            showError('Impossible de charger l\'épisode. Vérifiez que l\'épisode contient des actes.');
        }
    } else {
        showError('Aucun run disponible. Générez d\'abord un épisode avec: python app.py "Votre scénario"');
    }
});

// Démarrer le polling pour détecter les mises à jour de l'épisode
function startEpisodePolling() {
    // Arrêter le polling existant s'il y en a un
    stopEpisodePolling();
    
    // Poller toutes les 20 secondes pour détecter les mises à jour
    episodePollingInterval = setInterval(async () => {
        if (currentRunName) {
            await loadEpisode(false); // Ne pas forcer l'update, juste vérifier
        }
    }, 20000); // 20 secondes
    
    console.log('🔄 Polling de l\'épisode activé (vérification toutes les 20 secondes)');
}

// Arrêter le polling
function stopEpisodePolling() {
    if (episodePollingInterval) {
        clearInterval(episodePollingInterval);
        episodePollingInterval = null;
        console.log('🛑 Polling de l\'épisode arrêté');
    }
}

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
            
            // Arrêter le polling avant de changer de run
            stopEpisodePolling();
            
            await loadEpisode(true);
            if (currentEpisode && allActs.length > 0) {
                renderOverview();
                renderActs();
                updateNavigation();
                renderTwilightZoneStory();
                // Réinitialiser la détection de scroll après le chargement
                setupScrollDetection();
                // Redémarrer le polling
                startEpisodePolling();
            } else {
                showError('Impossible de charger l\'épisode. Vérifiez que l\'épisode contient des actes.');
            }
        } else {
            showError('Aucun run sélectionné');
        }
    });
}

// Calculer un hash simple du contenu d'un épisode pour détecter les changements
function calculateEpisodeHash(episode) {
    if (!episode) return null;
    
    // Créer un hash basé sur le contenu des actes (pour détecter les changements d'images)
    const contentParts = [];
    if (episode.acts) {
        Object.keys(episode.acts).sort().forEach(actKey => {
            const act = episode.acts[actKey];
            // Utiliser la longueur et les derniers caractères pour détecter les changements
            contentParts.push(`${actKey}:${act.content.length}:${act.content.slice(-200)}`);
        });
    }
    if (episode.twilight_zone_story) {
        contentParts.push(`twilight:${episode.twilight_zone_story.story.length}:${episode.twilight_zone_story.story.slice(-200)}`);
    }
    
    // Hash simple basé sur la longueur et les derniers caractères
    return contentParts.join('|');
}

// Mettre à jour l'affichage de l'épisode de manière progressive
function updateEpisodeDisplay() {
    if (!currentEpisode) return;
    
    // Mettre à jour la vue d'ensemble si nécessaire
    renderOverview();
    
    // Mettre à jour chaque acte qui a changé
    allActs.forEach((actKey, index) => {
        const act = currentEpisode.acts[actKey];
        const actCard = document.getElementById(`act-${index}`);
        
        if (actCard) {
            // Vérifier si le contenu a changé en comparant
            const contentEl = actCard.querySelector('.act-content');
            if (contentEl) {
                // Re-rendre le contenu markdown
                if (typeof marked !== 'undefined') {
                    contentEl.innerHTML = renderMarkdown(act.content);
                    // Traiter les images après le parsing markdown
                    processImages(contentEl);
                } else {
                    // Fallback
                    const paragraphs = act.content.split('\n\n').filter(p => p.trim());
                    contentEl.innerHTML = paragraphs.map(p => `<p>${escapeHtml(p)}</p>`).join('');
                    processImages(contentEl);
                }
            }
        } else {
            // Si l'acte n'existe pas encore, tout re-rendre
            renderActs();
            return;
        }
    });
    
    // Mettre à jour l'histoire Twilight Zone si nécessaire
    renderTwilightZoneStory();
}

// Charger l'épisode depuis le JSON
async function loadEpisode(forceUpdate = false) {
    if (!currentRunName) {
        console.warn('Aucun run sélectionné, impossible de charger l\'épisode');
        if (forceUpdate) {
            showError('Aucun run sélectionné. Sélectionnez un run dans le menu déroulant.');
        }
        return false;
    }
    
    try {
        // Construire l'URL avec le paramètre run et un timestamp pour éviter le cache
        const url = `/api/episode.json?run=${encodeURIComponent(currentRunName)}&t=${Date.now()}`;
        
        const response = await fetch(url);
        if (!response.ok) {
            if (response.status === 404) {
                if (forceUpdate) {
                    throw new Error(`Run "${currentRunName}" introuvable`);
                }
                return false;
            }
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const newEpisode = await response.json();
        
        // Vérifier que l'épisode a des actes
        if (!newEpisode.acts || Object.keys(newEpisode.acts).length === 0) {
            console.warn('L\'épisode ne contient aucun acte. Structure:', newEpisode);
            if (forceUpdate) {
                showError('L\'épisode ne contient aucun acte. Vérifiez que l\'épisode a été généré correctement.');
            }
            return false;
        }
        
        // Calculer le hash pour détecter les changements
        const newHash = calculateEpisodeHash(newEpisode);
        const hasChanged = newHash !== lastEpisodeHash;
        
        if (!hasChanged && !forceUpdate) {
            // Pas de changement, ne rien faire
            return false;
        }
        
        // Mettre à jour l'épisode
        const wasFirstLoad = currentEpisode === null;
        currentEpisode = newEpisode;
        lastEpisodeHash = newHash;
        
        // Préparer la liste des actes
        allActs = Object.keys(currentEpisode.acts)
            .sort((a, b) => {
                const numA = parseInt(a.replace('acte_', ''));
                const numB = parseInt(b.replace('acte_', ''));
                return numA - numB;
            });
        
        console.log('Épisode chargé:', currentEpisode);
        console.log('Actes trouvés:', allActs.length);
        
        if (hasChanged && !wasFirstLoad) {
            console.log('🔄 Changements détectés dans l\'épisode, mise à jour de l\'affichage...');
        }
        
        // Si c'est le premier chargement, tout rendre
        if (wasFirstLoad) {
            return true;
        }
        
        // Sinon, mettre à jour progressivement uniquement les actes qui ont changé
        updateEpisodeDisplay();
        return true;
        
    } catch (error) {
        console.error('Erreur lors du chargement de l\'épisode:', error);
        if (forceUpdate) {
            showError(`Impossible de charger l'épisode: ${error.message}`);
        }
        return false;
    }
}

// Afficher la vue d'ensemble
function renderOverview() {
    if (!currentEpisode) return;
    
    // Titre de l'épisode
    const titleEl = document.getElementById('episode-title');
    if (titleEl) {
        titleEl.textContent = currentEpisode.episode_title || 'Sans titre';
    }
    
    // Arc narratif (rendu Markdown)
    const narrativeArcEl = document.getElementById('narrative-arc');
    if (narrativeArcEl) {
        if (currentEpisode.narrative_arc) {
    if (typeof marked !== 'undefined') {
        narrativeArcEl.innerHTML = renderMarkdown(currentEpisode.narrative_arc);
    } else {
        // Fallback si marked n'est pas disponible
        const paragraphs = currentEpisode.narrative_arc.split('\n\n').filter(p => p.trim());
        narrativeArcEl.innerHTML = paragraphs.map(p => `<p>${escapeHtml(p)}</p>`).join('');
    }
    
    // Traiter les images dans l'arc narratif
    processImages(narrativeArcEl);
        } else {
            narrativeArcEl.innerHTML = '<p>Aucun arc narratif disponible.</p>';
        }
    }
    
    // Scénario
    const scenarioEl = document.getElementById('scenario-input');
    if (scenarioEl) {
        scenarioEl.textContent = currentEpisode.scenario_input || 'Aucun scénario disponible.';
    }
    
    // Afficher l'histoire Twilight Zone si disponible
    renderTwilightZoneStory();
}

// Rendre tous les actes
function renderActs() {
    if (!currentEpisode) return;
    
    const actsSection = document.getElementById('acts-section');
    if (!actsSection) {
        console.error('Élément acts-section introuvable dans le DOM');
        return;
    }
    
    actsSection.innerHTML = '';
    
    allActs.forEach((actKey, index) => {
        const act = currentEpisode.acts[actKey];
        const actCard = createActCard(actKey, act, index);
        actsSection.appendChild(actCard);
    });
    
    // Mettre en évidence le premier acte par défaut et scroller vers lui
    showAct(0);
    
    // Réinitialiser la détection de scroll après le rendu des actes
    setupScrollDetection();
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
    if (speechSynthesis && 'speechSynthesis' in window && window.speechSynthesis) {
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
        content.innerHTML = renderMarkdown(act.content);
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
            
            // Lien avec titre
            const refLink = document.createElement('a');
            refLink.href = ref.url;
            refLink.target = '_blank';
            refLink.rel = 'noopener noreferrer';
            refLink.textContent = ref.title;
            refLink.className = 'reference-link';
            refItem.appendChild(refLink);
            
            // Nom de la source (après le titre, entre parenthèses)
            const sourceName = extractSourceName(ref.url);
            const sourceSpan = document.createElement('span');
            sourceSpan.className = 'reference-source';
            sourceSpan.textContent = ` (${sourceName})`;
            refItem.appendChild(sourceSpan);
            
            // Description
            if (ref.description) {
                const refDesc = document.createElement('span');
                refDesc.className = 'reference-description';
                refDesc.textContent = ` — ${ref.description}`;
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
        isNavigatingProgrammatically = true;
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
            
            // Réactiver la détection après le scroll
            setTimeout(() => {
                isNavigatingProgrammatically = false;
                updateNavigation();
            }, 800);
        }, 100);
    } else {
        updateNavigation();
    }
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
        isNavigatingProgrammatically = true;
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
            
            // Réactiver la détection après le scroll
            setTimeout(() => {
                isNavigatingProgrammatically = false;
                updateNavigation();
            }, 800);
        }, 100);
    } else {
        updateNavigation();
    }
}

// Mettre à jour la navigation
function updateNavigation() {
    // Boutons précédent/suivant
    const prevBtn = document.getElementById('nav-prev');
    const nextBtn = document.getElementById('nav-next');
    const bonusBtn = document.getElementById('nav-bonus');
    
    if (!prevBtn || !nextBtn || !bonusBtn) return;
    
    // Vérifier si on est sur le bonus ou sur le dernier acte
    const isOnBonus = currentActIndex === -1; // -1 signifie qu'on est sur le bonus
    const hasBonus = currentEpisode && currentEpisode.twilight_zone_story;
    
    // Mettre à jour les boutons précédent/suivant
    if (isOnBonus) {
        prevBtn.disabled = false;
        nextBtn.disabled = true;
    } else {
        prevBtn.disabled = currentActIndex === 0;
        nextBtn.disabled = currentActIndex === allActs.length - 1 && !hasBonus;
    }
    
    // Afficher/masquer le bouton bonus
    if (hasBonus) {
        bonusBtn.style.display = 'flex';
        bonusBtn.classList.toggle('active', isOnBonus);
    } else {
        bonusBtn.style.display = 'none';
    }
    
    // Indicateurs d'actes (points de navigation)
    const indicator = document.getElementById('acts-indicator');
    if (!indicator) return;
    
    // Vider l'indicateur
    indicator.innerHTML = '';
    
    // Créer un point pour chaque acte
    allActs.forEach((actKey, index) => {
        const dot = document.createElement('div');
        const isActive = index === currentActIndex && !isOnBonus;
        dot.className = `act-dot ${isActive ? 'active' : ''}`;
        dot.dataset.index = index;
        dot.dataset.actName = ACT_NAMES[actKey] || actKey;
        dot.title = `${ACT_NAMES[actKey] || actKey} (Acte ${index + 1})`;
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

// Variables pour la détection de scroll
let scrollUpdateTimer = null;
let isNavigatingProgrammatically = false; // Flag pour éviter les mises à jour lors de navigation programmée

// Configuration de la navigation
function setupNavigation() {
    // Boutons précédent/suivant
    document.getElementById('nav-prev').addEventListener('click', () => {
        if (currentActIndex > 0) {
            isNavigatingProgrammatically = true;
            showAct(currentActIndex - 1);
            setTimeout(() => { isNavigatingProgrammatically = false; }, 1000);
        }
    });
    
    document.getElementById('nav-next').addEventListener('click', () => {
        if (currentActIndex < allActs.length - 1) {
            isNavigatingProgrammatically = true;
            showAct(currentActIndex + 1);
            setTimeout(() => { isNavigatingProgrammatically = false; }, 1000);
        } else if (currentActIndex === allActs.length - 1 && currentEpisode && currentEpisode.twilight_zone_story) {
            isNavigatingProgrammatically = true;
            showBonus();
            setTimeout(() => { isNavigatingProgrammatically = false; }, 1000);
        }
    });
    
    // Bouton bonus
    document.getElementById('nav-bonus').addEventListener('click', () => {
        isNavigatingProgrammatically = true;
        showBonus();
        setTimeout(() => { isNavigatingProgrammatically = false; }, 1000);
    });
    
    // Navigation au clavier
    document.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowLeft') {
            if (currentActIndex === -1) {
                isNavigatingProgrammatically = true;
                showAct(allActs.length - 1);
                setTimeout(() => { isNavigatingProgrammatically = false; }, 1000);
            } else if (currentActIndex > 0) {
                isNavigatingProgrammatically = true;
                showAct(currentActIndex - 1);
                setTimeout(() => { isNavigatingProgrammatically = false; }, 1000);
            }
        } else if (e.key === 'ArrowRight') {
            if (currentActIndex < allActs.length - 1) {
                isNavigatingProgrammatically = true;
                showAct(currentActIndex + 1);
                setTimeout(() => { isNavigatingProgrammatically = false; }, 1000);
            } else if (currentActIndex === allActs.length - 1 && currentEpisode && currentEpisode.twilight_zone_story) {
                isNavigatingProgrammatically = true;
                showBonus();
                setTimeout(() => { isNavigatingProgrammatically = false; }, 1000);
            }
        }
    });
    
    // Détection intelligente de l'acte visible lors du scroll
    setupScrollDetection();
}

// Détection intelligente basée sur la position de scroll
function setupScrollDetection() {
    // Supprimer l'ancien listener s'il existe
    window.removeEventListener('scroll', detectActiveActOnScroll);
    window.removeEventListener('scroll', detectActiveActOnScrollThrottled);
    
    // Fonction de détection avec throttling
    function detectActiveActOnScrollThrottled() {
        if (scrollUpdateTimer) {
            clearTimeout(scrollUpdateTimer);
        }
        
        scrollUpdateTimer = setTimeout(() => {
            if (!isNavigatingProgrammatically) {
                detectActiveActOnScroll();
            }
        }, 100); // Throttle à 100ms
    }
    
    // Ajouter le listener de scroll
    window.addEventListener('scroll', detectActiveActOnScrollThrottled, { passive: true });
    
    // Détecter aussi au chargement initial
    setTimeout(() => detectActiveActOnScroll(), 500);
}

// Détecter l'acte actuellement visible
function detectActiveActOnScroll() {
    if (!currentEpisode || allActs.length === 0) return;
    
    const headerHeight = document.querySelector('.header')?.offsetHeight || 0;
    const navHeight = document.querySelector('.acts-navigation')?.offsetHeight || 0;
    const viewportTop = window.scrollY + headerHeight + navHeight + 100; // Offset pour considérer un acte comme "actif"
    
    let closestActIndex = -1;
    let closestDistance = Infinity;
    
    // Vérifier chaque acte
    allActs.forEach((actKey, index) => {
        const actCard = document.getElementById(`act-${index}`);
        if (actCard) {
            const rect = actCard.getBoundingClientRect();
            const actTop = window.scrollY + rect.top;
            const actBottom = window.scrollY + rect.bottom;
            
            // Si l'acte est visible dans le viewport
            if (actTop <= viewportTop && actBottom >= viewportTop) {
                const distance = Math.abs(actTop - viewportTop);
                if (distance < closestDistance) {
                    closestDistance = distance;
                    closestActIndex = index;
                }
            }
        }
    });
    
    // Vérifier aussi la section bonus
    const twilightSection = document.getElementById('twilight-zone-section');
    if (twilightSection && currentEpisode.twilight_zone_story && !twilightSection.classList.contains('hidden')) {
        const rect = twilightSection.getBoundingClientRect();
        const sectionTop = window.scrollY + rect.top;
        const sectionBottom = window.scrollY + rect.bottom;
        
        if (sectionTop <= viewportTop && sectionBottom >= viewportTop) {
            const distance = Math.abs(sectionTop - viewportTop);
            if (distance < closestDistance) {
                closestActIndex = -1; // Bonus
            }
        }
    }
    
    // Mettre à jour si l'acte actif a changé
    if (closestActIndex !== currentActIndex && closestActIndex !== -2) {
        currentActIndex = closestActIndex;
        updateNavigation();
    }
}

// Échapper le HTML pour éviter les injections
// Rendu Markdown assaini : le contenu est généré par un LLM (et peut citer du web),
// il ne doit jamais être injecté dans le DOM sans DOMPurify. Sans DOMPurify -> texte échappé.
function renderMarkdown(text) {
    const source = text || '';
    if (typeof marked === 'undefined' || typeof DOMPurify === 'undefined') {
        return source.split(/\n\n+/).map(p => `<p>${escapeHtml(p)}</p>`).join('');
    }
    return DOMPurify.sanitize(marked.parse(source), { USE_PROFILES: { html: true } });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Extraire le nom de la source depuis une URL
function extractSourceName(url) {
    try {
        const urlObj = new URL(url);
        let hostname = urlObj.hostname;
        
        // Retirer www. si présent
        hostname = hostname.replace(/^www\./, '');
        
        // Extraire le domaine principal
        const parts = hostname.split('.');
        if (parts.length >= 2) {
            // Prendre les deux dernières parties (ex: "mit.edu" -> "MIT", "theatlantic.com" -> "The Atlantic")
            const domain = parts.slice(-2).join('.');
            
            // Nettoyer et formater le nom
            const domainName = domain.split('.')[0];
            
            // Cas spéciaux pour les domaines connus
            const knownSources = {
                'mit': 'MIT',
                'stanford': 'Stanford',
                'harvard': 'Harvard',
                'nature': 'Nature',
                'science': 'Science',
                'wired': 'Wired',
                'theatlantic': 'The Atlantic',
                'newyorker': 'The New Yorker',
                'guardian': 'The Guardian',
                'ted': 'TED',
                'wikipedia': 'Wikipedia',
                'arxiv': 'arXiv',
                'youtube': 'YouTube',
                'github': 'GitHub',
                'medium': 'Medium',
                'substack': 'Substack',
                'nautilus': 'Nautilus',
                'aeon': 'Aeon',
                'quanta': 'Quanta Magazine',
                'technologyreview': 'MIT Technology Review',
                'lesswrong': 'LessWrong',
                'sciencedaily': 'ScienceDaily',
                'phys': 'Phys.org',
                'bbc': 'BBC',
                'pbs': 'PBS',
                'arte': 'ARTE'
            };
            
            if (knownSources[domainName.toLowerCase()]) {
                return knownSources[domainName.toLowerCase()];
            }
            
            // Capitaliser la première lettre
            return domainName.charAt(0).toUpperCase() + domainName.slice(1);
        }
        
        return hostname;
    } catch (error) {
        // Si l'URL est invalide, retourner une valeur par défaut
        return 'Source';
    }
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
                
                // Gérer les boutons des actes normaux
                const otherIndex = allActs.indexOf(key);
                if (otherIndex >= 0) {
                    const otherBtn = document.getElementById(`audio-btn-${otherIndex}`);
                    if (otherBtn) {
                        otherBtn.querySelector('.audio-icon.play').style.display = 'block';
                        otherBtn.querySelector('.audio-icon.pause').style.display = 'none';
                        otherBtn.classList.remove('playing');
                    }
                }
                
                // Gérer le bouton Twilight Zone
                if (key === 'twilight_zone') {
                    const twilightBtn = document.getElementById('audio-btn-twilight-zone');
                    if (twilightBtn) {
                        twilightBtn.querySelector('.audio-icon.play').style.display = 'block';
                        twilightBtn.querySelector('.audio-icon.pause').style.display = 'none';
                        twilightBtn.classList.remove('playing');
                    }
                }
            }
        });
        
        // Arrêter les autres lecteurs si on joue twilight_zone
        if (actKey === 'twilight_zone') {
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
        }
        
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
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
                    <div>
                        <h3>${escapeHtml(story.title)}</h3>
                        <p class="twilight-zone-theme">Thème: ${escapeHtml(story.theme)}</p>
                    </div>
                    <div class="audio-controls" style="display: flex; gap: 0.5rem;">
                        <button class="audio-btn" id="audio-btn-twilight-zone" data-act-key="twilight_zone" style="display: none;" disabled>
                            <svg class="audio-icon play" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polygon points="5 3 19 12 5 21 5 3"></polygon>
                            </svg>
                            <svg class="audio-icon pause" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display: none;">
                                <rect x="6" y="4" width="4" height="16"></rect>
                                <rect x="14" y="4" width="4" height="16"></rect>
                            </svg>
                        </button>
                        <button class="speech-btn" id="speech-btn-twilight-zone" data-act-key="twilight_zone" style="display: none;" title="Lire avec la synthèse vocale">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
                                <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                                <line x1="12" y1="19" x2="12" y2="23"></line>
                                <line x1="8" y1="23" x2="16" y2="23"></line>
                            </svg>
                        </button>
                    </div>
                </div>
            </div>
            <div class="twilight-zone-content">
                ${renderMarkdown(story.story)}
            </div>
        `;
    } else {
        // Fallback si marked n'est pas disponible
        const paragraphs = story.story.split('\n\n').filter(p => p.trim());
        storyHTML = `
            <div class="twilight-zone-header">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
                    <div>
                        <h3>${escapeHtml(story.title)}</h3>
                        <p class="twilight-zone-theme">Thème: ${escapeHtml(story.theme)}</p>
                    </div>
                    <div class="audio-controls" style="display: flex; gap: 0.5rem;">
                        <button class="audio-btn" id="audio-btn-twilight-zone" data-act-key="twilight_zone" style="display: none;" disabled>
                            <svg class="audio-icon play" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polygon points="5 3 19 12 5 21 5 3"></polygon>
                            </svg>
                            <svg class="audio-icon pause" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display: none;">
                                <rect x="6" y="4" width="4" height="16"></rect>
                                <rect x="14" y="4" width="4" height="16"></rect>
                            </svg>
                        </button>
                        <button class="speech-btn" id="speech-btn-twilight-zone" data-act-key="twilight_zone" style="display: none;" title="Lire avec la synthèse vocale">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
                                <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                                <line x1="12" y1="19" x2="12" y2="23"></line>
                                <line x1="8" y1="23" x2="16" y2="23"></line>
                            </svg>
                        </button>
                    </div>
                </div>
            </div>
            <div class="twilight-zone-content">
                ${paragraphs.map(p => `<p>${escapeHtml(p)}</p>`).join('')}
            </div>
        `;
    }
    
    storyEl.innerHTML = storyHTML;
    
    // Vérifier la disponibilité audio et configurer les boutons
    const audioBtn = document.getElementById('audio-btn-twilight-zone');
    const speechBtn = document.getElementById('speech-btn-twilight-zone');
    if (audioBtn && speechBtn) {
        checkAudioAvailability('twilight_zone', audioBtn, 'twilight-zone', speechBtn);
        
        // Configurer le bouton speech
        if (speechSynthesis) {
            speechBtn.style.display = 'flex';
            speechBtn.addEventListener('click', () => toggleSpeech('twilight-zone'));
        }
    }
    
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
    if (!speechSynthesis || !('speechSynthesis' in window) || !window.speechSynthesis) {
        return null;
    }
    
    try {
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
        } else if (narrator === 'twilight') {
            // Twilight Zone : préférer voix masculine profonde
            // Priorité 1: Voix neurales/premium masculines profondes
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
                // Préférer Thomas ou voix masculine profonde
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
    } catch (error) {
        console.warn('Erreur lors de la récupération des voix:', error);
        return null;
    }
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
    
    // Récupérer le contenu (acte ou histoire Twilight Zone)
    let contentElement = null;
    let actCard = null;
    let narrator = 'narrator_1';
    
    if (index === 'twilight-zone') {
        // Cas spécial pour l'histoire Twilight Zone
        actCard = document.getElementById('twilight-zone-section');
        if (!actCard) return;
        contentElement = actCard.querySelector('.twilight-zone-content');
        if (!contentElement) return;
        // Utiliser la voix spéciale Twilight Zone (masculine profonde)
        narrator = 'twilight';
    } else {
        // Cas normal pour les actes
        actCard = document.getElementById(`act-${index}`);
        if (!actCard) return;
        contentElement = actCard.querySelector('.act-content');
        if (!contentElement) return;
        // Récupérer le narrateur de l'acte
        const act = currentEpisode.acts[allActs[index]];
        narrator = act?.narrator || 'narrator_1';
    }
    
    // Extraire le texte
    const text = extractTextFromHTML(contentElement);
    
    if (!text || text.length === 0) {
        console.warn('Aucun texte à lire');
        return;
    }
    
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
    } else if (narrator === 'twilight') {
        utterance.pitch = 0.85; // Plus grave pour Twilight Zone (voix masculine profonde)
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
        
        // Mettre en évidence l'acte ou la section en cours de lecture
        if (actCard) {
            actCard.classList.add('speaking');
        }
    };
    
    utterance.onend = () => {
        playIcon.style.display = 'block';
        if (pauseIcon) pauseIcon.style.display = 'none';
        btn.classList.remove('playing');
        btn.title = 'Lire avec la synthèse vocale';
        if (actCard) {
            actCard.classList.remove('speaking');
        }
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
        if (actCard) {
            actCard.classList.remove('speaking');
        }
        currentSpeechIndex = -1;
        currentUtterance = null;
        speechPaused = false;
        lastClickTime = 0;
    };
    
    // Lancer la lecture
    try {
        if (speechSynthesis && 'speechSynthesis' in window && window.speechSynthesis) {
    speechSynthesis.speak(utterance);
        } else {
            console.warn('Synthèse vocale non disponible');
            playIcon.style.display = 'block';
            if (pauseIcon) pauseIcon.style.display = 'none';
            btn.classList.remove('playing');
            btn.title = 'Synthèse vocale non disponible';
        }
    } catch (error) {
        console.error('Erreur lors de la lecture vocale:', error);
        playIcon.style.display = 'block';
        if (pauseIcon) pauseIcon.style.display = 'none';
        btn.classList.remove('playing');
        btn.title = 'Erreur de lecture vocale';
    }
}

// Arrêter la synthèse vocale
function stopSpeech() {
    if (speechSynthesis && 'speechSynthesis' in window && window.speechSynthesis) {
        try {
        speechSynthesis.cancel();
        } catch (error) {
            console.warn('Erreur lors de l\'arrêt de la synthèse vocale:', error);
        }
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
if ('speechSynthesis' in window && speechSynthesis) {
    // Chrome nécessite que les voix soient chargées
    if (speechSynthesis.onvoiceschanged !== undefined) {
    speechSynthesis.onvoiceschanged = () => {
            if (!speechSynthesis) return;
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
    }
    
    // Forcer le chargement des voix en créant un utterance vide
    // Cela force Chrome à charger les voix
    try {
    const dummyUtterance = new SpeechSynthesisUtterance('');
    dummyUtterance.volume = 0;
    speechSynthesis.speak(dummyUtterance);
    speechSynthesis.cancel();
    } catch (error) {
        console.warn('Erreur lors du chargement des voix:', error);
    }
    
    // Attendre que les voix soient chargées
    setTimeout(() => {
        if (!speechSynthesis) return;
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
        // Extraire le nom du fichier depuis différents formats de chemins
        let imageFilename = null;
        const runName = currentRunName || '';
        
        // Priorité 1: Utiliser l'attribut src original (avant que le navigateur ne le résolve)
        // C'est le plus fiable car il contient le nom du fichier tel qu'il est dans le markdown
        const originalSrc = img.getAttribute('src');
        if (originalSrc && originalSrc.includes('../images/')) {
            // Extraire le nom du fichier depuis le chemin relatif
            imageFilename = originalSrc.split('../images/')[1].split('?')[0].split('#')[0].trim();
            // Décoder si le navigateur a déjà encodé (certains navigateurs encodent même dans l'attribut)
            if (imageFilename && imageFilename.includes('%')) {
                try {
                    // Décoder plusieurs fois si nécessaire
                    let decoded = imageFilename;
                    let previousDecoded = '';
                    let decodeCount = 0;
                    while (decoded !== previousDecoded && decodeCount < 5) {
                        previousDecoded = decoded;
                        try {
                            decoded = decodeURIComponent(decoded);
                            decodeCount++;
                        } catch (e) {
                            break;
                        }
                    }
                    imageFilename = decoded;
                } catch (e) {
                    // Si le décodage échoue, utiliser tel quel
                }
            }
        }
        // Priorité 2: Chemin relatif dans le src résolu (../images/filename.png)
        else if (img.src && img.src.includes('../images/')) {
            imageFilename = img.src.split('../images/')[1].split('?')[0].split('#')[0].trim();
        }
        // Priorité 3: Chemin résolu par le navigateur (http://localhost:8000/../images/ ou /images/)
        else if (img.src) {
            try {
                // Essayer de détecter le nom du fichier depuis différents formats
                const srcUrl = new URL(img.src, window.location.origin);
                const pathname = srcUrl.pathname;
                
                // Chercher /images/ ou /../images/ dans le chemin
                if (pathname.includes('/images/')) {
                    imageFilename = pathname.split('/images/')[1];
                } else if (pathname.includes('/../images/')) {
                    imageFilename = pathname.split('/../images/')[1];
                } else if (pathname.startsWith('/images/')) {
                    imageFilename = pathname.replace('/images/', '');
                }
                
                // Décoder le nom du fichier s'il est déjà encodé par le navigateur
                if (imageFilename) {
                    try {
                        // Décoder plusieurs fois si nécessaire (gérer les encodages multiples)
                        let decoded = imageFilename;
                        let previousDecoded = '';
                        while (decoded !== previousDecoded) {
                            previousDecoded = decoded;
                            try {
                                decoded = decodeURIComponent(decoded);
                            } catch (e) {
                                break;
                            }
                        }
                        imageFilename = decoded;
                    } catch (e) {
                        // Si le décodage échoue, utiliser tel quel
                    }
                }
            } catch (e) {
                // Si l'URL ne peut pas être parsée, ignorer
            }
        }
        
        // Si on a trouvé un nom de fichier, convertir en chemin API
        if (imageFilename) {
            // Nettoyer le nom du fichier (enlever les paramètres de requête, etc.)
            imageFilename = imageFilename.split('?')[0].split('#')[0].trim();
            
            // Décoder si déjà encodé (éviter le double encodage)
            // Décoder plusieurs fois si nécessaire
            let decoded = imageFilename;
            let previousDecoded = '';
            let decodeCount = 0;
            while (decoded !== previousDecoded && decodeCount < 3) {
                previousDecoded = decoded;
                try {
                    decoded = decodeURIComponent(decoded);
                    decodeCount++;
                } catch (e) {
                    break;
                }
            }
            imageFilename = decoded;
            
            // Maintenant encoder une seule fois pour l'URL
            const encodedFilename = encodeURIComponent(imageFilename);
            img.src = `/api/images/${encodedFilename}?run=${encodeURIComponent(runName)}`;
        } else {
            // Si on ne peut pas extraire le nom, logger un avertissement
            console.warn('Impossible d\'extraire le nom du fichier image depuis:', img.src || img.getAttribute('src'));
        }
        
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

