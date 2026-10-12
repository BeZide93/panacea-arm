#!/usr/bin/env bash
set -euo pipefail
cat <<'OPTIONS'
Normal launch with the recorded overrides:
WINEDLLOVERRIDES="version=n,b;dinput8=n,b;LuaBackend=n,b" %command%

Enable Proton logging:
PROTON_LOG=1 WINEDLLOVERRIDES="version=n,b;dinput8=n,b;LuaBackend=n,b" %command%

Disable Panacea for comparison:
WINEDLLOVERRIDES="version=b;dinput8=n,b;LuaBackend=n,b" %command%

Enter the selected line in Steam -> Properties -> Launch Options.
Keep other options your setup requires; use %command% only once.
This is Steam syntax, not a game launch command to run in the Linux terminal.
version=b disables Panacea, but not necessarily other mod loaders.
Do not rename Panacea to dinput8.dll. Keep a real dinput8.dll supplied by another mod.
OPTIONS
