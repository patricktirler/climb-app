// The desktop database (ClimbData.json from Google Drive), cached in IndexedDB for offline use.
import { DATA_FILE } from './config.js';
import * as drive from './drive.js';
import * as store from './db.js';

let dataset = null;       // {file: {id, modifiedTime}, fetched, entries: {kind: [record]}, places, methods}

export async function load() {
  dataset = (await store.getMeta('dataset')) || null;
  return dataset;
}

export const current = () => dataset;
export const entryCount = () => Object.values(dataset?.entries || {}).reduce((n, list) => n + list.length, 0);

/** Ids of the entries the desktop already has (entries from this phone with these ids are not counted twice). */
export const ids = () => new Set(Object.values(dataset?.entries || {}).flat().map((r) => r.id));

/** Downloads the file if it changed. Resolves 'updated' | 'current' | 'not-found' | 'no-access'. */
export async function refresh() {
  if (!drive.canRead()) return 'no-access';
  const file = await drive.findFile(DATA_FILE);
  if (!file) return 'not-found';
  if (dataset?.file?.id === file.id && dataset.file.modifiedTime === file.modifiedTime) return 'current';
  const raw = await drive.downloadJson(file.id);
  dataset = {
    file: { id: file.id, modifiedTime: file.modifiedTime }, fetched: Date.now(),
    entries: raw.entries || {}, places: raw.places || {}, methods: raw.training?.methods || [],
  };
  await store.setMeta('dataset', dataset);
  return 'updated';
}
