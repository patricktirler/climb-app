// ClimbApp phone entry: choose a kind, fill in the form, entries are queued locally and uploaded to Google Drive.
// The desktop database is read from Drive for autocomplete and statistics.
import { DATA_FILE, FOLDER_NAME } from './config.js';
import * as data from './data.js';
import * as store from './db.js';
import * as drive from './drive.js';
import { buildForm, el, formatValue, openSheet, today } from './form.js';
import { renderStats } from './stats.js';
import { computeStats } from './statscalc.js';
import { makeContext } from './suggest.js';

const app = document.getElementById('app');
const TITLE_KEYS = ['name', 'area', 'place', 'gym', 'destination', 'site', 'mountain', 'text', 'weight'];

let spec;
let view = 'home';
let statsYear = Number(today().slice(0, 4));
let syncing = false;

const newId = () => crypto.randomUUID().replaceAll('-', '');

function toast(text, bad = false) {
  const t = el('div', `toast${bad ? ' bad' : ''}`, text);
  let box = document.getElementById('toasts');
  if (!box) { box = el('div'); box.id = 'toasts'; document.body.append(box); }
  box.append(t);
  setTimeout(() => t.remove(), bad ? 6000 : 2500);
}

// ------------------------------------------------------------------ helpers for entries
function titleOf({ kind, record: r }) {
  const key = TITLE_KEYS.find((k) => r[k]);
  const main = key === 'weight' ? `${r.weight} kg` : String(r[key] || spec.kinds[kind].label).slice(0, 70);
  return kind === 'sport_routes' && r.grade ? `${main}  ${r.grade}` : main;
}

const fileName = (entry) => `${entry.record.date || today()}_${entry.kind}_${entry.id}.json`;
const payload = (entry) => ({ format: 'climbapp-entry', version: 1, kind: entry.kind, record: entry.record });

/** Entries of this phone the desktop data does not contain (yet): they still count for suggestions and statistics. */
async function localOnly() {
  const known = data.ids();
  return (await store.allEntries()).filter((e) => !known.has(e.id));
}

const dataStatus = () => {
  const d = data.current();
  return d ? `Data of ${new Date(d.file.modifiedTime).toLocaleDateString()} · ${data.entryCount().toLocaleString('en')} entries`
    : `No data loaded: sign in with Sync to read ${DATA_FILE} from your Drive.`;
};

// ------------------------------------------------------------------ sync
async function refreshData(quiet) {
  try {
    const result = await data.refresh();
    if (quiet) return;
    if (result === 'updated') toast(`Data updated (${data.entryCount().toLocaleString('en')} entries)`);
    if (result === 'not-found') toast(`${DATA_FILE} not found in your Drive`, true);
    if (result === 'no-access') toast('No read access to Drive: Settings -> Grant read access', true);
  } catch (e) {
    if (e instanceof drive.AuthError || !quiet) throw e;
  }
}

async function syncNow(quiet = false) {
  if (syncing) return;
  if (!drive.isConfigured()) { openSettings(); return; }
  if (!drive.hasToken()) { drive.startSignIn(); return; }
  syncing = true;
  try {
    const waiting = (await store.allEntries()).filter((e) => !e.uploaded);
    if (waiting.length) {
      const byName = new Map(waiting.map((e) => [fileName(e), e]));
      await drive.uploadAll([...byName].map(([name, e]) => [name, payload(e)]), async (name) => {
        await store.putEntry({ ...byName.get(name), uploaded: true });
      });
      toast(`${waiting.length} uploaded`);
    } else if (!quiet) {
      toast('Nothing to upload');
    }
    await refreshData(quiet);
  } catch (e) {
    if (e instanceof drive.AuthError) toast('Signed out. Tap Sync to sign in again.', true);
    else toast(e.message === 'Failed to fetch' ? 'No connection. Entries stay on the phone.' : e.message, true);
  } finally {
    syncing = false;
    if (view === 'home') await showHome();
    if (view === 'stats') await showStats(statsYear);
  }
}

// ------------------------------------------------------------------ home
async function showHome() {
  view = 'home';
  const entries = (await store.allEntries()).sort((a, b) => b.created - a.created);
  const waiting = entries.filter((e) => !e.uploaded).length;

  const head = el('header', 'bar');
  head.append(el('h1', null, 'ClimbApp'));
  const sync = el('button', `btn${waiting ? ' primary' : ''}`, syncing ? 'Syncing …' : waiting ? `Sync (${waiting})` : 'Sync');
  sync.onclick = () => syncNow();
  const gear = el('button', 'btn icon', '⚙');
  gear.setAttribute('aria-label', 'Settings');
  gear.onclick = openSettings;
  head.append(sync, gear);

  const grid = el('div', 'kinds');
  for (const key of spec.order) {
    const b = el('button', 'kind', spec.kinds[key].label);
    b.style.setProperty('--c', spec.kinds[key].color);
    b.onclick = () => showForm(key);
    grid.append(b);
  }

  const stats = el('button', 'kind stats-link', 'Statistics');
  stats.onclick = () => showStats(statsYear);

  const list = el('div', 'entries');
  if (!entries.length) list.append(el('p', 'hint', 'No entries yet. Pick a kind above to add one.'));
  for (const entry of entries.slice(0, 40)) {
    const row = el('button', 'entry');
    row.style.setProperty('--c', spec.kinds[entry.kind].color);
    const text = el('span', 'entry-text');
    text.append(el('b', null, titleOf(entry)),
      el('small', null, `${spec.kinds[entry.kind].label} · ${formatValue({ type: 'date' }, entry.record.date)}`));
    row.append(text, el('span', `state${entry.uploaded ? ' ok' : ''}`, entry.uploaded ? '✓' : 'waiting'));
    row.onclick = () => entrySheet(entry);
    list.append(row);
  }
  app.replaceChildren(head, el('h2', 'section', 'New entry'), grid, el('h2', 'section', 'Overview'), stats,
    el('p', 'hint', dataStatus()), el('h2', 'section', 'Recent'), list);
}

