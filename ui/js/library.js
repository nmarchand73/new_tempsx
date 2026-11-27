import { state } from './state.js';
import { getProgress, lastReadRun } from './storage.js';
import { escapeHtml } from './utils.js';

const ROMAN = ['', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII'];

// Teinte déterministe d'après le nom du run : chaque couverture sans image a sa propre lumière
function hueFor(name) {
    let h = 0;
    for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) % 360;
    return h;
}

function formatCost(cost) {
    return typeof cost === 'number' ? `${cost.toFixed(2).replace('.', ',')} $` : '';
}

function cardHtml(run, resumeRun) {
    const progress = getProgress(run.name);
    const resumeAct = progress && progress.act > 0 ? progress.act + 1 : 0;
    const cover = run.cover
        ? `<img src="/api/images/${encodeURIComponent(run.cover)}?run=${encodeURIComponent(run.name)}" alt="" loading="lazy">`
        : `<span class="run-cover-mark" aria-hidden="true">${ROMAN[Math.min(run.acts, 7)] || 'X'}</span>`;
    const segments = Array.from({ length: 7 }, (_, i) => `<i class="${i < run.acts ? 'on' : ''}"></i>`).join('');
    const foot = [
        run.audio ? `<span title="Pistes audio">♪ ${run.audio}</span>` : '',
        run.images ? `<span title="Images">▣ ${run.images}</span>` : '',
        run.has_twilight ? '<span title="Histoire bonus">★ bonus</span>' : '',
        formatCost(run.cost_usd) ? `<span title="Coût de génération">${formatCost(run.cost_usd)}</span>` : '',
    ].filter(Boolean).join('');
    const badge = run.complete ? '' : '<span class="run-badge">En cours</span>';
    const resume = resumeAct
        ? `<span class="run-resume">Reprendre à l'acte ${ROMAN[resumeAct] || resumeAct} →</span>`
        : `<span class="run-resume">${run.complete ? 'Lire →' : 'Suivre →'}</span>`;
    const last = run.name === resumeRun ? ' is-last' : '';
    return `
        <a class="run-card${last}" href="#/run/${encodeURIComponent(run.name)}" role="listitem" style="--hue:${hueFor(run.name)}">
            <div class="run-cover">${cover}${badge}</div>
            <div class="run-body">
                <p class="run-meta">${escapeHtml(run.date || '')} · ${run.acts} acte${run.acts > 1 ? 's' : ''}</p>
                <h3 class="run-title">${escapeHtml(run.title || run.name)}</h3>
                <p class="run-scenario">${escapeHtml(run.scenario || '')}</p>
                <div class="run-progress" role="img" aria-label="${run.acts} actes sur 7">${segments}</div>
                <div class="run-foot"><span class="run-stats">${foot}</span>${resume}</div>
            </div>
        </a>`;
}

export function renderLibrary(filter = '') {
    const grid = document.getElementById('library-grid');
    const meta = document.getElementById('library-meta');
    const toolbar = document.getElementById('library-toolbar');
    if (!grid) return;

    const runs = state.availableRuns;
    const q = filter.trim().toLowerCase();
    const shown = q
        ? runs.filter(r => `${r.title} ${r.scenario} ${r.name}`.toLowerCase().includes(q))
        : runs;
    const resumeRun = lastReadRun();

    if (meta) {
        const totalCost = runs.reduce((sum, r) => sum + (typeof r.cost_usd === 'number' ? r.cost_usd : 0), 0);
        meta.textContent = runs.length
            ? `${runs.length} épisode${runs.length > 1 ? 's' : ''}${totalCost ? `  ·  ${formatCost(totalCost)} de génération` : ''}`
            : '';
    }
    if (toolbar) toolbar.classList.toggle('only-action', runs.length < 4);

    if (!runs.length) {
        grid.innerHTML = `
            <div class="empty-state">
                <p class="empty-mark" aria-hidden="true">X</p>
                <h3>Aucun épisode pour l'instant</h3>
                <p>Générez votre premier épisode : il apparaîtra ici et se remplira acte par acte.</p>
                <pre class="dialog-code"><code>python app.py "Votre scénario"</code></pre>
            </div>`;
        return;
    }
    if (!shown.length) {
        grid.innerHTML = `<div class="empty-state"><h3>Aucun résultat</h3><p>Aucun épisode ne correspond à « ${escapeHtml(filter)} ».</p></div>`;
        return;
    }
    grid.innerHTML = shown.map(r => cardHtml(r, resumeRun)).join('');
}

export function setupLibrary(onNewEpisode) {
    const search = document.getElementById('library-search');
    if (search) search.addEventListener('input', () => renderLibrary(search.value));
    const btn = document.getElementById('new-episode-btn');
    if (btn) btn.addEventListener('click', onNewEpisode);
}
