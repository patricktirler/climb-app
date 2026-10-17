# ClimbApp phone app (PWA)

Enter climbing days, routes, tours, training … on the iPhone. Entries are stored on the phone first (works offline) and
uploaded to the Google Drive folder `ClimbApp-Inbox`. The desktop app imports them from there automatically.
The phone also reads `ClimbData.json` (the desktop database in Drive) for autocomplete, dependent dropdowns
(country -> region -> area -> crag) and a statistics screen. The data is cached, so both work offline.

```
iPhone (PWA) --upload--> Google Drive: ClimbApp-Inbox --Drive for Desktop--> D:\Google Drive\ClimbApp-Inbox --inbox.py--> ClimbData.json
```

## One-time setup

1. **Google Cloud** (free): console.cloud.google.com -> new project -> *APIs & Services*
   - enable **Google Drive API**
   - *OAuth consent screen*: user type External, app name ClimbApp, add your Google account as test user and add the
     scopes `drive.file` (write the inbox folder) and `drive.readonly` (read `ClimbData.json`). `drive.readonly` is a
     restricted scope: keep the app in *Testing* mode, Google then shows "has not verified this app" once at sign-in
     (Advanced -> continue). Tick both permissions; if you left reading out, Settings -> *Grant read access*.
   - *Credentials* -> Create credentials -> **OAuth client ID** -> type **Web application**
   - *Authorized redirect URIs*: the exact address of the app, e.g. `https://USER.github.io/REPO/`
     (add `http://localhost:8765/` for testing on the PC)
   - copy the client id into `config.js`
2. **Host** the `pwa/` folder over HTTPS. With GitHub Pages: push the repo, Settings -> Pages -> Source *GitHub Actions*;
   `.github/workflows/pwa.yml` publishes only `pwa/` (never the rest of the repo).
3. **iPhone**: open the address in *Safari* -> Share -> *Add to Home Screen*, start ClimbApp from the home screen, tap
   **Sync** and sign in with Google.
4. **Desktop**: install Google Drive for Desktop. The app looks in `D:\Google Drive\ClimbApp-Inbox`; change it in
   Settings -> *Phone app inbox* if your Drive lives elsewhere.

Data: `config.js` names the file to read (`DATA_FILE`, default `ClimbData.json`). The newest file with that name in
your Drive is downloaded at startup and on **Sync** when it changed (about 1.5 MB). Entries made on the phone that the
desktop has not imported yet are included in suggestions and statistics.

## Notes

- After changing `schema.py` run `python make_pwa.py` (rewrites `kinds.json`) and redeploy. Bump `CACHE` in `sw.js`
  when the list of files changes. A new version appears the second time the app is started.
- Google's access token lasts one hour; after that **Sync** signs in again (one redirect, no password). The token
  can read your whole Drive for that hour (`drive.readonly`); it is only kept on the phone.
- An uploaded entry cannot be edited on the phone (the desktop skips ids it already has): duplicate it instead.
- Imported files move to `imported/` in the inbox, unusable ones to `rejected/`; problems are logged to
  `%APPDATA%\ClimbAppV2\inbox.log`.
- Local test: `cd pwa && python -m http.server 8765`, then http://localhost:8765/
