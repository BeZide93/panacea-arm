"""Tk-free assistant; the same plan, validation, backups and installer as the GUI."""
import os
from pathlib import Path
import platform

from core import (APPID, Plan, Runner, SetupError, Target, accounts, execute,
                  game_dirs, libraries, plan_summary, prefixes, proton_candidates,
                  require_stopped, setup_lock, shortcuts, steam_roots)

from routing import configuration, observe


def ask(label, default=''):
    value = input(label + (f' [{default}]' if default else '') + ': ').strip()
    return value or str(default)


def yes(label, default=False):
    while True:
        value = ask(label + (' [J/n]' if default else ' [j/N]')).lower()
        if not value:
            return default
        if value in ('j', 'ja', 'y', 'yes'):
            return True
        if value in ('n', 'nein', 'no'):
            return False
        print('Bitte j oder n eingeben.')


def choose(label, choices, default=None, manual=False):
    """Only a unique choice (or recorded Proton hint) receives a default."""
    choices = list(choices)
    if not choices and not manual:
        raise SetupError('Keine Auswahl gefunden: '+label)
    print('\n'+label)
    for i, item in enumerate(choices, 1):
        print(f'  {i}. {item}')
    index = choices.index(default)+1 if default in choices else (1 if len(choices)==1 else '')
    while True:
        value = ask('Nummer'+(' oder vollständigen Pfad eingeben' if manual else ''), index)
        if value.isdigit() and 1 <= int(value) <= len(choices):
            return choices[int(value)-1]
        if manual and value and (value.startswith('/') or value.startswith('~/')):
            return Path(value).expanduser().resolve()
        print('Bitte eine gültige Nummer'+(' oder einen absoluten Pfad' if manual else '')+' wählen.')


def build_plan(home):
    steam = choose('Steam-Verzeichnis', steam_roots(home), manual=True)
    libs = libraries(steam, home)
    use_game = yes('Kingdom Hearts einrichten?', True)
    use_openkh = yes('OpenKH einrichten?')
    if not use_game and not use_openkh:
        raise SetupError('Kein Programm ausgewählt.')
    runtimes = yes('Fehlende Windows-Runtimes prüfen/installieren?', True)
    dll = yes('Main version.dll im Spielordner einsetzen?', True) if use_game else False
    launch = yes('Steam-Startoptionen einrichten?', True)
    account = choose('Steam-Konto (userdata-ID)', accounts(steam))
    targets = []

    def add_target(label, appid, game=False):
        _, note = configuration(steam, account, appid, libs)
        print('\n'+label+' — '+note)
        print('Jetzt '+label+' über Steam starten und GEÖFFNET LASSEN. Dann hier Enter drücken.\n'
              'Der Assistent liest nur den tatsächlichen Prefix und Wine-Build; er startet nichts selbst.')
        while True:
            command=input('Enter = laufenden Start erkennen; ? = Experten-Inventar; Strg+C = abbrechen: ').strip()
            if command == '?':
                print('Gefundene Prefixe (nicht bestätigt):')
                print('\n'.join(map(str,prefixes(libs,appid))))
                print('Gefundene Proton-Builds (nicht bestätigt):')
                print('\n'.join(map(str,proton_candidates(home,libs,steam))))
                continue
            if command:
                print('Enter, ? oder Strg+C verwenden. Keine manuelle Proton-Nummer erforderlich.')
                continue
            try:
                evidence = observe(steam, account, appid, libs, proton_candidates(home, libs, steam))
                break
            except SetupError as error:
                print(str(error))
        print('Bestätigter Prefix: '+str(evidence.compat))
        print('Bestätigter ARM64-Proton: '+str(evidence.proton))
        print(label+' jetzt schließen. Steam erst nach der Erkennung aller Programme schließen.')
        targets.append(Target(label, appid, evidence.compat, evidence.proton, game, evidence))

    if use_game:
        add_target('Kingdom Hearts', APPID, True)
    if use_openkh:
        path = steam/'userdata'/account/'config/shortcuts.vdf'
        found = {f'{s.name} — {s.appid}': s for s in shortcuts(path.read_bytes())
                 if 'openkh' in (s.name+' '+s.exe).lower()} if path.is_file() else {}
        selected = found[choose('OpenKH Steam-Verknüpfung', found)]
        add_target('OpenKH', selected.appid)
    game = choose('Spielordner', game_dirs(libs), manual=True) if dll else Path('/')
    backup = Path(ask('Backup-Verzeichnis', home/'panacea-prefix-backups')).expanduser().resolve()
    raw = ask('Optional: vollständiger Pfad zur originalen add_registry.bat (Enter = überspringen)')
    batch = Path(raw).expanduser().resolve() if raw else None
    batch_id = choose('Registry-Batch im Prefix dieser AppID ausführen', [t.appid for t in targets]) if batch else APPID
    input('Jetzt Steam, Spiel und OpenKH vollständig schließen; danach Enter: ')
    plan = Plan(steam, account, game, backup, targets, runtimes, dll, launch, batch, batch_id)
    plan.validate()
    return plan


def review_and_install(plan, state):
    summary = plan_summary(plan)
    print('\nAUSWAHL PRÜFEN — bisher keine Installation\n\n'+summary)
    require_stopped()
    if ask('\nZum Einrichten genau JA eingeben; Enter beendet ohne Installation') != 'JA':
        print('Beendet ohne Installation.')
        return
    with setup_lock(state):
        with (state/'setup.log').open('w') as log:
            runner = Runner(print, log)
            runner.log('Panacea DroidDeck Setup — '+str(state/'setup.log'))
            runner.log(summary)
            try:
                folder = execute(plan, runner)
            except Exception as error:
                runner.log('FAILED: '+str(error))
                raise
    print('\nEinrichtung abgeschlossen. Backup: '+str(folder))
    print('Steam neu öffnen und Spiel/OpenKH testen. Die Runtime-Prüfung ersetzt keinen Spieltest.')


def main():
    home = Path.home()
    state = Path(os.environ.get('XDG_STATE_HOME', home/'.local/state'))/'panacea-arm'
    try:
        if platform.machine().lower() not in ('aarch64', 'arm64'):
            raise SetupError('Im ARM64-Linux-Desktop von DroidDeck starten.')
        print('Panacea / OpenKH Setup — Terminal-Assistent\n'
              'Zur Erkennung das jeweilige Programm über Steam öffnen; vor der Installation alles schließen.\n'
              'Vor der abschließenden Bestätigung wird nichts installiert. Strg+C bricht ab.')
        plan = build_plan(home)
        review_and_install(plan, state)
        input('\nEnter schließt den Assistenten.')
        return 0
    except (KeyboardInterrupt, EOFError):
        print('\nAbgebrochen. Bei Abbruch während der Installation das Setup-Log prüfen; kein automatischer Rollback.')
        return 130
    except (SetupError, OSError, UnicodeError, ValueError) as error:
        print('\nFEHLER: '+str(error))
        print('Installationslog (falls begonnen): '+str(state/'setup.log'))
        print('Vorhandene Backups bleiben erhalten; kein automatischer Rollback.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
