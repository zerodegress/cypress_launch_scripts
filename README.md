# Cypress Launch Scripts

Chinese version: [README_ZH.md](README_ZH.md)

Scripts for launching Cypress client/server on Linux.

## Linux Client Usage (`cypress_launch.py`)

### 1) Prerequisites

- `umu-run` (recommended) or `wine` installed
- For `umu-run`: set `WINEPREFIX` and `PROTONPATH` to choose the Wine prefix and Proton build you want to use
- Download the latest CypressLauncher from https://github.com/dotthefox/CypressLauncher
- Matching `cypress_*.dll` exists under `--launcher-dir`

### 2) Basic Command

```bash
WINEPREFIX=/path/to/prefix \
PROTONPATH=/path/to/proton \
./cypress_launch.py \
  --game GW2 \
  --game-dir "C:/Program Files/EA Games/Plants vs Zombies Garden Warfare 2" \
  --server-ip 127.0.0.1:25200 \
  --username your_name \
  --runner umu-run \
  --launcher-dir ~/Downloads/CypressLauncher-vX.Y.Z \
  --ea-launcher "C:/Program Files/Electronic Arts/EA Desktop/.../EALauncher.exe" \
  --use-mods \
  --mod-pack Default
```

### 3) Common Options

- `--ea-launcher`: required, path to EA Launcher executable
- `--ea-delay-seconds`: delay before game launch after EA starts (default `30`)
- `--runner`: `umu-run` / `wine` / `native` (`umu-run` recommended on Linux)
- `--launcher-dir`: required runtime assets directory. Point this to the latest CypressLauncher folder downloaded from https://github.com/dotthefox/CypressLauncher
- `--dry-run`: print launch command only, do not actually launch

### 4) Path Compatibility

`--game-dir` and `--ea-launcher` support both:

- Windows-style paths, e.g. `C:/Program Files/...`
- Linux-style paths, e.g. `/home/user/Games/...`

In Proton mode, the script handles path conversion automatically.

### 5) Shutdown Note

After the game exits, EA App may still keep running.  
If you want a full shutdown, close EA App manually.

## Dedicated Server

Use `cypress_launch_server.py` for dedicated server launch.  
It does not require `--ea-launcher`.

### Linux Dedicated Server Example

```bash
WINEPREFIX=/path/to/prefix \
PROTONPATH=/path/to/proton \
./cypress_launch_server.py \
  --game GW2 \
  --game-dir /home/zerodegress/Games/ea-app/drive_c/Program\ Files/EA\ Games/Plants\ vs\ Zombies\ Garden\ Warfare\ 2 \
  --device-ip 127.0.0.1 \
  --level Level_Coop_ZombossFactory \
  --inclusion 'GameMode=GraveyardOps0;TOD=Day;HostedMode=ServerHosted' \
  --launcher-dir ~/Downloads/CypressLauncher-vX.Y.Z \
  --runner umu-run \
  --use-mods \
  --mod-pack Default
```
