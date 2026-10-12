#!/usr/bin/env bash
set -euo pipefail
cat <<'OPTIONS'
Kingdom Hearts: normal launch with the recorded overrides:
WINEDLLOVERRIDES="version=n,b;dinput8=n,b;LuaBackend=n,b" %command%

Enable Proton logging:
PROTON_LOG=1 WINEDLLOVERRIDES="version=n,b;dinput8=n,b;LuaBackend=n,b" %command%

Disable Panacea for comparison:
WINEDLLOVERRIDES="version=b;dinput8=n,b;LuaBackend=n,b" %command%

OpenKH Mod Manager ONLY: workaround if its window briefly opens and closes:
PROTON_USE_WINED3D=1 %command%

OpenKH workaround with a diagnostic log:
PROTON_LOG=1 PROTON_USE_WINED3D=1 %command%

WineD3D resolved this startup problem in the tested DroidDeck ARM64 setup.
Apply it to the OpenKH Steam shortcut, not to Kingdom Hearts.
To undo it, remove PROTON_USE_WINED3D=1.

Enter the selected line in Steam -> Properties -> Launch Options.
Keep other options your setup requires; use %command% only once.
This is Steam syntax, not a game launch command to run in the Linux terminal.
version=b disables Panacea, but not necessarily other mod loaders.
Do not rename Panacea to dinput8.dll. Keep a real dinput8.dll supplied by another mod.
OPTIONS
