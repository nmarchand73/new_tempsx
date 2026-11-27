import { state } from './state.js';
import { checkAudioAvailability } from './audio.js';
import { ACT_NUMBERS } from './config.js';
import { processImages } from './lightbox.js';
import { setupScrollDetection, showAct } from './navigation.js';
import { handleSpeechClick, toggleSpeech } from './speech.js';
import { escapeHtml, extractSourceName, renderMarkdown } from './utils.js';

// Métadonnées sous le titre : nombre d'actes, coût de génération, date du run
export function renderHeroMeta() {
    const el = document.getElementById('hero-meta');
    if (!el || !state.currentEpisode) return;
    const parts = [];
    const actCount = Object.keys(state.currentEpisode.acts || {}).length;
    parts.push(`${actCount} acte${actCount > 1 ? 's' : ''}`);
    if (state.currentEpisode.twilight_zone_story) parts.push('+ histoire bonus');
    if (typeof state.currentEpisode.cost_usd === 'number') {
        parts.push(`${state.currentEpisode.cost_usd.toFixed(2).replace('.', ',')} $ de génération`);
    }
    const run = state.availableRuns.find(r => r.name === state.currentRunName);
    if (run && run.date) parts.push(run.date);
    el.textContent = parts.join('  ·  ');
}

// Afficher la vue d'ensemble
export function renderOverview() {
    if (!state.currentEpisode) return;
    
    // Titre de l'épisode
    const titleEl = document.getElementById('episode-title');
    if (titleEl) {
        titleEl.textContent = state.currentEpisode.episode_title || 'Sans titre';
    }
    renderHeroMeta();
    
    // Arc narratif (rendu Markdown)
    const narrativeArcEl = document.getElementById('narrative-arc');
    if (narrativeArcEl) {
        if (state.currentEpisode.narrative_arc) {
    if (typeof marked !== 'undefined') {
        narrativeArcEl.innerHTML = renderMarkdown(state.currentEpisode.narrative_arc);
    } else {
        // Fallback si marked n'est pas disponible
        const paragraphs = state.currentEpisode.narrative_arc.split('\n\n').filter(p => p.trim());
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
        scenarioEl.textContent = state.currentEpisode.scenario_input || 'Aucun scénario disponible.';
    }
    
    // Afficher l'histoire Twilight Zone si disponible
    renderTwilightZoneStory();
}

// Rendre tous les actes
export function renderActs() {
    if (!state.currentEpisode) return;
    
    const actsSection = document.getElementById('acts-section');
    if (!actsSection) {
        console.error('Élément acts-section introuvable dans le DOM');
        return;
    }
    
    actsSection.innerHTML = '';
    
    state.allActs.forEach((actKey, index) => {
        const act = state.currentEpisode.acts[actKey];
        const actCard = createActCard(actKey, act, index);
        actsSection.appendChild(actCard);
    });
    
    // Mettre en évidence le premier acte par défaut, sans scroller (la page démarre sur le titre
    // de l'épisode, et un nouveau rendu pendant la génération ne doit pas faire sauter la lecture)
    showAct(0, false);
    
    // Réinitialiser la détection de scroll après le rendu des actes
    setupScrollDetection();
}

// Créer une carte d'acte
export function createActCard(actKey, act, index) {
    const card = document.createElement('div');
    card.className = 'act-card';
    card.id = `act-${index}`;
    card.dataset.actKey = actKey;
    
    const actNumber = ACT_NUMBERS[actKey] || actKey;
    
    // Header
    const header = document.createElement('div');
    header.className = 'act-header';
    
    const headerLeft = document.createElement('div');
    headerLeft.className = 'act-heading';
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
    if (state.speechSynthesis && 'speechSynthesis' in window && window.speechSynthesis) {
        speechBtn.disabled = false;
        
        // Clic simple = pause/reprise, double-clic = arrêt
        speechBtn.addEventListener('click', (e) => handleSpeechClick(e, index));
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
            sourceSpan.textContent = sourceName;
            refItem.appendChild(sourceSpan);
            
            // Description
            if (ref.description) {
                const refDesc = document.createElement('span');
                refDesc.className = 'reference-description';
                refDesc.textContent = ref.description;
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

// Afficher une erreur
export function showError(message) {
    const mainContent = document.querySelector('.main-content');
    if (!mainContent) {
        console.error('Erreur:', message);
        return;
    }
    mainContent.innerHTML = `
        <div class="state-message error">
            <h2>Signal perdu</h2>
            <p class="state-detail">${escapeHtml(message)}</p>
            <p class="state-hint">
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

// Afficher l'histoire Twilight Zone
export function renderTwilightZoneStory() {
    if (!state.currentEpisode || !state.currentEpisode.twilight_zone_story) {
        const section = document.getElementById('twilight-zone-section');
        if (section) {
            section.classList.add('hidden');
        }
        return;
    }
    
    const section = document.getElementById('twilight-zone-section');
    const storyEl = document.getElementById('twilight-zone-story');
    
    if (!section || !storyEl) return;
    
    const story = state.currentEpisode.twilight_zone_story;
    
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
        if (state.speechSynthesis) {
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
