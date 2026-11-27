import { state } from './state.js';
import { extractTextFromHTML } from './utils.js';

// Obtenir une voix française selon le narrateur
export function getFrenchVoice(narrator = 'narrator_1') {
    if (!state.speechSynthesis || !('speechSynthesis' in window) || !window.speechSynthesis) {
        return null;
    }
    
    try {
    const voices = state.speechSynthesis.getVoices();
    
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

// Distingue clic simple (pause/reprise) et double-clic (arrêt) sur le bouton de lecture vocale
export function handleSpeechClick(event, index) {
    const now = Date.now();
    const timeSinceLastClick = now - lastClickTime;
    if (timeSinceLastClick < 300 && timeSinceLastClick > 0) {
        event.preventDefault();
        clearTimeout(clickTimeout);
        lastClickTime = 0;
        toggleSpeech(index, true);
    } else {
        lastClickTime = now;
        clearTimeout(clickTimeout);
        clickTimeout = setTimeout(() => {
            toggleSpeech(index, false);
            lastClickTime = 0;
        }, 300);
    }
}

export function toggleSpeech(index, isDoubleClick = false) {
    const btn = document.getElementById(`speech-btn-${index}`);
    const playIcon = btn.querySelector('.speech-icon.play');
    const pauseIcon = btn.querySelector('.speech-icon.pause');
    
    // Si double-clic, arrêter complètement
    if (isDoubleClick && state.currentSpeechIndex === index && (state.currentUtterance || state.speechPaused)) {
        stopSpeech();
        return;
    }
    
    // Si on est en train de lire cet acte
    if (state.currentSpeechIndex === index && state.currentUtterance) {
        if (state.speechPaused) {
            // Reprendre
            state.speechSynthesis.resume();
            state.speechPaused = false;
            playIcon.style.display = 'none';
            if (pauseIcon) pauseIcon.style.display = 'block';
            btn.classList.add('playing');
            btn.title = 'Mettre en pause (double-clic pour arrêter)';
        } else {
            // Pause
            state.speechSynthesis.pause();
            state.speechPaused = true;
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
        const act = state.currentEpisode.acts[state.allActs[index]];
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
        state.currentSpeechIndex = index;
        state.currentUtterance = utterance;
        state.speechPaused = false;
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
        state.currentSpeechIndex = -1;
        state.currentUtterance = null;
        state.speechPaused = false;
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
        state.currentSpeechIndex = -1;
        state.currentUtterance = null;
        state.speechPaused = false;
        lastClickTime = 0;
    };
    
    // Lancer la lecture
    try {
        if (state.speechSynthesis && 'speechSynthesis' in window && window.speechSynthesis) {
    state.speechSynthesis.speak(utterance);
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
export function stopSpeech() {
    if (state.speechSynthesis && 'speechSynthesis' in window && window.speechSynthesis) {
        try {
        state.speechSynthesis.cancel();
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
    
    state.currentSpeechIndex = -1;
    state.currentUtterance = null;
    state.speechPaused = false;
    lastClickTime = 0;
    
    // Annuler le timeout de clic simple s'il existe
    if (clickTimeout) {
        clearTimeout(clickTimeout);
        clickTimeout = null;
    }
}

// Charger les voix disponibles (nécessaire pour certains navigateurs)
if ('speechSynthesis' in window && state.speechSynthesis) {
    // Chrome nécessite que les voix soient chargées
    if (state.speechSynthesis.onvoiceschanged !== undefined) {
    state.speechSynthesis.onvoiceschanged = () => {
            if (!state.speechSynthesis) return;
        const voices = state.speechSynthesis.getVoices();
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
    state.speechSynthesis.speak(dummyUtterance);
    state.speechSynthesis.cancel();
    } catch (error) {
        console.warn('Erreur lors du chargement des voix:', error);
    }
    
    // Attendre que les voix soient chargées
    setTimeout(() => {
        if (!state.speechSynthesis) return;
        const voices = state.speechSynthesis.getVoices();
        if (voices.length > 0) {
            const frenchVoices = voices.filter(v => v.lang.startsWith('fr'));
            console.log('Voix françaises trouvées:', frenchVoices.length);
        }
    }, 500);
}

// ============================================
// Gestion des images : Lightbox, Lazy Loading, Erreurs
// ============================================
