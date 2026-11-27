import { state } from './state.js';
import { renderLibrary } from './library.js';
import { setupNavigation, showAct, showBonus, updateNavigation } from './navigation.js';
import { renderActs, renderOverview, showError } from './render.js';
import { fillRunSelector, loadEpisode, loadRuns, startEpisodePolling, stopEpisodePolling } from './runs.js';
import { stopSpeech } from './speech.js';
import { getProgress } from './storage.js';

const LIBRARY_REFRESH_MS = 10000;
let navigationReady = false;
let libraryTimer = null;

// #/                      -> bibliothèque
// #/run/<nom>[/acte-N]    -> lecteur (à l'acte N)
// #/run/<nom>/bonus       -> lecteur, histoire bonus
export function parseRoute(hash = location.hash) {
    const m = hash.replace(/^#\/?/, '').match(/^run\/([^/]+)(?:\/(acte-(\d+)|bonus))?\/?$/);
    if (!m) return { view: 'library' };
    let name;
    try {
        name = decodeURIComponent(m[1]);
    } catch {
        return { view: 'library' };
    }
    return { view: 'run', run: name, act: m[3] ? parseInt(m[3], 10) - 1 : null, bonus: m[2] === 'bonus' };
}

function setView(view) {
    document.body.dataset.view = view;
    document.getElementById('library-view').hidden = view !== 'library';
    document.getElementById('reader-view').hidden = view !== 'reader';
}

function stopMedia() {
    stopSpeech();
    Object.values(state.audioPlayers).forEach((audio) => audio.pause());
    state.audioPlayers = {};
}

function resetReader() {
    stopEpisodePolling();
    stopMedia();
    state.currentEpisode = null;
    state.allActs = [];
    state.currentActIndex = 0;
    state.lastEpisodeHash = null;
}

async function showLibrary() {
    resetReader();
    state.currentRunName = null;
    setView('library');
    document.title = 'NEW TEMPS X — Bibliothèque';
    await loadRuns();
    const search = document.getElementById('library-search');
    renderLibrary(search ? search.value : '');
    window.scrollTo(0, 0);
    // Rafraîchit la bibliothèque : un épisode en cours de génération se remplit sous vos yeux
    clearInterval(libraryTimer);
    libraryTimer = setInterval(async () => {
        if (document.body.dataset.view !== 'library' || document.hidden) return;
        await loadRuns();
        renderLibrary(search ? search.value : '');
    }, LIBRARY_REFRESH_MS);
}

async function openRun({ run, act, bonus }) {
    clearInterval(libraryTimer);

    // Même épisode déjà ouvert : on se contente de naviguer
    if (state.currentRunName === run && state.currentEpisode) {
        setView('reader');
        if (bonus) showBonus();
        else if (act !== null && act >= 0 && act < state.allActs.length) showAct(act);
        return;
    }

    // Position à restaurer, lue AVANT le rendu (qui écrase la progression enregistrée)
    const saved = getProgress(run);
    resetReader();
    state.currentRunName = run;
    setView('reader');
    window.scrollTo(0, 0);
    if (!state.availableRuns.length) await loadRuns();
    fillRunSelector();

    const ok = await loadEpisode(true);
    if (!ok || !state.currentEpisode || state.allActs.length === 0) {
        if (!ok) return; // loadEpisode a déjà affiché l'erreur
        showError("Impossible de charger l'épisode. Vérifiez que l'épisode contient des actes.");
        return;
    }

    if (!navigationReady) {
        setupNavigation();
        navigationReady = true;
    }
    renderOverview();
    renderActs();
    updateNavigation();
    startEpisodePolling();
    document.title = `${state.currentEpisode.episode_title || 'Épisode'} — NEW TEMPS X`;

    if (bonus && state.currentEpisode.twilight_zone_story) {
        showBonus();
    } else {
        const target = act !== null ? act : saved ? saved.act : 0;
        if (target > 0 && target < state.allActs.length) showAct(target);
    }
}

export async function route() {
    const r = parseRoute();
    if (r.view === 'run') await openRun(r);
    else await showLibrary();
}
