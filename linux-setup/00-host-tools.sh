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
admin=()
if (( EUID != 0 )); then need sudo; admin=(sudo); fi
if command -v pacman >/dev/null; then
    "${admin[@]}" pacman -S --needed --noconfirm python python-pip curl cabextract unzip file
elif command -v apt-get >/dev/null; then
    "${admin[@]}" apt-get update
    "${admin[@]}" apt-get install -y python3 python3-pip python3-venv curl cabextract unzip file
else
    fail 'This helper supports Arch and Debian/Ubuntu. Install packages manually on other distributions.'
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
    python3 -m venv "$KIT_DIR/tools/protontricks-venv"
    "$KIT_DIR/tools/protontricks-venv/bin/python" -m pip install 'protontricks==1.15.0'
    printf '%s\n' "Optional installation: $KIT_DIR/tools/protontricks-venv/bin/protontricks"
fi
printf '%s\n' 'Helper tools are ready. No Wine prefix has been modified.'
