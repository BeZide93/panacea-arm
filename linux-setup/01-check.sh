#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
[[ $# == 0 || ( $# == 1 && $1 == --wine ) ]] || fail 'Usage: bash 01-check.sh [--wine]'
load_config
printf '\nLinux tools:\n'
for cmd in python3 curl cabextract unzip file; do
    if command -v "$cmd" >/dev/null; then printf 'OK %s\n' "$cmd"; else printf 'MISSING %s\n' "$cmd"; fi
done
printf '\nWinetricks components recorded in this prefix:\n'
if [[ -f "$WINEPREFIX/winetricks.log" ]]; then cat "$WINEPREFIX/winetricks.log"; else printf 'No winetricks.log found.\n'; fi
printf '\n.NET installation directories:\n'
for base in 'Program Files/dotnet' 'Program Files/dotnet/x64' 'Program Files/dotnet/x86' 'Program Files (x86)/dotnet'; do
    for runtime in Microsoft.NETCore.App Microsoft.WindowsDesktop.App; do
        path="$WINEPREFIX/drive_c/$base/shared/$runtime"
        if [[ -d "$path" ]]; then printf '%s:\n' "$path"; find "$path" -mindepth 1 -maxdepth 1 -type d -printf '  %f\n'; fi
    done
done
printf '\nDLL files (presence alone does not prove they work):\n'
for folder in system32 syswow64; do
    for dll in ucrtbase.dll xaudio2_9.dll mfc42.dll msvcp60.dll; do
        path="$WINEPREFIX/drive_c/windows/$folder/$dll"
        if [[ -e "$path" ]]; then
            if command -v file >/dev/null; then file -L -- "$path"; else printf 'PRESENT %s\n' "$path"; fi
        else printf 'NOT FOUND %s\n' "$path"; fi
    done
done
if [[ ${1:-} == --wine ]]; then
    printf '\nWine runtime check (may trigger Wine initialization):\n'
    check_wine
    for base in 'Program Files/dotnet' 'Program Files/dotnet/x64' 'Program Files/dotnet/x86' 'Program Files (x86)/dotnet'; do
        dotnet="$WINEPREFIX/drive_c/$base/dotnet.exe"
        if [[ -f "$dotnet" ]]; then
            "$WINE" "$dotnet" --list-runtimes || fail ".NET could not be started: $dotnet"
        fi
    done
    "$WINE" reg.exe query 'HKCU\Software\Wine\DllOverrides' || printf 'No global registry overrides could be read. Launch options apply separately.\n'
fi
