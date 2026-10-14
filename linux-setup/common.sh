#!/usr/bin/env bash
# Shared functions; loading this file does not run Wine or change a prefix.
set -euo pipefail
KIT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
# Reuse the user-local helpers installed by the manual DroidDeck setup.
export PATH="$HOME/.local/bin:$PATH"
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null || fail "Required program not found: $1"; }
load_config() {
    local cfg=${KH_SETUP_CONFIG:-"$KIT_DIR/config.env"}
    [[ -f "$cfg" ]] || fail "Copy config.example.env to config.env and check the paths."
    # This is a user-owned shell configuration, not downloaded code.
    source "$cfg"
    : "${KH_APPID:?}" "${KH_COMPATDATA:?}" "${KH_PROTON_ROOT:?}" "${KH_STEAM_ROOT:?}" "${KH_BACKUP_ROOT:?}"
    [[ "$KH_APPID" =~ ^[1-9][0-9]{0,9}$ ]] && (( KH_APPID <= 4294967295 )) || fail "Invalid Steam AppID: $KH_APPID"
    [[ "${KH_COMPATDATA##*/}" == "$KH_APPID" ]] || fail "Compatdata directory must match the selected AppID."
    [[ "$KH_COMPATDATA" == /* && "$KH_PROTON_ROOT" == /* && "$KH_BACKUP_ROOT" == /* ]] || fail 'Absolute paths are required.'
    [[ -f "$KH_COMPATDATA/pfx/system.reg" && -d "$KH_COMPATDATA/pfx/drive_c" ]] || fail 'Existing prefix not found. Check the path; no new prefix will be created.'
    [[ -d "$KH_STEAM_ROOT" ]] || fail 'Steam directory not found.'
    [[ -x "$KH_PROTON_ROOT/files/bin-arm64/wine" && -x "$KH_PROTON_ROOT/files/bin-arm64/wineserver" ]] || fail 'ARM64 Proton/Wine not found. Set the active DroidDeck build in config.env.'
    export WINEPREFIX="$KH_COMPATDATA/pfx"
    export WINE="$KH_PROTON_ROOT/files/bin-arm64/wine"
    export WINESERVER="$KH_PROTON_ROOT/files/bin-arm64/wineserver"
    export STEAM_COMPAT_DATA_PATH="$KH_COMPATDATA"
    export STEAM_COMPAT_CLIENT_INSTALL_PATH="$KH_STEAM_ROOT"
    export SteamAppId="$KH_APPID" SteamGameId="$KH_APPID"
    export PATH="$KH_PROTON_ROOT/files/bin-arm64:$HOME/.local/bin:$PATH"
    # Library layout follows Valve Proton 11 init_wine(). Preserve host entries.
    export LD_LIBRARY_PATH="$KH_PROTON_ROOT/files/lib/x86_64-linux-gnu:$KH_PROTON_ROOT/files/lib/aarch64-linux-gnu:$KH_PROTON_ROOT/files/lib/i386-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    export WINEDLLPATH="$KH_PROTON_ROOT/files/lib/vkd3d:$KH_PROTON_ROOT/files/lib/wine${WINEDLLPATH:+:$WINEDLLPATH}"
    unset WINEARCH
    printf 'AppID: %s\nPrefix: %s\nWine: %s\n' "$KH_APPID" "$WINEPREFIX" "$WINE"
}
backup_prefix() {
    need realpath
    local source_path dest_root
    source_path=$(realpath -- "$WINEPREFIX")
    dest_root=$(realpath -m -- "$KH_BACKUP_ROOT")
    [[ "$dest_root/" != "$source_path/"* ]] || fail 'The backup directory must be outside the prefix.'
    mkdir -p -- "$dest_root"
    BACKUP_DIR=$(mktemp -d "$dest_root/${KH_APPID}-$(date +%Y%m%d-%H%M%S)-XXXXXX")
    printf 'Prefix backup: %s/pfx\n' "$BACKUP_DIR"
    cp -a --reflink=auto -- "$WINEPREFIX" "$BACKUP_DIR/pfx"
    printf 'Prefix=%s\nProton=%s\nAppID=%s\n' "$WINEPREFIX" "$KH_PROTON_ROOT" "$KH_APPID" > "$BACKUP_DIR/context.txt"
    printf '%s\n' 'Backup complete.'
}
check_wine() {
    "$WINE" cmd.exe /c 'echo WINE_TEST_OK' || fail 'Wine check failed; installation stopped.'
}
winetricks_path() {
    WINETRICKS="$KIT_DIR/tools/winetricks"
    [[ -f "$WINETRICKS" ]] || fail 'Run 00-host-tools.sh --install first.'
    printf '%s  %s\n' '672a1ff4442e8691a3ffc0e6860137e201a1d1227e9b3044245f1731e9e9837e' "$WINETRICKS" | sha256sum -c - >/dev/null || fail 'Winetricks checksum mismatch.'
}
