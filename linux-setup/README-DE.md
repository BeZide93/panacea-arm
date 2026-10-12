# OpenKH / Panacea unter Linux ARM64: bisherige Einrichtung

[English](README.md) · [Setup-ZIP herunterladen](https://github.com/BeZide93/panacea-arm/raw/refs/heads/main/packages/Panacea-ARM-Linux-Setup.zip)

Stand: 12. Oktober 2026. Für deine Arch-Linux-ARM-/DroidDeck-Umgebung unter Android mit Steam und Proton Experimental ARM64. Im Terminal dieser Linux-Umgebung ausführen, nicht in einer beliebigen Android-/Termux-Shell.

## Was wir damals gemacht haben

| Schritt | Ergebnis |
|---|---|
| Linux-Hilfsprogramme eingerichtet | Protontricks 1.15.0, Winetricks 20260125-next, pip 26.2.1 und cabextract 1.11 wurden im damaligen Verlauf als installiert festgehalten. |
| Steam-Prefixe gefunden | Kingdom Hearts: `2552430`; der separat gestartete OpenKH-Mod-Manager: `4018651221`. |
| Protontricks ausprobiert | Erkannte beide Einträge, konnte den angepassten ARM64-Proton-Build aber nicht korrekt verwenden. |
| Auf das Wine des aktiven Proton-Builds gewechselt | `files/bin-arm64/wine` und `files/bin-arm64/wineserver`, mit dem ausdrücklich ausgewählten Spiel-Prefix. Kein zusätzliches System-Wine. |
| Windows-Komponenten eingerichtet | `dotnet8`, `dotnetdesktop8`, `vcrun6`, `xaudio29`. Im damaligen Check waren .NET Core/Desktop 8.0.12 vorhanden. |
| `ucrtbase2019` versucht | Danach traten `c000007b`/`c0000135` auf. Die beiden `ucrtbase.dll` aus `system32` und `syswow64` wurden aus der Prefix-Sicherung zurückkopiert. |
| Wine danach geprüft | `WINE_TEST_OK`, Exit-Code 0. |
| Originale `add_registry.bat` ausgeführt | Registry-Einrichtung aus dem OpenKH-Paket durchgeführt. |
| DLL-Overrides gesetzt | `version`, `dinput8`, `LuaBackend`: jeweils `native,builtin`. |
| Panacea-Startfehler untersucht | Fehlender `VerQueryValueA`-Export; anschließend zusätzliche Hook-Probleme. Unsere angepasste `version.dll` ergänzt die Exporte und verwendet stabile Trampoline. |

Diese Zusammenfassung rekonstruiert den belegten Ablauf. Nicht alle ursprünglichen Terminalzeilen und Downloadbefehle sind vollständig erhalten. Die beigefügten Skripte sind **neu daraus erstellte Hilfsskripte**, keine unveränderte Kopie des damaligen Terminalverlaufs.

`vcrun6` ist die alte Visual-C++-6-Laufzeit, nicht Visual C++ 2022. Eine zusätzliche Installation von `vcrun2022`, `d3dcompiler_47`, kompletter DirectX-Pakete oder ein Wechsel des Proton-Builds ist durch die rekonstruierten Schritte nicht belegt und wird hier nicht automatisch vorgenommen.

## Pfade aus deinem Aufbau

Im Proton-Log steht dieser Build:

```text
/root/.local/share/droiddeck-esync/dist/valve-experimental-11.0-20261001-arm64-1790819359-76e24eb8146d-r1~015ab1a0
```

Spielordner aus demselben Log:

```text
/root/Games/Windows/steamapps/common/KINGDOM HEARTS -HD 1.5+2.5 ReMIX-
```

Der rekonstruierte Prefix-Pfad ist `$HOME/.local/share/Steam/steamapps/compatdata/2552430/pfx`. Die Konfiguration verwendet `$HOME`, also in deinem damaligen Linux-Container `/root`. Nach einem DroidDeck-/Proton-Update kann der Buildordner anders heißen. Es wird bewusst nicht automatisch der vermeintlich neueste Ordner gewählt.

## Verwendung der Skripte

Das ZIP entpacken und im Unterordner `Panacea-ARM-Linux-Setup` ein Terminal öffnen. Bei einem Repository-Checkout stattdessen nach `linux-setup` wechseln. Alle Skripte lassen sich mit `bash` aufrufen, ein `chmod` ist nicht erforderlich.

```bash
cp config.example.env config.env
nano config.env
bash 01-check.sh
```

Anstelle von `nano` kann ein beliebiger Texteditor verwendet werden. Skriptmeldungen und Konfigurationskommentare sind auf Englisch; diese Anleitung bleibt deutsch.

In `config.env` vor allem `KH_PROTON_ROOT`, `KH_STEAM_ROOT` und `KH_COMPATDATA` kontrollieren. Das Skript akzeptiert nur einen bereits bestehenden Prefix mit `system.reg` und `drive_c`; es legt keinen neuen an. Den separaten OpenKH-Prefix nur dann auswählen, wenn du tatsächlich den Mod Manager dort reparieren willst: dafür **AppID und Compatdata-Pfad gemeinsam** auf `4018651221` ändern. Die OpenKH-ID ist benutzerspezifisch und keine allgemeine AppID für OpenKH. Die Skripte akzeptieren die beiden IDs aus diesem Setup. Installationen in einem Prefix gelten nicht automatisch im anderen.

**Auf deinem bereits funktionierenden System reicht zunächst die Prüfung. Eine Neuinstallation ist nicht erforderlich.**

| Datei | Zweck |
|---|---|
| `00-host-tools.sh` | Installiert fehlende Linux-Hilfsprogramme und lädt Winetricks mit festgelegtem Commit und SHA-256-Prüfung. Optional Protontricks in einer eigenen Python-Umgebung. |
| `01-check.sh` | Prüft Pfade, Werkzeuge, Runtime-Verzeichnisse und DLL-Dateien. Standardmäßig ohne Wine-Start; `--wine` führt zusätzlich Wine und die installierten .NET-Hosts aus. |
| `02-install-runtimes.sh` | Installiert nur ausdrücklich angegebene Komponenten aus der damaligen Liste. Sichert vorher den vollständigen Prefix. |
| `03-add-registry.sh` | Führt die von dir angegebene originale `add_registry.bat` aus, ebenfalls nach einer Prefix-Sicherung. |
| `04-launch-options.sh` | Gibt die normalen Startoptionen, die Diagnosevariante und den Gegencheck ohne Panacea aus. Ändert Steam nicht automatisch. |
| `common.sh` | Gemeinsame Prefix-/Wine-Auswahl und Backup-Funktionen. |

### 1. Linux-Hilfsprogramme

```bash
bash 00-host-tools.sh --install
```

Unter Arch verwendet das Skript `pacman -S --needed`, unter Debian/Ubuntu `apt-get`. Es installiert kein anderes Wine. Winetricks wird lokal im Unterordner `tools` gespeichert. Der gepinnte Commit ist `f3890f670867b5ffbc3938726db45c0f7d16c8ba`; dessen Datei wird vor Verwendung per SHA-256 geprüft.

Nur wenn du Protontricks zusätzlich wieder haben möchtest:

```bash
bash 00-host-tools.sh --install --with-protontricks
tools/protontricks-venv/bin/protontricks -l
```

Das optionale Protontricks wird nicht für die eigentliche ARM64-Installation verwendet. Die früheren pip-/cabextract-Versionen sind historische Angaben; das Skript verwendet hierfür die Pakete deiner Distribution.

### 2. Windows-Runtimes im richtigen Prefix

Vorher Spiel, Launcher und OpenKH vollständig beenden. Steam selbst darf geöffnet bleiben. Jede Installation erstellt eine vollständige Sicherung unter `KH_BACKUP_ROOT`; genügend freien Speicher einplanen.

Beispiel für eine fehlende Audio-Komponente:

```bash
bash 02-install-runtimes.sh --install xaudio29
```

Den gesamten damaligen Komponentenstand bei Bedarf reproduzieren:

```bash
bash 02-install-runtimes.sh --install dotnet8 dotnetdesktop8 vcrun6 xaudio29
bash 01-check.sh --wine
```

Winetricks lädt die zugehörigen Microsoft-Pakete anhand seiner Downloaddefinitionen und Prüfsummen. Die gepinnten `dotnet8`-/`dotnetdesktop8`-Verben installieren **8.0.12**: Das bildet den damaligen Stand ab und ist keine Zusage, die aktuellste .NET-8-Sicherheitsversion zu installieren. Für das x64-Spiel/OpenKH werden Windows-x86/x64-Komponenten verwendet; der ARM64-Host ist kein Grund, Windows-ARM64-Installer einzusetzen.

`ucrtbase2019` ist nicht erlaubt. Auch beliebige andere Winetricks-Verben werden vom Skript abgelehnt. Bereits vorhandene Komponenten werden ohne `--force` behandelt. Bei einem Fehler wird die weitere Installation abgebrochen; es gibt keinen automatischen Rollback, der spätere Änderungen überdecken könnte.

### 3. OpenKH-Registry

Nur falls diese Einrichtung noch fehlt: `KH_REGISTRY_BAT` in `config.env` auf die vorhandene originale `add_registry.bat` setzen, dann:

```bash
bash 03-add-registry.sh --apply
```

Das Skript startet die Batchdatei aus ihrem eigenen Verzeichnis. Es erzeugt keine unbekannten OpenKH-Registry-Einträge selbst. Die benötigten BASS-/LuaBackend-Dateien kommen weiterhin aus deinem bestehenden OpenKH-/Panacea-Paket; dieses Skriptpaket ersetzt dessen Installation nicht.

### 4. Steam-Startoptionen

Normal:

```text
WINEDLLOVERRIDES="version=n,b;dinput8=n,b;LuaBackend=n,b" %command%
```

Mit Proton-Log:

```text
PROTON_LOG=1 WINEDLLOVERRIDES="version=n,b;dinput8=n,b;LuaBackend=n,b" %command%
```

Weitere bei dir erforderliche Optionen beibehalten. `%command%` ist ein Steam-Platzhalter, kein Terminalbefehl. Für FPS-Messungen das zusätzliche `PROTON_LOG=1` wieder entfernen. Panacea nicht in `dinput8.dll` umbenennen. Unsere reparierte DLL bleibt `version.dll` im Spielordner; der Riku-Cache bleibt separat in `mod/kh2/dll/KH2RikuSizeFix.dll`.

## OpenKH öffnet sich kurz und schließt wieder

**Bestätigter Workaround in deinem DroidDeck-/Proton-Experimental-ARM64-Aufbau:** WineD3D für den OpenKH Mod Manager verwenden. In Steam unter **OpenKH → Eigenschaften → Startoptionen** eintragen:

```text
PROTON_USE_WINED3D=1 %command%
```

Mit zusätzlichem Diagnose-Log:

```text
PROTON_LOG=1 PROTON_USE_WINED3D=1 %command%
```

Das gilt **nur für den eigenen OpenKH-Steam-Eintrag**. Die funktionierenden Startoptionen von Kingdom Hearts unverändert lassen. Weitere benötigte Optionen beibehalten und `%command%` nur einmal verwenden. Zum Zurücknehmen `PROTON_USE_WINED3D=1` wieder entfernen.

Im fehlgeschlagenen Lauf wurden x64 .NET Core und Windows Desktop **8.0.30** bereits aus `C:\Program Files\dotnet\x64\…` geladen. Anschließend nutzte WPF Direct3D 9 über DXVK; am Ende des Logs standen eine abgebrochene X-Verbindung und Speicherzugriffsfehler in `vkCreateGraphicsPipelines` und `vkQueuePresentKHR`. WineD3D verwendet für Direct3D 9 OpenGL statt des DXVK-/Vulkan-Pfads. Damit startete OpenKH bei dir erfolgreich. Welche Grafikkomponente den ursprünglichen Fehler auslöst, ist noch nicht isoliert; die Option ist kein pauschales Erfordernis für alle ARM64-Systeme.

Nicht allein anhand der Verzeichnisliste des ursprünglichen Prüfskripts .NET nachinstallieren: Es prüft derzeit `Program Files/dotnet` und `Program Files (x86)/dotnet`, erfasst aber nicht die zusätzliche Struktur `Program Files/dotnet/x64` aus diesem Lauf.

Quelle: [Valve: Proton-Laufzeitoptionen](https://github.com/ValveSoftware/Proton#runtime-config-options).

## Der damalige UCRT-Rollback

Zurückgesetzt wurden genau `drive_c/windows/system32/ucrtbase.dll` und `drive_c/windows/syswow64/ucrtbase.dll`, jeweils aus der zugehörigen alten Prefix-Sicherung. Das ist **kein normaler Installationsschritt** und wird auf dem jetzt funktionierenden System nicht wiederholt. Eine Vollwiederherstellung würde zusätzlich Registry, Einstellungen und mögliche spätere Spielstände zurücksetzen; vorhandene Backups deshalb nicht blind über den aktuellen Prefix kopieren.

## Prüfung und Grenzen

Die Skripte wurden hier syntaktisch und mit nachgebildeten Wine-/Installationsaufrufen geprüft, einschließlich Pfaden mit Leerzeichen, Prefix-Sicherung, Ablehnung unerlaubter Komponenten und Abbruch bei Wine-Fehlern. Dein Android-/ARM64-System wurde hier nicht ausgeführt. Ein positiver Dateicheck allein belegt noch keine funktionierende Runtime; `--wine`, .NET-Runtime-Ausgabe und der tatsächliche Spielstart sind die nächsten praktischen Prüfungen.

Die Library-Pfade in `common.sh` folgen dem aktuellen Proton-11-Code; ihre exakte damalige Shell-Belegung war nicht rekonstruierbar. Andere Umgebungsvariablen deines DroidDeck-Terminals bleiben erhalten.

## Quellen und Projekte

- [Unser Panacea-Paket](https://github.com/BeZide93/panacea-arm)
- [Riku-Performance-Fix](https://github.com/BeZide93/kh2-riku-perf-fix)
- [Winetricks: geprüfter Quellstand und Downloaddefinitionen](https://github.com/Winetricks/winetricks/blob/f3890f670867b5ffbc3938726db45c0f7d16c8ba/src/winetricks)
- [Valve Proton 11: ARM64-Wine-Auswahl und init_wine](https://github.com/ValveSoftware/Proton/blob/proton_11.0/proton)
- [DroidDeck](https://github.com/Droid-Deck/DroidDeck)
- [Microsoft: .NET unter Windows](https://learn.microsoft.com/dotnet/core/install/windows)
