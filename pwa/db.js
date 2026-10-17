// Local storage (IndexedDB): entries waiting for upload (and the uploaded ones until removed) plus small settings.
const NAME = 'climbapp';
let opened;

function open() {
  opened ||= new Promise((resolve, reject) => {
    const req = indexedDB.open(NAME, 1);
    req.onupgradeneeded = () => {
      req.result.createObjectStore('entries', { keyPath: 'id' });
      req.result.createObjectStore('meta');
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  return opened;
}

async function run(store, mode, fn) {
  const db = await open();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(store, mode);
    const req = fn(tx.objectStore(store));
    tx.oncomplete = () => resolve(req?.result);
    tx.onerror = tx.onabort = () => reject(tx.error);
  });
}

// entry: {id, kind, record, created, uploaded}
export const putEntry = (entry) => run('entries', 'readwrite', (s) => s.put(entry));
export const allEntries = () => run('entries', 'readonly', (s) => s.getAll());
export const deleteEntry = (id) => run('entries', 'readwrite', (s) => s.delete(id));
export const getMeta = (key) => run('meta', 'readonly', (s) => s.get(key));
export const setMeta = (key, value) => run('meta', 'readwrite', (s) => s.put(value, key));
