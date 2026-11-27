import { state } from './state.js';
import { saveProgress } from './storage.js';
import { ACT_NAMES } from './config.js';
import { stopSpeech } from './speech.js';

// Barre de progression de lecture
export function setupReadingProgress() {
    const bar = document.getElementById('reading-progress');
    if (!bar) return;
    const update = () => {
        const max = document.documentElement.scrollHeight - window.innerHeight;
        bar.style.transform = `scaleX(${max > 0 ? Math.min(1, window.scrollY / max) : 0})`;
    };
    window.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update);
    update();
}

// Afficher un acte spécifique (met en évidence et scroll vers l'acte)
export function showAct(index, scroll = true) {
    // Arrêter la synthèse vocale si on change d'acte
    if (state.currentSpeechIndex !== index) {
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
        state.currentActIndex = index;
        
        if (!scroll) {
            updateNavigation();
            return;
        }
        
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
export function showBonus() {
    if (!state.currentEpisode || !state.currentEpisode.twilight_zone_story) {
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
        state.currentActIndex = -1; // -1 signifie qu'on est sur le bonus
        
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
// Mémorise la position de lecture et la reflète dans l'URL (lien partageable, sans polluer l'historique)
function persistReadingPosition() {
    if (document.body.dataset.view !== 'reader' || !state.currentRunName || !state.currentEpisode) return;
    const run = encodeURIComponent(state.currentRunName);
    if (state.currentActIndex === -1) {
        history.replaceState(null, '', `#/run/${run}/bonus`);
        return;
    }
    saveProgress(state.currentRunName, state.currentActIndex);
    history.replaceState(null, '', `#/run/${run}/acte-${state.currentActIndex + 1}`);
}

export function updateNavigation() {
    // Boutons précédent/suivant
    const prevBtn = document.getElementById('nav-prev');
    const nextBtn = document.getElementById('nav-next');
    const bonusBtn = document.getElementById('nav-bonus');
    
    if (!prevBtn || !nextBtn || !bonusBtn) return;
    
    persistReadingPosition();
    
    // Vérifier si on est sur le bonus ou sur le dernier acte
    const isOnBonus = state.currentActIndex === -1; // -1 signifie qu'on est sur le bonus
    const hasBonus = state.currentEpisode && state.currentEpisode.twilight_zone_story;
    
    // Mettre à jour les boutons précédent/suivant
    if (isOnBonus) {
        prevBtn.disabled = false;
        nextBtn.disabled = true;
    } else {
        prevBtn.disabled = state.currentActIndex === 0;
        nextBtn.disabled = state.currentActIndex === state.allActs.length - 1 && !hasBonus;
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
    state.allActs.forEach((actKey, index) => {
        const dot = document.createElement('div');
        const isActive = index === state.currentActIndex && !isOnBonus;
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
        bonusDot.textContent = '★';
        bonusDot.addEventListener('click', () => showBonus());
        indicator.appendChild(bonusDot);
    }
}

// Variables pour la détection de scroll
let scrollUpdateTimer = null;

let isNavigatingProgrammatically = false; // Flag pour éviter les mises à jour lors de navigation programmée

// Configuration de la navigation
export function setupNavigation() {
    // Boutons précédent/suivant
    document.getElementById('nav-prev').addEventListener('click', () => {
        if (state.currentActIndex > 0) {
            isNavigatingProgrammatically = true;
            showAct(state.currentActIndex - 1);
            setTimeout(() => { isNavigatingProgrammatically = false; }, 1000);
        }
    });
    
    document.getElementById('nav-next').addEventListener('click', () => {
        if (state.currentActIndex < state.allActs.length - 1) {
            isNavigatingProgrammatically = true;
            showAct(state.currentActIndex + 1);
            setTimeout(() => { isNavigatingProgrammatically = false; }, 1000);
        } else if (state.currentActIndex === state.allActs.length - 1 && state.currentEpisode && state.currentEpisode.twilight_zone_story) {
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
        // Uniquement dans le lecteur, hors saisie de texte, hors lightbox et sans modificateur
        if (document.body.dataset.view !== 'reader') return;
        if (e.altKey || e.ctrlKey || e.metaKey) return;
        if (e.target.closest && e.target.closest('input, textarea, select, dialog')) return;
        if (document.getElementById('lightbox')?.classList.contains('active')) return;
        if (e.key === 'ArrowLeft') {
            if (state.currentActIndex === -1) {
                isNavigatingProgrammatically = true;
                showAct(state.allActs.length - 1);
                setTimeout(() => { isNavigatingProgrammatically = false; }, 1000);
            } else if (state.currentActIndex > 0) {
                isNavigatingProgrammatically = true;
                showAct(state.currentActIndex - 1);
                setTimeout(() => { isNavigatingProgrammatically = false; }, 1000);
            }
        } else if (e.key === 'ArrowRight') {
            if (state.currentActIndex < state.allActs.length - 1) {
                isNavigatingProgrammatically = true;
                showAct(state.currentActIndex + 1);
                setTimeout(() => { isNavigatingProgrammatically = false; }, 1000);
            } else if (state.currentActIndex === state.allActs.length - 1 && state.currentEpisode && state.currentEpisode.twilight_zone_story) {
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
export function setupScrollDetection() {
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
export function detectActiveActOnScroll() {
    if (!state.currentEpisode || state.allActs.length === 0) return;
    
    const headerHeight = document.querySelector('.header')?.offsetHeight || 0;
    const navHeight = document.querySelector('.acts-navigation')?.offsetHeight || 0;
    const viewportTop = window.scrollY + headerHeight + navHeight + 100; // Offset pour considérer un acte comme "actif"
    
    // -2 = aucun acte sous la ligne de lecture, -1 = section bonus, >= 0 = acte
    let closestActIndex = -2;
    let closestDistance = Infinity;
    
    // Vérifier chaque acte
    state.allActs.forEach((actKey, index) => {
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
    if (twilightSection && state.currentEpisode.twilight_zone_story && !twilightSection.classList.contains('hidden')) {
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
    
    // Au-dessus du premier acte (titre, arc narratif) : on considère le premier acte actif
    if (closestActIndex === -2) {
        const firstCard = document.getElementById('act-0');
        if (firstCard && window.scrollY + firstCard.getBoundingClientRect().top > viewportTop) {
            closestActIndex = 0;
        }
    }
    
    // Mettre à jour si l'acte actif a changé
    if (closestActIndex !== state.currentActIndex && closestActIndex !== -2) {
        state.currentActIndex = closestActIndex;
        updateNavigation();
    }
}
