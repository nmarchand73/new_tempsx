import { initializeLightbox } from './lightbox.js';
import { setupLibrary } from './library.js';
import { setupReadingProgress } from './navigation.js';
import { route } from './router.js';
import { setupRunSelector } from './runs.js';
import { state } from './state.js';

function setupNewEpisodeDialog() {
    const dialog = document.getElementById('new-episode-dialog');
    const copyBtn = document.getElementById('copy-cmd-btn');
    if (!dialog) return () => {};
    if (copyBtn) {
        copyBtn.addEventListener('click', async () => {
            const cmd = document.getElementById('new-episode-cmd').textContent;
            try {
                await navigator.clipboard.writeText(cmd);
                copyBtn.textContent = 'Copié ✓';
            } catch {
                copyBtn.textContent = 'Sélectionnez et copiez';
            }
            setTimeout(() => { copyBtn.textContent = 'Copier la commande'; }, 1800);
        });
    }
    return () => (typeof dialog.showModal === 'function' ? dialog.showModal() : dialog.setAttribute('open', ''));
}

document.addEventListener('DOMContentLoaded', async () => {
    setupReadingProgress();

    // Synthèse vocale du navigateur (optionnelle)
    state.speechSynthesis = 'speechSynthesis' in window ? window.speechSynthesis : null;

    initializeLightbox();
    setupRunSelector();
    setupLibrary(setupNewEpisodeDialog());

    window.addEventListener('hashchange', route);
    await route();
});
