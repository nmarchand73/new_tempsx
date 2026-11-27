// Persistance locale légère (progression de lecture). Tolère un localStorage indisponible.
const KEY = 'ntx:progress';

function readAll() {
    try {
        return JSON.parse(localStorage.getItem(KEY) || '{}') || {};
    } catch {
        return {};
    }
}

export function getProgress(run) {
    const entry = readAll()[run];
    return entry && Number.isInteger(entry.act) ? entry : null;
}

export function saveProgress(run, act) {
    if (!run) return;
    try {
        const all = readAll();
        all[run] = { act, ts: Date.now() };
        localStorage.setItem(KEY, JSON.stringify(all));
    } catch {
        /* stockage plein ou désactivé : on ignore */
    }
}

export function lastReadRun() {
    const all = readAll();
    const entries = Object.entries(all).sort((a, b) => (b[1].ts || 0) - (a[1].ts || 0));
    return entries.length ? entries[0][0] : null;
}
