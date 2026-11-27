import { state } from './state.js';
import { processImages } from './lightbox.js';
import { renderActs, renderOverview, renderTwilightZoneStory, showError } from './render.js';
import { escapeHtml, renderMarkdown } from './utils.js';

// Démarrer le polling pour détecter les mises à jour de l'épisode
export function startEpisodePolling() {
    // Arrêter le polling existant s'il y en a un
    stopEpisodePolling();
    
    // Poller toutes les 20 secondes pour détecter les mises à jour
    state.episodePollingInterval = setInterval(async () => {
        if (state.currentRunName) {
            await loadEpisode(false); // Ne pas forcer l'update, juste vérifier
        }
    }, 20000); // 20 secondes
    
    console.log('🔄 Polling de l\'épisode activé (vérification toutes les 20 secondes)');
}

// Arrêter le polling
export function stopEpisodePolling() {
    if (state.episodePollingInterval) {
        clearInterval(state.episodePollingInterval);
        state.episodePollingInterval = null;
        console.log('🛑 Polling de l\'épisode arrêté');
    }
}

// Charger la liste des runs disponibles
export async function loadRuns() {
    try {
        const response = await fetch('/api/runs');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        state.availableRuns = await response.json();
    } catch (error) {
        console.error('Erreur lors du chargement des runs:', error);
        state.availableRuns = [];
    }
}

// Remplir le sélecteur de run (visible dans le lecteur) ; le changement navigue vers le run choisi
export function fillRunSelector() {
    const selector = document.getElementById('run-selector');
    if (!selector) return;
    selector.innerHTML = '';
    if (state.availableRuns.length === 0) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = 'Aucun run disponible';
        selector.appendChild(option);
        selector.disabled = true;
        return;
    }
    selector.disabled = false;
    state.availableRuns.forEach((run, index) => {
        const option = document.createElement('option');
        option.value = run.name;
        const date = run.date ? ` (${run.date})` : '';
        option.textContent = `${index === 0 ? '● ' : ''}${run.title || run.name}${date}`;
        option.title = `Run: ${run.name}\nScénario: ${run.scenario || 'Pas de scénario'}`;
        option.selected = run.name === state.currentRunName;
        selector.appendChild(option);
    });
}

export function setupRunSelector() {
    const selector = document.getElementById('run-selector');
    if (!selector) return;
    selector.addEventListener('change', (e) => {
        if (e.target.value) location.hash = `#/run/${encodeURIComponent(e.target.value)}`;
    });
}

// Calculer un hash simple du contenu d'un épisode pour détecter les changements
export function calculateEpisodeHash(episode) {
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
export function updateEpisodeDisplay() {
    if (!state.currentEpisode) return;
    
    // Mettre à jour la vue d'ensemble si nécessaire
    renderOverview();
    
    // Mettre à jour chaque acte qui a changé
    state.allActs.forEach((actKey, index) => {
        const act = state.currentEpisode.acts[actKey];
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
export async function loadEpisode(forceUpdate = false) {
    if (!state.currentRunName) {
        console.warn('Aucun run sélectionné, impossible de charger l\'épisode');
        if (forceUpdate) {
            showError('Aucun run sélectionné. Sélectionnez un run dans le menu déroulant.');
        }
        return false;
    }
    
    try {
        // Construire l'URL avec le paramètre run et un timestamp pour éviter le cache
        const url = `/api/episode.json?run=${encodeURIComponent(state.currentRunName)}&t=${Date.now()}`;
        
        const response = await fetch(url);
        if (!response.ok) {
            if (response.status === 404) {
                if (forceUpdate) {
                    throw new Error(`Run "${state.currentRunName}" introuvable`);
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
        const hasChanged = newHash !== state.lastEpisodeHash;
        
        if (!hasChanged && !forceUpdate) {
            // Pas de changement, ne rien faire
            return false;
        }
        
        // Mettre à jour l'épisode
        const wasFirstLoad = state.currentEpisode === null;
        state.currentEpisode = newEpisode;
        state.lastEpisodeHash = newHash;
        
        // Préparer la liste des actes
        state.allActs = Object.keys(state.currentEpisode.acts)
            .sort((a, b) => {
                const numA = parseInt(a.replace('acte_', ''));
                const numB = parseInt(b.replace('acte_', ''));
                return numA - numB;
            });
        
        console.log('Épisode chargé:', state.currentEpisode);
        console.log('Actes trouvés:', state.allActs.length);
        
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
