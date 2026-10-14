#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
# Desktop launchers do not necessarily read the shell profile used by the manual setup.
export PATH="$HOME/.local/bin:$PATH"
finish() { local status=$?; if (( status != 0 )); then printf '\nSetup failed (%s). Press Enter to close.\n' "$status"; read -r _ || true; fi; }
trap finish EXIT
case "$(uname -m)" in aarch64|arm64) ;; *) printf 'Run this in DroidDeck’s ARM64 Linux desktop.\n' >&2; exit 1;; esac
if ! command -v python3 >/dev/null; then
    printf 'Python 3 is missing. Restore/install DroidDeck’s Linux Python tools, then retry.\n' >&2
    exit 1
fi
case "${1:-}" in
    --terminal) python3 assistant/terminal.py; exit $? ;;
    --web) python3 assistant/web.py; exit $? ;;
    '') ;;
    *) printf 'Usage: bash start-setup.sh [--terminal|--web]\n' >&2; exit 1 ;;
esac
if ! python3 -c 'import tkinter' >/dev/null 2>&1; then
    printf 'Tk is unavailable. Opening the graphical browser assistant; no sudo or Tk installation is needed.\n'
    python3 assistant/web.py
else
    python3 assistant/gui.py
fi
