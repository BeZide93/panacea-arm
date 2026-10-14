# Linux ARM64 dependency setup

[Deutsch](README-DE.md) · [Download the complete setup kit](../packages/Panacea-ARM-Linux-Setup.zip?raw=true)

Helper scripts for an existing OpenKH / Kingdom Hearts installation in **DroidDeck's Linux environment on Android**, using Proton Experimental ARM64. Run them in that environment's terminal. The Windows game, Panacea and OpenKH still use x86/x64 components.

This kit reconstructs the dependency setup used on October 12, 2026. It is not a complete Steam, DroidDeck or OpenKH installer. The scripts were newly written from the recorded steps; they are not a verbatim terminal transcript.

## Graphical setup for DroidDeck

1. Download and extract the [complete setup ZIP](../packages/Panacea-ARM-Linux-Setup.zip?raw=true) **inside DroidDeck's Linux desktop**.
2. Close Steam, Kingdom Hearts, OpenKH and other Windows applications. Double-click **`Panacea-Setup.desktop`** in the extracted folder. If the file manager asks, allow execution / mark the launcher as trusted. Keep the entire folder together.
3. Select your Steam account and enable **OpenKH** if you also want to configure its separate shortcut/prefix. Review the paths from the working manual setup below. No game launch or live process recognition is required; keep Steam and Windows applications closed throughout.
4. Use **Auswahl prüfen** in the browser, review the summary, tick the confirmation box and click **Jetzt einrichten** (native Tk: **Einrichten**). The assistant backs up each selected prefix, the replaced DLL and changed Steam files before installation. Reopen Steam after it finishes.

The German-language form can check/install missing runtimes, install the bundled main `version.dll`, run an explicitly selected original `add_registry.bat` in the selected prefix, and merge Steam launch options. Uncheck operations you do not need. For OpenKH alone, uncheck Kingdom Hearts and DLL installation. OpenKH must already exist as a Steam shortcut and have been started once. There is no fixed shortcut AppID.

Python 3 is supplied by DroidDeck's Linux tools. With Tk available, the native form opens. **Without Tk, the launcher automatically opens a graphical interface in the local browser** — no Tk installation, extra Python packages or terminal answers are required to open and use the form. It has the same fixed profile, account/shortcut selection, operation checkboxes, backup directory, review dialog and installation backend. Progress, errors and setup.log are shown on the page. Use **Assistent beenden** after completion; keep the starter window open while installing. If the browser does not open automatically, the starter prints the local URL.

Explicit browser mode: `bash start-setup.sh --web`. The text assistant remains available with `bash start-setup.sh --terminal`. The browser server binds only to `127.0.0.1` on a random port and protects its API with a per-session token and origin/host checks. Opening the page or reviewing the selection does not start installation; **Jetzt einrichten** requires a reviewed selection. Downloads for missing runtimes still require Internet access.

**Locally installed helpers:** The desktop launcher, assistant checks and installer commands explicitly include `~/.local/bin` in their search path, just like the working manual setup. An existing `~/.local/bin/cabextract` is reused without `sudo` or package installation, even when the desktop did not load your shell profile. `setup.log` records the selected `cabextract` path.

On DroidDeck ARM64, missing or non-working `cabextract`, `curl`, `unzip` and `file` are installed automatically under `~/.local`, including dependencies selected by pacman. Pacman only prints a dependency plan against freshly downloaded private Arch Linux ARM metadata; it does not install system packages or update the system package database. Packages use HTTPS and their repository SHA-256 checksums. Package scripts are not executed. Each helper must start successfully before it is published in `~/.local/bin`; all checks happen before Wine prefix changes. No `sudo`, Android root or fake-root session is required. The working DroidDeck base environment must provide Python 3, pacman and (for zstd packages) bsdtar; the assistant does not reinstall the Linux environment itself.

### Paths from the working manual setup

The assistant uses these locations on existing and new setups; it does not switch libraries based on another discovered prefix or `config_info`:

| Component | Default location |
|---|---|
| Steam | `~/.local/share/Steam` |
| Kingdom Hearts prefix | `~/.local/share/Steam/steamapps/compatdata/2552430/pfx` |
| OpenKH prefix | `~/.local/share/Steam/steamapps/compatdata/<shortcut-AppID>/pfx` |
| Game files | `~/Games/Windows/steamapps/common/KINGDOM HEARTS -HD 1.5+2.5 ReMIX-` |
| Proton | `~/.local/share/droiddeck-esync/dist/<build>` |
| Backups | `~/panacea-prefix-backups` |

