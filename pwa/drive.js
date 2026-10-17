// Google sign-in (OAuth implicit flow via full-page redirect) and uploads to the Drive inbox folder.
//
// A redirect instead of the Google Identity Services popup, because popups are unreliable in iOS home-screen apps.
// Scopes: drive.file to create the inbox folder and the entry files, drive.readonly to read the desktop database
// (ClimbData.json, which the app did not create) for autocomplete and statistics.
import { CLIENT_ID, FOLDER_NAME } from './config.js';

const READ_SCOPE = 'https://www.googleapis.com/auth/drive.readonly';
const SCOPE = `https://www.googleapis.com/auth/drive.file ${READ_SCOPE}`;
const SCOPE_VERSION = '2';          // a token from the older drive.file-only version is ignored
const FILES = 'https://www.googleapis.com/drive/v3/files';

export class AuthError extends Error {}

const read = (key) => { try { return localStorage.getItem(key); } catch { return null; } };
const write = (key, value) => {
  try { value == null ? localStorage.removeItem(key) : localStorage.setItem(key, value); } catch { /* private mode */ }
};

export const isConfigured = () => /^[\w-]+\.apps\.googleusercontent\.com$/.test(CLIENT_ID) && !CLIENT_ID.startsWith('PASTE');
export const hasToken = () => !!read('token') && read('scopeV') === SCOPE_VERSION
  && Date.now() < Number(read('tokenExp')) - 60_000;
// Google lets the user untick single permissions: reading may be missing although uploads work
export const canRead = () => hasToken() && (read('scopes') || '').includes(READ_SCOPE);
export const tokenExpiry = () => (hasToken() ? new Date(Number(read('tokenExp'))) : null);

// must equal one of the "authorized redirect URIs" of the OAuth client
export const redirectUri = () => location.origin + location.pathname.replace(/index\.html$/, '');

export function startSignIn({ consent = false } = {}) {
  const state = crypto.randomUUID();
  write('oauthState', state);
  const params = new URLSearchParams({
    client_id: CLIENT_ID, redirect_uri: redirectUri(), response_type: 'token', scope: SCOPE, state,
    include_granted_scopes: 'true',
  });
  if (consent) params.set('prompt', 'consent');                // asks for permissions the user left out before
  location.assign(`https://accounts.google.com/o/oauth2/v2/auth?${params}`);
}

/** Call once at startup: picks up the token Google appended to the url. null = this was no sign-in redirect. */
export function consumeRedirect() {
  if (!/[#&](access_token|error)=/.test(location.hash)) return null;
  const params = new URLSearchParams(location.hash.slice(1));
  history.replaceState(null, '', location.pathname + location.search);
  if (params.get('error')) return { error: params.get('error') };
  if (params.get('state') !== read('oauthState')) return { error: 'state_mismatch' };
  write('oauthState', null);
  write('token', params.get('access_token'));
  write('scopes', params.get('scope') || '');
  write('scopeV', SCOPE_VERSION);
  write('tokenExp', String(Date.now() + Number(params.get('expires_in') || 3600) * 1000));
  return { ok: true };
}

async function call(url, init = {}) {
  const res = await fetch(url, { ...init, headers: { ...init.headers, Authorization: `Bearer ${read('token')}` } });
  if (res.status === 401) {
    write('token', null);
    throw new AuthError('Signed out');
  }
  if (!res.ok) {
    let message = res.statusText;
    try { message = (await res.json()).error.message; } catch { /* keep status text */ }
    throw new Error(`Drive: ${message} (${res.status})`);
  }
  return res;
}

async function ensureFolder() {
  const cached = read('folderId');
  if (cached) {
    try {
      const info = await (await call(`${FILES}/${cached}?fields=trashed`)).json();
      if (!info.trashed) return cached;
    } catch (e) {
      if (e instanceof AuthError) throw e;          // any other error: look the folder up again
    }
  }
  const query = encodeURIComponent(`name='${FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false`);
  let id = (await (await call(`${FILES}?q=${query}&fields=files(id)`)).json()).files?.[0]?.id;
  if (!id) {
    const created = await call(`${FILES}?fields=id`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: FOLDER_NAME, mimeType: 'application/vnd.google-apps.folder' }),
    });
    id = (await created.json()).id;
  }
  write('folderId', id);
  return id;
}

/** Uploads [name, object] pairs as JSON files into the inbox folder; onUploaded(name) runs after each one. */
export async function uploadAll(files, onUploaded) {
  const parent = await ensureFolder();
  for (const [name, object] of files) {
    const boundary = `climbapp${Math.random().toString(16).slice(2)}`;
    const body = `--${boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n`
      + `${JSON.stringify({ name, parents: [parent], mimeType: 'application/json' })}\r\n`
      + `--${boundary}\r\nContent-Type: application/json\r\n\r\n${JSON.stringify(object)}\r\n--${boundary}--`;
    await call('https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id', {
      method: 'POST', headers: { 'Content-Type': `multipart/related; boundary=${boundary}` }, body,
    });
    await onUploaded(name);
  }
}

/** The newest non-folder file with this name anywhere in the Drive, or null. */
export async function findFile(name) {
  const query = encodeURIComponent(`name='${name}' and trashed=false and mimeType!='application/vnd.google-apps.folder'`);
  const url = `${FILES}?q=${query}&orderBy=modifiedTime%20desc&pageSize=1&fields=files(id,modifiedTime)`;
  return (await (await call(url)).json()).files?.[0] || null;
}

export async function downloadJson(id) {
  return (await call(`${FILES}/${id}?alt=media`)).json();
}
