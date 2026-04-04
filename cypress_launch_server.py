#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import os
import shlex
import shutil
import struct
import subprocess
import sys
from pathlib import Path


EXECUTABLES = {
    "GW1": "PVZ.Main_Win64_Retail.exe",
    "GW2": "GW2.Main_Win64_Retail.exe",
    "BFN": "PVZBattleforNeighborville.exe",
}

PATCHED_EXECUTABLES = {
    "GW2": "GW2.PreEAAC.exe",
    "BFN": "BFN.PreEAAC.exe",
}

SERVER_LAUNCH_ARGS = {
    "GW1": "-Online.ClientIsPresenceEnabled false -Online.ServerIsPresenceEnabled false "
    "-Game.Platform GamePlatform_Win32 -SyncedBFSettings.AllUnlocksUnlocked true "
    "-PingSite ams -name \"PVZGW Dedicated Server\"",
    "GW2": "-enableServerLog -platform Win32 -console -Game.Platform GamePlatform_Win32 "
    "-Game.EnableServerLog true -GameMode.SkipIntroHubNIS true -Online.Backend Backend_Local "
    "-Online.PeerBackend Backend_Local -PVZServer.MapSequencerEnabled false",
    "BFN": "-Online.ClientIsPresenceEnabled 0 -Online.ServerIsPresenceEnabled 0 "
    "-Game.Platform GamePlatform_Win32 -allUnlocksUnlocked "
    "-GameMode.OverrideRoundStartPlayerCount 1 -Online.Backend Backend_Local "
    "-Online.PeerBackend Backend_Local -PVZServer.MapSequencerEnabled false",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minimal Cypress dedicated server launcher")
    parser.add_argument("--game", choices=["GW1", "GW2", "BFN"], required=True)
    parser.add_argument("--game-dir", type=Path, required=True)
    parser.add_argument("--device-ip", required=True)
    parser.add_argument("--level", required=True, help="GW1/GW2 level or BFN dsub")
    parser.add_argument("--inclusion", required=True)
    parser.add_argument("--start-point", default="", help="BFN only")
    parser.add_argument("--server-password", default="")
    parser.add_argument("--player-count", default="")
    parser.add_argument("--additional-args", default="")
    parser.add_argument("--use-mods", action="store_true")
    parser.add_argument("--mod-pack", default="")
    parser.add_argument("--use-playlist", action="store_true")
    parser.add_argument("--playlist", default="", help="Playlist filename under game_dir/Playlists")
    parser.add_argument("--disable-ai-backfill", action="store_true", help="BFN only")
    parser.add_argument("--launcher-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--runner", choices=["auto", "native", "umu-run", "wine"], default="auto")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def get_rtp_launch_code() -> str:
    now = dt.datetime.utcnow()
    seed = ((now.year * 104729) ^ (now.month * 224737) ^ (now.day * 350377)) & 0xFFFFFFFF
    value = (seed ^ (((seed << 16) & 0xFFFFFFFF) ^ (seed >> 16))) & 0xFFFFFFFF
    return str(value)


def get_pe_timestamp(path: Path) -> dt.datetime:
    with path.open("rb") as f:
        if f.read(2) != b"MZ":
            raise ValueError(f"{path} is not a valid PE (bad DOS header)")
        f.seek(0x3C)
        pe_offset = struct.unpack("<I", f.read(4))[0]
        f.seek(pe_offset)
        if f.read(4) != b"PE\x00\x00":
            raise ValueError(f"{path} is not a valid PE (bad NT header)")
        file_header = f.read(20)
        timestamp = struct.unpack("<I", file_header[4:8])[0]
        return dt.datetime.utcfromtimestamp(timestamp)


def requires_patched_exe(game: str, exe_path: Path) -> bool:
    if game == "GW1":
        return False
    return get_pe_timestamp(exe_path).year >= 2024


def split_args(text: str) -> list[str]:
    if not text.strip():
        return []
    return shlex.split(text, posix=True)


def resolve_runner(mode: str) -> str:
    if mode != "auto":
        return mode
    if os.name == "nt":
        return "native"
    if shutil.which("umu-run"):
        return "umu-run"
    if shutil.which("wine"):
        return "wine"
    raise RuntimeError("No runner found. Install umu-run or wine, or pass --runner explicitly.")


def build_command(runner: str, exe_path: Path, exe_args: list[str]) -> list[str]:
    if runner == "native":
        return [str(exe_path), *exe_args]
    if runner == "umu-run":
        return ["umu-run", str(exe_path), *exe_args]
    if runner == "wine":
        return ["wine", str(exe_path), *exe_args]
    raise ValueError(f"Unsupported runner: {runner}")


def ensure_patched_exe(game: str, game_dir: Path, launcher_dir: Path, runner: str) -> str:
    base_exe = EXECUTABLES[game]
    base_exe_path = game_dir / base_exe
    if not requires_patched_exe(game, base_exe_path):
        return base_exe

    patched_exe = PATCHED_EXECUTABLES[game]
    patched_exe_path = game_dir / patched_exe
    if patched_exe_path.exists():
        return patched_exe

    patcher = launcher_dir / "courgette.exe"
    patch_file = launcher_dir / f"{game}.patch"
    if not patcher.exists():
        raise FileNotFoundError(f"Patcher not found: {patcher}")
    if not patch_file.exists():
        raise FileNotFoundError(f"Patch file not found: {patch_file}")

    apply_cmd = "-applybsdiff" if game == "BFN" else "-apply"
    patcher_cmd = build_command(
        runner,
        patcher,
        [apply_cmd, str(base_exe_path), str(patch_file), str(patched_exe_path)],
    )
    print("Creating patched executable...")
    result = subprocess.run(patcher_cmd, cwd=str(launcher_dir))
    if result.returncode != 0:
        raise RuntimeError(f"Patcher failed (exit: 0x{result.returncode:X})")
    return patched_exe


def build_server_args(ns: argparse.Namespace, game_dir: Path) -> list[str]:
    playlist_args: list[str] = []
    if ns.use_playlist:
        playlist_path = game_dir / "Playlists" / ns.playlist
        playlist_args = ["-usePlaylist", "-playlistFilename", str(playlist_path)]

    if ns.game in {"GW1", "GW2"}:
        args = [
            "-server",
            "-level",
            ns.level,
            "-listen",
            ns.device_ip,
            "-inclusion",
            ns.inclusion,
            "-allowMultipleInstances",
            "-Network.ServerAddress",
            ns.device_ip,
        ]
        if ns.server_password.strip():
            args.extend(["-Server.ServerPassword", ns.server_password.strip()])
        args.extend(playlist_args)
        args.extend(split_args(SERVER_LAUNCH_ARGS[ns.game]))
        if ns.player_count.strip():
            args.extend(["-Network.MaxClientCount", ns.player_count.strip()])
    else:
        args = [
            "-server",
            "-listen",
            ns.device_ip,
            "-dsub",
            ns.level,
            "-inclusion",
            ns.inclusion,
            "-startpoint",
            ns.start_point,
            "-allowMultipleInstances",
            "-enableServerLog",
            "-Network.ServerAddress",
            ns.device_ip,
        ]
        if ns.server_password.strip():
            args.extend(["-Server.ServerPassword", ns.server_password.strip()])
        args.extend(playlist_args)
        if ns.use_mods:
            args.extend(["-datapath", str(game_dir / "ModData" / ns.mod_pack)])
        if ns.disable_ai_backfill:
            args.extend(["-GameMode.BackfillMpWithAI", "false"])
        args.extend(split_args(SERVER_LAUNCH_ARGS[ns.game]))
        if ns.player_count.strip():
            count = ns.player_count.strip()
            args.extend(
                [
                    "-Network.MaxClientCount",
                    count,
                    "-NetObjectSystem.MaxServerConnectionCount",
                    count,
                    "-Online.DirtySockMaxConnectionCount",
                    count,
                ]
            )

    args.extend(split_args(ns.additional_args))
    return args


def validate_inputs(ns: argparse.Namespace, launcher_dir: Path, game_dir: Path) -> None:
    if not ns.device_ip.strip():
        raise ValueError("Device IP cannot be empty.")
    if not ns.level.strip():
        raise ValueError("Level/DSub cannot be empty.")
    if not ns.inclusion.strip():
        raise ValueError("Inclusion cannot be empty.")
    if not game_dir.exists():
        raise FileNotFoundError(f"Game directory not found: {game_dir}")

    exe_path = game_dir / EXECUTABLES[ns.game]
    if not exe_path.exists():
        raise FileNotFoundError(f"Game executable not found: {exe_path}")

    server_dll = launcher_dir / f"cypress_{ns.game}.dll"
    if not server_dll.exists():
        raise FileNotFoundError(f"Server DLL not found: {server_dll}")

    if ns.use_mods and not ns.mod_pack.strip():
        raise ValueError("--use-mods requires --mod-pack.")
    if ns.use_playlist and not ns.playlist.strip():
        raise ValueError("--use-playlist requires --playlist.")


def main() -> int:
    ns = parse_args()
    game_dir = ns.game_dir.expanduser().resolve()
    launcher_dir = ns.launcher_dir.expanduser().resolve()
    target_dll = game_dir / "dinput8.dll"

    try:
        validate_inputs(ns, launcher_dir, game_dir)
        runner = resolve_runner(ns.runner)
        exe_name = ensure_patched_exe(ns.game, game_dir, launcher_dir, runner)
        server_args = build_server_args(ns, game_dir)

        source_dll = launcher_dir / f"cypress_{ns.game}.dll"
        if not target_dll.exists():
            shutil.copy2(source_dll, target_dll)

        env = os.environ.copy()
        env["EARtPLaunchCode"] = get_rtp_launch_code()
        env["ContentId"] = "1026482"
        env["GW_LAUNCH_ARGS"] = subprocess.list2cmdline(server_args)
        if ns.use_mods:
            env["GAME_DATA_DIR"] = str(game_dir / "ModData" / ns.mod_pack)
        else:
            env.pop("GAME_DATA_DIR", None)
        if runner == "umu-run":
            env.setdefault("GAMEID", "cypresslauncher")

        game_cmd = build_command(runner, game_dir / exe_name, server_args)
        print("Launch command:", subprocess.list2cmdline(game_cmd))
        if ns.dry_run:
            return 0

        process = subprocess.Popen(game_cmd, cwd=str(game_dir), env=env)
        print(f"Server launched (PID {process.pid})")
        exit_code = process.wait()
        print(f"Server exited with code 0x{exit_code:X}")
        return 0
    except Exception as exc:
        print(f"Launch failed: {exc}", file=sys.stderr)
        return 1
    finally:
        try:
            target_dll.unlink(missing_ok=True)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
