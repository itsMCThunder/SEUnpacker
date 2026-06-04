# SEUnpacker


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



