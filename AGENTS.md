# Repository Guidelines

## Project Structure & Module Organization
This repository contains two executable Python entry points at the root:
- `cypress_launch.py`: client/game launcher.
- `cypress_launch_server.py`: dedicated server launcher.

Both scripts share similar patterns: argument parsing, runner selection (`native`, `umu-run`, `wine`), optional patching for newer executables, environment setup, and process launch. Keep new modules small and place them at repo root unless a clear package structure is introduced.

Runtime assets (not tracked here but required at launch) are expected beside scripts, for example `cypress_GW1.dll`, `courgette.exe`, and `*.patch` files.

## Build, Test, and Development Commands
No build step is required.
- `python3 cypress_launch.py --help`: view client launcher options.
- `python3 cypress_launch_server.py --help`: view server launcher options.
- `python3 cypress_launch.py --game GW2 --game-dir /path/to/game --server-ip 127.0.0.1 --username tester --dry-run`: validate arguments and print the generated command without launching.
- `python3 cypress_launch_server.py --game BFN --game-dir /path/to/game --device-ip 127.0.0.1 --level some_dsub --inclusion all --dry-run`: dry-run server launch flow.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation.
- Keep type hints (`Path`, `list[str]`, etc.) and `from __future__ import annotations` for consistency.
- Use `snake_case` for functions/variables and `UPPER_SNAKE_CASE` for constants (for example `EXECUTABLES`).
- Prefer small, pure helper functions for argument building and validation.

## Testing Guidelines
There is no automated test suite yet. For changes, require:
- `--help` smoke checks for both scripts.
- At least one `--dry-run` scenario per modified code path.
- Validation/error-path checks (missing args/files, bad combinations like `--use-mods` without `--mod-pack`).

If tests are added, use `tests/` with `pytest` and name files `test_*.py`.

## Commit & Pull Request Guidelines
`git log` currently shows no commits, so no established convention exists yet. Start with:
- Commit messages: imperative, concise subject (for example `feat: add playlist validation`).
- Keep commits focused (one behavior change per commit).
- PRs should include: purpose, key flags changed, dry-run commands executed, and sample output for behavior changes.

## Security & Configuration Tips
Do not commit real server passwords, personal usernames, or machine-specific paths. Use `--dry-run` while iterating on launch arguments to avoid accidental live launches.
