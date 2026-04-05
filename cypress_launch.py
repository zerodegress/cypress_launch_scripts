#!/usr/bin/env python3
import argparse
import datetime as dt
import os
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
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

SPECIAL_LAUNCH_ARGS = {
    "GW1": "-GameTime.MaxSimFps -1",
    "GW2": "-GameMode.SkipIntroHubNIS true",
    "BFN": "-GameMode.ShouldSkipHUBTutorial 1 -GameMode.SocialHUBSkipStationTutorials 1",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minimal Cypress game launcher")
    parser.add_argument("--game", choices=["GW1", "GW2", "BFN"], required=True)
    parser.add_argument("--game-dir", type=Path, required=True)
    parser.add_argument("--server-ip", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--server-password", default="")
    parser.add_argument("--ea-launcher", type=Path, required=True, help="Path to EA launcher executable")
    parser.add_argument("--ea-delay-seconds", type=int, default=30, help="Seconds to wait after launching EA")
    parser.add_argument("--additional-args", default="")
    parser.add_argument("--fov", type=float, default=None)
    parser.add_argument("--use-mods", action="store_true")
    parser.add_argument("--mod-pack", default="")
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


def build_proton_dual_launch_command(
    runner: str, script_path: Path
) -> list[str]:
    if runner not in {"umu-run", "wine"}:
        raise ValueError(f"Unsupported proton runner: {runner}")
    launcher = "umu-run" if runner == "umu-run" else "wine"
    return [launcher, r"C:\windows\system32\cmd.exe", "/c", unix_to_wine_host_path(script_path)]


def unix_to_wine_host_path(path: Path) -> str:
    return f"Z:{str(path.resolve()).replace('/', '\\')}"

def escape_batch_value(value: str) -> str:
    return value.replace("%", "%%").replace('"', '^"')


def write_proton_launch_script(
    ea_launcher: str,
    game_exe_path: str,
    game_args: list[str],
    env_vars: dict[str, str],
    ea_delay_seconds: int,
) -> Path:
    fd, temp_path = tempfile.mkstemp(prefix="cypress_launch_", suffix=".bat")
    os.close(fd)
    script_path = Path(temp_path)
    game_args_line = subprocess.list2cmdline(game_args)
    env_lines = [f'set "{key}={escape_batch_value(value)}"' for key, value in env_vars.items()]
    content = "\r\n".join(
        [
            "@echo off",
            "setlocal",
            *env_lines,
            f'set "EA_PATH={escape_batch_value(ea_launcher)}"',
            f'set "GAME_EXE_PATH={escape_batch_value(game_exe_path)}"',
            "if \"%EA_PATH:~1,1%\"==\":\" (",
            "  start \"\" /b /exec \"%EA_PATH%\"",
            ") else (",
            "  start \"\" /b /unix \"%EA_PATH%\"",
            ")",
            f"ping -n {ea_delay_seconds + 1} 127.0.0.1 >nul",
            f'"%GAME_EXE_PATH%" {game_args_line}'.strip(),
            "endlocal",
            "exit /b %ERRORLEVEL%",
            "",
        ]
    )
    script_path.write_text(content, encoding="utf-8", newline="\r\n")
    return script_path


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


def build_launch_args(ns: argparse.Namespace, game_dir: Path) -> list[str]:
    args = [
        "-playerName",
        ns.username,
        "-console",
        "-Client.ServerIp",
        ns.server_ip,
        "-allowMultipleInstances",
        "-RenderDevice.IntelMinDriverVersion",
        "0.0",
    ]
    if ns.server_password.strip():
        args.extend(["-password", ns.server_password.strip()])
    args.extend(split_args(SPECIAL_LAUNCH_ARGS[ns.game]))

    if ns.use_mods and ns.game == "BFN":
        args.extend(["-datapath", str(game_dir / "ModData" / ns.mod_pack)])

    if ns.fov is not None and ns.game != "GW1":
        args.extend(["-Render.FovMultiplier", f"{(ns.fov / 70.0):g}"])

    args.extend(split_args(ns.additional_args))
    return args


def validate_inputs(ns: argparse.Namespace, launcher_dir: Path, game_dir: Path) -> None:
    if not ns.username.strip():
        raise ValueError("Username cannot be empty.")
    if len(ns.username) < 3:
        raise ValueError("Username must be at least 3 characters.")
    if len(ns.username) > 32:
        raise ValueError("Username cannot exceed 32 characters.")
    if not ns.server_ip.strip():
        raise ValueError("Server IP cannot be empty.")
    if ns.ea_delay_seconds < 0:
        raise ValueError("--ea-delay-seconds must be >= 0.")

    server_dll = launcher_dir / f"cypress_{ns.game}.dll"
    if not server_dll.exists():
        raise FileNotFoundError(f"Server DLL not found: {server_dll}")

    if ns.use_mods and not ns.mod_pack.strip():
        raise ValueError("--use-mods requires --mod-pack.")


def main() -> int:
    ns = parse_args()
    launcher_dir = ns.launcher_dir.expanduser().resolve()
    proton_script_path: Path | None = None
    is_proton_runner = False
    target_dll: Path | None = None

    try:
        runner = resolve_runner(ns.runner)
        is_proton_runner = runner in {"umu-run", "wine"}
        game_dir = Path(str(ns.game_dir)) if is_proton_runner else ns.game_dir.expanduser().resolve()
        ea_launcher = str(ns.ea_launcher) if is_proton_runner else str(ns.ea_launcher.expanduser().resolve())
        target_dll = game_dir / "dinput8.dll"

        validate_inputs(ns, launcher_dir, game_dir)

        if is_proton_runner:
            exe_name = PATCHED_EXECUTABLES.get(ns.game, EXECUTABLES[ns.game])
        else:
            exe_name = ensure_patched_exe(ns.game, game_dir, launcher_dir, runner)
        launch_args = build_launch_args(ns, game_dir)

        source_dll = launcher_dir / f"cypress_{ns.game}.dll"

        assert target_dll is not None
        if not target_dll.exists():
            shutil.copy2(source_dll, target_dll)

        env = os.environ.copy()
        if not is_proton_runner:
            env["EARtPLaunchCode"] = get_rtp_launch_code()
            env["ContentId"] = "1026482"
            env["GW_LAUNCH_ARGS"] = subprocess.list2cmdline(launch_args)
            if ns.use_mods:
                env["GAME_DATA_DIR"] = str(game_dir / "ModData" / ns.mod_pack)
            else:
                env.pop("GAME_DATA_DIR", None)
        if runner == "umu-run":
            env.setdefault("GAMEID", "cypresslauncher")

        if is_proton_runner:
            game_dir_raw = str(ns.game_dir)
            launch_args_for_env = launch_args.copy()
            game_dir_root = game_dir_raw.rstrip("/\\")
            game_exe_for_env = f"{game_dir_root}/{exe_name}"
            proton_env = {
                "EARtPLaunchCode": get_rtp_launch_code(),
                "ContentId": "1026482",
                "GW_LAUNCH_ARGS": subprocess.list2cmdline(launch_args_for_env),
                "GAME_DATA_DIR": f"{game_dir_root}/ModData/{ns.mod_pack}" if ns.use_mods else "",
            }
            proton_script_path = write_proton_launch_script(
                str(ns.ea_launcher),
                game_exe_for_env,
                launch_args,
                proton_env,
                ns.ea_delay_seconds,
            )
            game_cmd = build_proton_dual_launch_command(runner, proton_script_path)
        else:
            game_cmd = build_command(runner, game_dir / exe_name, launch_args)
        print("Launch command:", subprocess.list2cmdline(game_cmd))
        if ns.dry_run:
            return 0

        launch_cwd = str(launcher_dir) if is_proton_runner else str(game_dir)
        if runner == "native":
            ea_process = subprocess.Popen([ea_launcher], cwd=launch_cwd, env=env)
            print(f"EA launcher started (PID {ea_process.pid})")
            process = subprocess.Popen(game_cmd, cwd=launch_cwd, env=env)
            print(f"Game launched (PID {process.pid})")
            exit_code = process.wait()
            print(f"Game exited with code 0x{exit_code:X}")
        else:
            process = subprocess.Popen(game_cmd, cwd=launch_cwd, env=env)
            print(f"Game launched (PID {process.pid})")
            exit_code = process.wait()
            print(f"Game exited with code 0x{exit_code:X}")
    except Exception as exc:
        print(f"Launch failed: {exc}", file=sys.stderr)
        return 1
    finally:
        try:
            if target_dll is not None:
                target_dll.unlink(missing_ok=True)
            if proton_script_path is not None:
                proton_script_path.unlink(missing_ok=True)
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
