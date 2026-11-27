import { state } from './state.js';

// Vérifier si l'audio est disponible
export async function checkAudioAvailability(actKey, audioBtn, index, speechBtn = null) {
    if (!state.currentRunName) {
        // Cacher le bouton audio si aucun run n'est sélectionné
        audioBtn.style.display = 'none';
        return;
    }
    
    const audioUrl = `/api/audio/${actKey}?run=${encodeURIComponent(state.currentRunName)}`;
    
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
export async function toggleAudio(actKey, index) {
    const btn = document.getElementById(`audio-btn-${index}`);
    const playIcon = btn.querySelector('.audio-icon.play');
    const pauseIcon = btn.querySelector('.audio-icon.pause');
    
    // Si un lecteur existe déjà pour cet acte
    if (state.audioPlayers[actKey]) {
        const audio = state.audioPlayers[actKey];
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
        // Construire l'URL audio avec le paramètre run
        const audioUrl = state.currentRunName 
            ? `/api/audio/${actKey}?run=${encodeURIComponent(state.currentRunName)}`
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
        
        state.audioPlayers[actKey] = audio;
        
        // Arrêter les autres lecteurs
        Object.keys(state.audioPlayers).forEach(key => {
            if (key !== actKey && state.audioPlayers[key]) {
                state.audioPlayers[key].pause();
                state.audioPlayers[key].currentTime = 0;
                
                // Gérer les boutons des actes normaux
                const otherIndex = state.allActs.indexOf(key);
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
            Object.keys(state.audioPlayers).forEach(key => {
                if (key !== actKey && state.audioPlayers[key]) {
                    state.audioPlayers[key].pause();
                    state.audioPlayers[key].currentTime = 0;
                    const otherIndex = state.allActs.indexOf(key);
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
