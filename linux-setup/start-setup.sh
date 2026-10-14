#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
finish() { local status=$?; if (( status != 0 )); then printf '\nSetup failed (%s). Press Enter to close.\n' "$status"; read -r _ || true; fi; }
trap finish EXIT
case "$(uname -m)" in aarch64|arm64) ;; *) printf 'Run this in DroidDeck\x27s ARM64 Linux desktop.\n' >&2; exit 1;; esac
if ! command -v python3 >/dev/null || ! python3 -c 'import tkinter' >/dev/null 2>&1; then
    printf 'The graphical setup needs Python 3 and Tk. Install these Linux packages? [y/N] '
    read -r answer
    [[ "$answer" == y || "$answer" == Y ]] || exit 0
    admin=(); if (( EUID != 0 )); then admin=(sudo); fi
    if command -v apt-get >/dev/null; then
        "${admin[@]}" apt-get update
        "${admin[@]}" apt-get install -y python3 python3-tk
    elif command -v pacman >/dev/null; then
        "${admin[@]}" pacman -S --needed --noconfirm python tk
    else
        printf 'Install Python 3 and Tk using your distribution package manager.\n' >&2; exit 1
    fi
fi
python3 assistant/gui.py