The tested `valve-experimental-11.0-20261001-arm64-1790819359-76e24eb8146d-r1~015ab1a0` build is preferred while present. If it is absent, a single valid build in that same esync directory is accepted. Multiple alternatives require an explicit `KH_PROTON_ROOT` in `config.env`; the assistant never chooses the newest build or switches to stock Proton automatically.

An existing **`config.env` beside `start-setup.sh` takes precedence**. The assistant reads simple `KH_…=…` assignments, quotes, `$HOME` and previously defined variables; it never executes shell commands from that file. An explicitly configured missing path causes a stop instead of a fallback. To intentionally change a path, edit `config.env` and restart (GUI: reload the profile).

Missing prefixes at the intended locations stop the setup. Nothing is moved, and an unrelated prefix in the game library is not substituted. This remains an installer for dependencies in existing Steam prefixes, not a Steam/game downloader or automatic prefix creator. Newly installed Windows components go into the same intended prefixes. These are known manual defaults, not a claim that the currently selected Steam runtime has been observed.

**What gets changed:** the game receives `version=n,b;dinput8=n,b;LuaBackend=n,b`; other DLL overrides, wrappers and arguments are preserved. Only the selected OpenKH shortcut receives `PROTON_USE_WINED3D=1`. Steam must be fully closed. Complex shell expressions or concurrent config edits cause a stop instead of a guessed rewrite; use the manual launch-option instructions below in that case.

The DLL is bundled and SHA-256 checked; no moving `main` download happens during installation. The general KH2 Asset Size Cache remains a separate mod. DroidDeck, Steam, the game, OpenKH and its original Panacea/BASS dependencies must already be installed. This assistant is not an OpenKH downloader.

.NET checks run the Windows x86/x64 hosts, including `Program Files/dotnet/x64`, and accept working **8.x** runtimes instead of downgrading them. Missing runtimes use the same pinned Winetricks/.NET 8.0.12 setup documented below. If Winetricks records a runtime but its checks fail, setup stops without forcing a reinstall. `ucrtbase2019` is never installed. Legacy runtime checks use Winetricks installation records; final game/OpenKH testing is still necessary.

**Logs and recovery:** `~/.local/state/panacea-arm/setup.log` (or `$XDG_STATE_HOME/panacea-arm/setup.log`) is reset for each installation attempt. Backups are timestamped below the selected backup folder; `backup.json` maps originals to backups and `RESTORE.txt` explains recovery. No automatic rollback overwrites a prefix after failure. A full prefix restore also reverts later saves/settings, so retain the current prefix first. Existing Panacea logs are unaffected.

## Manual setup

Extract the ZIP and open a terminal in its `Panacea-ARM-Linux-Setup` folder. If using a repository checkout, enter `linux-setup` instead.

```bash
cp config.example.env config.env
nano config.env
bash 01-check.sh
```

Use any text editor in place of `nano`. Check these settings before installing anything:

| Setting | Meaning |
|---|---|
| `KH_PROTON_ROOT` | Your active DroidDeck Proton build, containing `files/bin-arm64/wine` and `wineserver`. |
| `KH_STEAM_ROOT` | The Steam client installation directory inside the Linux environment. |
| `KH_APPID` | `2552430` for Kingdom Hearts HD 1.5+2.5 ReMIX. |
| `KH_COMPATDATA` | The game's existing `steamapps/compatdata/2552430` directory, without `/pfx`. |
| `KH_BACKUP_ROOT` | Location for complete prefix backups. Keep it outside the prefix. |
| `KH_REGISTRY_BAT` | Optional absolute path to the original `add_registry.bat` supplied with your OpenKH setup. |

The example Proton path identifies the build used in the original setup; it may change after an update. Select the build actually used by the game. No automatic newest-build selection is performed.

The scripts require an existing prefix with `system.reg` and `drive_c`. They will not create a new one. The original user's separate OpenKH shortcut had AppID **4018651221**; this is a user-specific shortcut ID, not a universal OpenKH AppID. If you need that prefix instead, change **both** the AppID and compatdata path. The scripts accept valid unsigned Steam AppIDs and require the compatdata folder name to match. Installing a runtime in one prefix does not install it in the other.

**If your installation already works, start with the checks. Reinstalling its dependencies is unnecessary.**

## Scripts