function entrySheet(entry) {
  const body = el('div');
  body.append(el('p', null, titleOf(entry)),
    el('p', 'hint', entry.uploaded ? 'Already uploaded. Changes would not reach the desktop app, so duplicate it instead.'
      : 'Waiting for upload.'));
  const actions = [];
  if (!entry.uploaded) actions.push({ label: 'Edit', primary: true, onClick: () => showForm(entry.kind, entry) });
  actions.push(
    { label: 'Duplicate', primary: entry.uploaded, onClick: () => {
      const copy = { ...entry.record };
      for (const key of ['id', 'date', 'date_to']) delete copy[key];     // new id, date defaults to today
      showForm(entry.kind, null, copy);
    } },
    { label: 'Delete', danger: true, onClick: async () => {
      if (!confirm(entry.uploaded ? 'Remove from this phone? The uploaded copy stays in Drive.' : 'Delete this entry?')) return false;
      await store.deleteEntry(entry.id);
      await showHome();
    } },
    { label: 'Close' });
  openSheet({ title: spec.kinds[entry.kind].label, body, actions });
}

// ------------------------------------------------------------------ form
async function showForm(kind, entry = null, prefill = {}) {
  view = 'form';
  const k = spec.kinds[kind];
  const ctx = makeContext(kind, spec, data.current(), await localOnly());
  const form = buildForm(k.fields, entry ? entry.record : prefill, ctx);

  const head = el('header', 'bar');
  const back = el('button', 'btn', '‹ Back');
  back.onclick = showHome;
  head.append(back, el('h1', null, k.label));
  const save = el('button', 'btn primary wide', 'Save');
  save.onclick = async () => {
    const missing = form.missing();
    if (missing.length) { toast(`Missing: ${missing.join(', ')}`, true); return; }
    const id = entry?.id ?? newId();
    await store.putEntry({ id, kind, record: { ...form.read(), id }, created: entry?.created ?? Date.now(), uploaded: false });
    toast('Saved');
    await showHome();
    if (drive.hasToken()) syncNow(true);
  };
  const foot = el('div', 'save-bar');
  foot.append(save);
  app.replaceChildren(head, form.el, foot);
  window.scrollTo(0, 0);
}

// ------------------------------------------------------------------ statistics
async function showStats(year) {
  view = 'stats';
  statsYear = year;
  const head = el('header', 'bar');
  const back = el('button', 'btn', '‹ Back');
  back.onclick = showHome;
  const refresh = el('button', 'btn', syncing ? 'Loading …' : 'Reload');
  refresh.onclick = () => syncNow();
  head.append(back, el('h1', null, 'Statistics'), refresh);
  const d = data.current();
  if (!d) {
    app.replaceChildren(head, el('p', 'hint', dataStatus()));
    return;
  }
  const entries = [...Object.entries(d.entries).flatMap(([kind, list]) => list.map((record) => ({ kind, record }))),
    ...await localOnly()];
  const calc = computeStats(entries, spec.grades, year, today());
  app.replaceChildren(head, ...renderStats(calc, { spec, titleOf, onYear: showStats, status: dataStatus() }));
  window.scrollTo(0, 0);
}

// ------------------------------------------------------------------ settings
function openSettings() {
  const body = el('div', 'settings');
  const line = (text, cls = 'hint') => body.append(el('p', cls, text));

  if (!drive.isConfigured()) {
    line('Google sign-in is not set up yet: enter the OAuth client id in config.js (see README.md).', 'hint warn');
  } else {
    const until = drive.tokenExpiry();
    line(until ? `Signed in until ${until.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}.`
      : 'Not signed in. Tap Sync to sign in with Google.');
    line(`Entries are uploaded to the Drive folder "${FOLDER_NAME}".`);
    body.append(el('h3', null, 'Desktop data'));
    line(`${dataStatus()} Used for autocomplete and statistics.`);
    if (until && !drive.canRead()) line('Reading your Drive was not allowed when you signed in.', 'hint warn');
    const grant = el('button', 'btn', 'Grant read access');
    grant.onclick = () => drive.startSignIn({ consent: true });
    body.append(grant);
  }

  const clean = el('button', 'btn', 'Remove uploaded entries from this phone');
  clean.onclick = async () => {
    const done = (await store.allEntries()).filter((e) => e.uploaded);
    if (!done.length || !confirm(`Remove ${done.length} uploaded entries from this phone? Drive keeps them.`)) return;
    await Promise.all(done.map((e) => store.deleteEntry(e.id)));
    toast(`${done.length} removed`);
    if (view === 'home') showHome();
  };
  body.append(el('h3', null, 'Storage'), clean);
  openSheet({ title: 'Settings', body, actions: [{ label: 'Close', primary: true }] });
}

// ------------------------------------------------------------------ start
async function init() {
  navigator.storage?.persist?.();
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js').catch(() => {});
  const signIn = drive.consumeRedirect();
  [spec] = await Promise.all([fetch('kinds.json').then((r) => r.json()), data.load()]);
  await showHome();
  if (signIn?.error) toast(`Sign-in failed: ${signIn.error}`, true);
  else if (signIn?.ok || drive.hasToken()) syncNow(true);
}

init().catch((e) => { app.textContent = `Could not start: ${e.message}`; });
