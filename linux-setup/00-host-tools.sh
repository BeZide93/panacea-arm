#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
if [[ ${1:-} != --install ]]; then
    printf '%s\n' 'Usage: bash 00-host-tools.sh --install [--with-protontricks]' \
        'Installs Linux helper tools and a verified Winetricks version.' \
        'Protontricks is optional; the ARM64 installation uses Wine directly.'
    exit 0
fi
[[ $# == 1 || ( $# == 2 && $2 == --with-protontricks ) ]] || fail 'Unknown option.'
local_helpers=false
case "$(uname -m)" in
    aarch64|arm64)
        local_helpers=true
        need python3
        python3 "$KIT_DIR/assistant/host_tools.py"
        ;;
esac
# The DroidDeck desktop uses the Android app UID even when USER is root.
# Downloading Winetricks needs no package manager if the tools already exist.
missing=()
for tool in python3 curl cabextract unzip file; do
    command -v "$tool" >/dev/null || missing+=("$tool")
done
if [[ ${2:-} == --with-protontricks && $local_helpers == false ]]; then
    if ! command -v python3 >/dev/null || ! python3 -m pip --version >/dev/null 2>&1; then missing+=(pip); fi
    if ! command -v python3 >/dev/null || ! python3 -c 'import venv, ensurepip' >/dev/null 2>&1; then missing+=(venv); fi
fi
if (( ${#missing[@]} )); then
    admin=()
    if (( EUID != 0 )); then
        command -v sudo >/dev/null || fail "Missing Linux tools: ${missing[*]}. This session has no sudo. Install them through your Linux environment's package installation facility, then retry. No Wine prefix has been modified."
        admin=(sudo)
    fi
    packages=()
    if command -v pacman >/dev/null; then
        for tool in "${missing[@]}"; do
            case "$tool" in python3|venv) packages+=(python);; pip) packages+=(python-pip);; *) packages+=("$tool");; esac
        done
        "${admin[@]}" pacman -S --needed --noconfirm "${packages[@]}"
    elif command -v apt-get >/dev/null; then
        for tool in "${missing[@]}"; do
            case "$tool" in pip) packages+=(python3-pip);; venv) packages+=(python3-venv);; *) packages+=("$tool");; esac
        done
        "${admin[@]}" apt-get update
        "${admin[@]}" apt-get install -y "${packages[@]}"
    else
        fail 'This helper supports Arch and Debian/Ubuntu. Install packages manually on other distributions.'
    fi
else
    printf '%s\n' 'Linux helper tools already present; package installation skipped.'
fi
mkdir -p -- "$KIT_DIR/tools"
tmp=$(mktemp "$KIT_DIR/tools/winetricks.XXXXXX")
trap 'rm -f -- "$tmp"' EXIT
curl --fail --location --retry 3 --proto '=https' --proto-redir '=https' \
    'https://raw.githubusercontent.com/Winetricks/winetricks/f3890f670867b5ffbc3938726db45c0f7d16c8ba/src/winetricks' -o "$tmp"
printf '%s  %s\n' '672a1ff4442e8691a3ffc0e6860137e201a1d1227e9b3044245f1731e9e9837e' "$tmp" | sha256sum -c -
chmod 755 "$tmp"
mv -- "$tmp" "$KIT_DIR/tools/winetricks"
if [[ ${2:-} == --with-protontricks ]]; then
    if [[ $local_helpers == true ]]; then
        python3 "$KIT_DIR/assistant/host_tools.py" --protontricks "$KIT_DIR/tools/protontricks-venv"
    else
        python3 -m venv "$KIT_DIR/tools/protontricks-venv"
        "$KIT_DIR/tools/protontricks-venv/bin/python" -m pip install 'protontricks==1.15.0'
    fi
    printf '%s\n' "Optional installation: $KIT_DIR/tools/protontricks-venv/bin/protontricks"
fi
printf '%s\n' 'Helper tools are ready. No Wine prefix has been modified.'