| File | Purpose |
|---|---|
| `00-host-tools.sh` | Installs Linux helper packages and downloads a pinned, SHA-256-verified Winetricks script. Optionally installs Protontricks in its own Python environment. |
| `01-check.sh` | Checks paths, helper tools, runtime directories and DLL files. Add `--wine` to run Wine and the installed .NET hosts. |
| `02-install-runtimes.sh` | Installs only explicitly selected components, after backing up the entire prefix. |
| `03-add-registry.sh` | Runs your original OpenKH registry batch from its own directory, after a prefix backup. |
| `04-launch-options.sh` | Prints Steam launch options. Does not change Steam configuration. |
| `common.sh` | Shared Wine selection, configuration and backup functions. |

All scripts can be run using `bash`; executable permissions are not required. `config.env` is a local shell configuration: edit your own copy. Keep it out of commits and public downloads.

## 1. Install Linux helper tools

```bash
bash 00-host-tools.sh --install
```

DroidDeck ARM64 uses the local installation described above and includes `~/.local/bin` in the PATH of the assistant and every installer process. Other supported Linux hosts use `pacman -S --needed` or `apt-get` for missing tools. It does not install another Wine. Winetricks is stored in `tools`, pinned to commit `f3890f670867b5ffbc3938726db45c0f7d16c8ba` and checked before installation or use.

Protontricks is optional. In the recorded setup it found the Steam entries but could not use the custom ARM64 Proton build, so the scripts select that build's Wine directly.

```bash
bash 00-host-tools.sh --install --with-protontricks
tools/protontricks-venv/bin/protontricks -l
```

On DroidDeck this optional command creates an isolated Python environment and bootstraps pip 26.2.1 from its SHA-256-checked PyPI wheel, then installs Protontricks 1.15.0 and its Python dependencies. It needs no system pip, sudo or changes to the system Python. The normal graphical setup does not install Protontricks because it uses Proton Wine directly.

## 2. Install missing Windows runtimes

Close the game, launcher and OpenKH first. Steam itself may remain open. Ensure there is enough space for a complete prefix backup under `KH_BACKUP_ROOT`.

For a missing audio dependency:

```bash
bash 02-install-runtimes.sh --install xaudio29
```

To reproduce the recorded component set when needed:

```bash
bash 02-install-runtimes.sh --install dotnet8 dotnetdesktop8 vcrun6 xaudio29
bash 01-check.sh --wine
```

The four allowed verbs are:

| Component | Purpose / pinned setup |
|---|---|
| `dotnet8` | .NET runtime 8.0.12. |
| `dotnetdesktop8` | Windows Desktop Runtime 8.0.12. |
| `vcrun6` | Legacy Visual C++ 6 runtime; this is not Visual C++ 2022. |
| `xaudio29` | Microsoft XAudio 2.9 redistributable. |

Winetricks downloads the Microsoft packages using its own download definitions and checksums. The pinned .NET verbs reproduce **8.0.12**, not the newest .NET 8 security update. The ARM64 host does not mean that Windows ARM64 installers should replace these x86/x64 dependencies.

The scripts do not force reinstallation. An error stops subsequent components. `ucrtbase2019` and other unlisted verbs are rejected. No automatic rollback overwrites the prefix after an error; the backup path is printed for recovery.

## 3. Apply the OpenKH registry setup

Only if this setup is still missing: set `KH_REGISTRY_BAT` to the existing original `add_registry.bat`, then run:

```bash
bash 03-add-registry.sh --apply
```

The batch runs from its own directory. The kit does not invent OpenKH registry entries or supply a substitute batch. Keep the BASS dependencies, LuaBackend and other files from your existing OpenKH/Panacea installation.

## 4. Steam launch options

The recorded working overrides were:

```text
WINEDLLOVERRIDES="version=n,b;dinput8=n,b;LuaBackend=n,b" %command%
```

To collect a Proton log:

```text
PROTON_LOG=1 WINEDLLOVERRIDES="version=n,b;dinput8=n,b;LuaBackend=n,b" %command%
```

Keep any additional options your environment requires, and use `%command%` only once. These are Steam launch options, not shell commands. Remove the additional `PROTON_LOG=1` for FPS comparisons.

The repaired `version.dll` belongs in the game folder. Do not rename Panacea to `dinput8.dll`; keep a real `dinput8.dll` supplied by another mod if needed. The general KH2 Asset Size Cache remains in `mod/kh2/dll/KH2AssetSizeCache.dll`. `04-launch-options.sh` also prints a `version=b` diagnostic option that disables Panacea, but does not necessarily disable other mod loaders.

