# ClimbApp

A personal climbing logbook: climbing days, sport routes and ticks, alpine climbs, mountain tours, training,
cycling, paragliding, trips and competitions, with a calendar, lists, statistics and maps.

I started this as a school project when I first learned to code. Years later, with coding agents around, I finally had
the time to rework it from the ground up: a Python / PySide6 rewrite of the desktop app, plus a phone app for entering
data on the go.

## Desktop app

```
pip install -r requirements.txt
python main.py
```

Windows is the main target (`create_shortcut.ps1` makes a desktop shortcut). All data lives in one JSON file, by
default in a Google Drive folder, with automatic backups. It can import the old V1 format and 8a.nu logbook exports.
The database path can be changed in Settings.

## Phone app

[`pwa/`](pwa/) is a small installable web app (PWA) for entering data on an iPhone, offline included. Entries are
uploaded to Google Drive and imported by the desktop app; the phone also reads the database for autocomplete and
statistics. Setup is described in [pwa/README.md](pwa/README.md).

## Your own data

The database, backups and credentials are not part of the repository (see `.gitignore`). The one-time migrations in
`migrate.py` read an optional `migrate_private.json` for personal names and places; without it they leave those alone.
