# SEUnpacker
<<<<<<< HEAD

SEUnpacker is a desktop utility for converting StreamElements alert and widget packs into Firebot-ready overlays, events, presets, and local resources.

## What it does

- Analyzes StreamElements alert/widget ZIP packs
- Installs local overlay resources into Firebot v5
- Creates Firebot overlay widgets and preset effects
- Supports StreamElements URL-based widget import flows
- Supports StreamElements login state and Twitch authorization
- Includes GitHub release update checking
- Includes an uninstall manager for SEUnpacker-installed packs

## Build on Windows

From the project folder, run:

```powershell
py -m pip install -r .\requirements.txt
.\build_windows.bat
```

The built executable will be created at:

```text
dist\SEUnpacker.exe
```

## Release updates

SEUnpacker checks GitHub Releases for updates from:

```text
https://github.com/itsMCThunder/SEUnpacker
```

Publish new builds as GitHub Releases and attach `SEUnpacker.exe` as a release asset.

## Important: do not commit local auth/cache data

Twitch OAuth tokens, StreamElements browser session data, Firebot profiles, generated output, and build artifacts should stay local and should not be committed.

The `.gitignore` in this repo excludes common local/cache/build folders, but always review `git status` before committing.
=======
SEUnpacker is a desktop conversion tool that helps streamers import StreamElements alert and widget packs into Firebot. It analyzes StreamElements packages, installs local overlay resources, creates Firebot widgets and preset effects, and supports StreamElements URL-based import flows with Twitch-connected data handling where possible.
>>>>>>> b15b5cd76f857462879636a4099b68fa81bb83b1