## OpenKH opens briefly and closes

**Confirmed workaround in the tested DroidDeck / Proton Experimental ARM64 setup:** use WineD3D for the OpenKH Mod Manager. In Steam, open **OpenKH → Properties → Launch Options** and use:

```text
PROTON_USE_WINED3D=1 %command%
```

To keep a diagnostic log as well:

```text
PROTON_LOG=1 PROTON_USE_WINED3D=1 %command%
```

Apply this to **OpenKH's own Steam shortcut only**. Keep Kingdom Hearts' working launch options unchanged. Preserve any other required options and include `%command%` only once. To undo the workaround, remove `PROTON_USE_WINED3D=1`.

The failing run had already loaded x64 .NET Core and Windows Desktop **8.0.30** from `C:\Program Files\dotnet\x64\…`. WPF then used Direct3D 9 through DXVK; the log ended with a broken X connection and access violations in `vkCreateGraphicsPipelines` and `vkQueuePresentKHR`. WineD3D uses OpenGL instead of the DXVK/Vulkan path for Direct3D 9, and OpenKH started successfully with this option. The exact underlying graphics component responsible has not been isolated; this is not evidence that every ARM64 installation needs the workaround.

The check script and assistant now also inspect `Program Files/dotnet/x64` and `dotnet/x86`. The assistant additionally runs the detected Windows hosts; directory presence alone is not a successful runtime test.

Reference: [Valve's Proton runtime options](https://github.com/ValveSoftware/Proton#runtime-config-options).

## Recorded UCRT failure and recovery

Installing `ucrtbase2019` caused `c000007b` / `c0000135` errors in the original setup. The previous `ucrtbase.dll` files in **both** `drive_c/windows/system32` and `drive_c/windows/syswow64` were restored from that prefix's backup. Wine then returned `WINE_TEST_OK` with exit code 0.

This recovery is not a normal installation step and should not be repeated on a working prefix. A complete prefix restore would also revert registry settings and potentially newer saves. The kit therefore leaves recovery as an explicit action rather than automatically copying a backup over the active prefix.

## Validation and limits

The assistant has automated tests for Steam library/shortcut discovery, high-bit shortcut IDs, VDF edits, option merging, separate prefix backups, failures and runtime detection. CI opens the Tk form under Xvfb and validates the desktop launcher. These are host-side tests with mocked Wine/installer calls, not an Android installation test. Profile tests cover fixed locations, preference for the known build, explicit configuration overrides, rejection of shell code, missing prefixes and ambiguous replacement builds.


The scripts have been syntax-checked and exercised with mocked Wine/installer calls, including paths with spaces, prefix backups, rejected components and failure handling. They have not been executed here on an Android ARM64 device. File presence alone does not prove a working runtime; use `01-check.sh --wine`, inspect the runtime list and then test the game.

Wine and wineserver are explicitly selected from `files/bin-arm64`. Library search paths follow Valve Proton 11's `init_wine()` layout; their exact historical terminal values were not recoverable. Other environment variables from the DroidDeck terminal are retained.

## References

- [Panacea compatibility DLL](https://github.com/BeZide93/panacea-arm)
- [KH2 Asset Size Cache](https://github.com/BeZide93/kh2-asset-size-cache)
- [Pinned Winetricks source and package definitions](https://github.com/Winetricks/winetricks/blob/f3890f670867b5ffbc3938726db45c0f7d16c8ba/src/winetricks)
- [Valve Proton 11](https://github.com/ValveSoftware/Proton/blob/proton_11.0/proton)
- [DroidDeck](https://github.com/Droid-Deck/DroidDeck)
- [Microsoft .NET installation on Windows](https://learn.microsoft.com/dotnet/core/install/windows)

### Local helper files and removal

Launchers are in `~/.local/bin`; packages, licenses, package checksums and any replaced launcher backups are kept under `~/.local/share/panacea-arm/host-tools/install-*`. Existing working helpers are left untouched. The setup adds the search path for its own processes; it does not rewrite shell startup files. To remove a helper installed by setup, close setup and remove its launcher only if it contains `# Managed by Panacea ARM setup.`; restore its matching `previous/<name>` backup if present. Remove the matching installation directory only when no remaining launcher refers to it. Wine-prefix rollback is separate.
