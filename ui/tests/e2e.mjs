// Test E2E du lecteur. Usage : node ui/tests/e2e.mjs   (Playwright doit être installé, Chromium disponible)
// Démarre le serveur sur un dossier de sortie temporaire avec un run de démonstration.
import { spawn, execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const tmp = mkdtempSync(join(tmpdir(), 'ntx-'));
const PORT = 8190 + Math.floor(Math.random() * 50);

// Le serveur lit OUTPUT_DIR depuis le projet : on lui passe un dossier via la variable NEWTEMPSX_OUTPUT_DIR.
execFileSync('python3', [join(root, 'ui/tests/make_demo.py'), join(tmp, 'output')]);
const server = spawn('python3', [join(root, 'ui/server.py'), '--port', String(PORT)], {
  env: { ...process.env, NEWTEMPSX_OUTPUT_DIR: join(tmp, 'output') }, stdio: 'ignore',
});
await new Promise(r => setTimeout(r, 1200));

let failures = 0;
const check = (name, ok, extra = '') => { console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${ok ? '' : '  ' + extra}`); if (!ok) failures++; };

const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  // --- Bibliothèque ---
  await page.goto(`http://127.0.0.1:${PORT}/`);
  await page.waitForSelector('.run-card', { timeout: 8000 });
  check('bibliothèque : une carte par run', (await page.locator('.run-card').count()) === 4);
  check('bibliothèque : badge « En cours » sur le run partiel', (await page.locator('.run-badge').count()) === 1);
  const demo = page.locator('.run-card', { hasText: 'Machines' });
  check('bibliothèque : titre et avancement 7/7', (await demo.locator('.run-progress i.on').count()) === 7);
  check('bibliothèque : couverture issue de l\'image du run', (await demo.locator('.run-cover img').count()) === 1);
  check('bibliothèque : lecteur masqué', await page.locator('#reader-view[hidden]').count() === 1);
  check('bibliothèque : coût affiché', (await demo.locator('.run-foot').textContent()).includes('4,37'));
  await page.fill('#library-search', 'zzz');
  check('bibliothèque : filtre sans résultat', (await page.locator('.run-card').count()) === 0 && (await page.locator('.empty-state').count()) === 1);
  await page.fill('#library-search', 'machines');
  check('bibliothèque : filtre avec résultat', (await page.locator('.run-card').count()) === 1);
  await page.fill('#library-search', '');
  await page.click('#new-episode-btn');
  check('dialogue « Nouvel épisode » ouvert', await page.locator('#new-episode-dialog[open]').count() === 1);
  await page.keyboard.press('Escape');

  // --- Lecteur ---
  await demo.click();
  await page.waitForSelector('.act-card', { timeout: 8000 });
  check('ouverture du lecteur : hash de l\'URL', /#\/run\/.+/.test(page.url()));
  check('lecteur visible, bibliothèque masquée', (await page.locator('#library-view[hidden]').count()) === 1 && (await page.locator('#reader-view[hidden]').count()) === 0);

  check('titre de l\'épisode affiché', (await page.textContent('#episode-title')).includes('Machines'));
  check('7 cartes d\'acte', (await page.locator('.act-card').count()) === 7);
  check('7 repères numérotés + bonus', (await page.locator('.act-dot').count()) === 8);
  check('méta du hero (coût)', (await page.textContent('#hero-meta')).includes('4,37'));
  check('arc narratif rendu en Markdown', (await page.locator('#narrative-arc strong').count()) === 1);
  check('sélecteur de runs rempli', (await page.locator('#run-selector option').count()) >= 1);
  await page.waitForTimeout(700);
  check('premier acte actif au chargement', await page.locator('#act-0.active').count() === 1);
  check('page démarre en haut (pas de scroll auto)', (await page.evaluate(() => window.scrollY)) < 50);

  await page.click('.act-dot:nth-child(3)');
  await page.waitForTimeout(1500);
  check('clic sur le repère III => acte 3 actif', await page.locator('#act-2.active').count() === 1);
  await page.click('#nav-next');
  await page.waitForTimeout(1200);
  check('bouton suivant => acte 4 actif', await page.locator('#act-3.active').count() === 1);
  await page.click('#nav-prev');
  await page.waitForTimeout(1200);
  check('bouton précédent => acte 3 actif', await page.locator('#act-2.active').count() === 1);

  check('sources affichées', (await page.locator('#act-0 .reference-link').count()) >= 1);

  // Lightbox
  await page.locator('#act-0 .act-content img').first().scrollIntoViewIfNeeded();
  await page.waitForTimeout(500);
  check('image intégrée dans l\'acte', (await page.locator('#act-0 .act-content img').count()) === 1);
  await page.locator('#act-0 .act-content img').first().click();
  await page.waitForTimeout(400);
  check('lightbox ouverte au clic', await page.locator('#lightbox.active').count() === 1);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);
  check('lightbox fermée avec Échap', await page.locator('#lightbox.active').count() === 0);

  // Bonus
  await page.click('#nav-bonus');
  await page.waitForTimeout(1000);
  check('bonus : section visible', await page.locator('#twilight-zone-section:not(.hidden)').count() === 1);
  check('bonus : titre de la nouvelle', (await page.textContent('#twilight-zone-story')).includes('Dernier Interprète'));
  await page.click('.act-dot:nth-child(1)');
  await page.waitForTimeout(800);
  check('retour à un acte masque le bonus', await page.locator('#twilight-zone-section.hidden').count() === 1);

  // Clavier
  await page.click('.act-dot:nth-child(2)');
  await page.waitForTimeout(1200);
  await page.keyboard.press('ArrowLeft');
  await page.waitForTimeout(800);
  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(1000);
  check('flèche droite => acte suivant', await page.locator('#act-1.active').count() === 1);

  // Position de lecture : URL partageable + reprise
  check('URL reflète l\'acte courant', /\/acte-2$/.test(page.url()), page.url());
  const deep = page.url();
  await page.click('#nav-back');
  await page.waitForSelector('.run-card');
  check('retour bibliothèque : vue bibliothèque', await page.locator('#library-view[hidden]').count() === 0);
  check('carte : reprise à l\'acte II', (await page.locator('.run-card', { hasText: 'Machines' }).locator('.run-resume').textContent()).includes('acte II'));
  await page.goto(deep.replace(/acte-\d+/, 'acte-5'));
  await page.reload();
  await page.waitForSelector('.act-card');
  await page.waitForTimeout(1800);
  check('lien profond : acte 5 actif', await page.locator('#act-4.active').count() === 1);
  await page.goBack().catch(() => {});

  // Sécurité : le contenu est assaini
  check('pas de script injecté', (await page.locator('.act-content script').count()) === 0);
  check('aucune erreur JS', errors.length === 0, errors.join(' | '));
} finally {
  await browser.close();
  server.kill();
  rmSync(tmp, { recursive: true, force: true });
}
console.log(failures ? `\n${failures} échec(s)` : '\nTous les tests E2E passent');
process.exit(failures ? 1 : 0);
