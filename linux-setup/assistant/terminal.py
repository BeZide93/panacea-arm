"""Tk-free assistant; the same plan, validation, backups and installer as the GUI."""
import os
from pathlib import Path
import platform

from core import (APPID, Plan, Runner, SetupError, Target, accounts, execute,
                  plan_summary, require_stopped, setup_lock, shortcuts)
from setup_profile import load_profile


def ask(label, default=''):
    value = input(label + (f' [{default}]' if default else '') + ': ').strip()
    return value or str(default)


def yes(label, default=False):
    while True:
        value = ask(label + (' [Y/n]' if default else ' [y/N]')).lower()
        if not value:
            return default
        if value in ('j', 'ja', 'y', 'yes'):
            return True
        if value in ('n', 'nein', 'no'):
            return False
        print('Enter y or n.')


def choose(label, choices, default=None, manual=False):
    """Only a unique choice (or recorded Proton hint) receives a default."""
    choices = list(choices)
    if not choices and not manual:
        raise SetupError('No choices found: '+label)
    print('\n'+label)
    for i, item in enumerate(choices, 1):
        print(f'  {i}. {item}')
    index = choices.index(default)+1 if default in choices else (1 if len(choices)==1 else '')
    while True:
        value = ask('Number'+(' or enter a full path' if manual else ''), index)
        if value.isdigit() and 1 <= int(value) <= len(choices):
            return choices[int(value)-1]
        if manual and value and (value.startswith('/') or value.startswith('~/')):
            return Path(value).expanduser().resolve()
        print('Select a valid number'+(' or an absolute path' if manual else '')+'.')


def build_plan(home):
    profile = load_profile(home)
    steam = profile.steam
    proton = profile.require_proton()
    print('Manual DroidDeck profile:')
    print('Steam: '+str(steam)+'\nProton: '+str(proton)+'\n'+profile.note)
    use_game = yes('Set up Kingdom Hearts?', True)
    use_openkh = yes('Set up OpenKH?')
    if not use_game and not use_openkh:
        raise SetupError('No application selected.')
    runtimes = yes('Check/install missing Windows runtimes?', True)
    dll = yes('Install main version.dll in the game directory?', True) if use_game else False
    launch = yes('Configure Steam launch options?', True)
    account = choose('Steam account (userdata ID)', accounts(steam)) if launch or use_openkh else ''
    targets = []

    def add_target(label, appid, game=False):
        compat = profile.compat(appid)
        if not (compat/'pfx/system.reg').is_file() or not (compat/'pfx/drive_c').is_dir():
            raise SetupError(f'{label}: Prefix missing at the expected location: {compat}. '
                             'No fallback to another library. Check the path/setup.')
        print(label+' Prefix: '+str(compat))
        targets.append(Target(label, appid, compat, proton, game))

    if use_game:
        add_target('Kingdom Hearts', APPID, True)
    if use_openkh:
        path = steam/'userdata'/account/'config/shortcuts.vdf'
        found = {f'{s.name} — {s.appid}': s for s in shortcuts(path.read_bytes())
                 if 'openkh' in (s.name+' '+s.exe).lower()} if path.is_file() else {}
        selected = found[choose('OpenKH Steam shortcut', found)]
        add_target('OpenKH', selected.appid)
    game = profile.game if dll else Path('/')
    backup = Path(ask('Backup directory', profile.backup)).expanduser().resolve()
    raw = ask('Optional: full path to the original add_registry.bat (Enter = skip)')
    batch = Path(raw).expanduser().resolve() if raw else None
    batch_id = choose('Run registry batch in the prefix for this AppID', [t.appid for t in targets]) if batch else APPID
    plan = Plan(steam, account, game, backup, targets, runtimes, dll, launch, batch, batch_id)
    plan.validate()
    return plan


def review_and_install(plan, state):
    summary = plan_summary(plan)
    print('\nREVIEW SELECTION — nothing installed yet\n\n'+summary)
    require_stopped()
    if ask('\nType YES exactly to install; Enter exits without installing') != 'YES':
        print('Exited without installing.')
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
    print('\nSetup complete. Backup: '+str(folder))
    print('Reopen Steam and test the game/OpenKH. Runtime checks do not replace an in-game test.')


def main():
    home = Path.home()
    state = Path(os.environ.get('XDG_STATE_HOME', home/'.local/state'))/'panacea-arm'
    try:
        if platform.machine().lower() not in ('aarch64', 'arm64'):
            raise SetupError('Run this inside the DroidDeck ARM64 Linux desktop.')
        print('Panacea / OpenKH Setup — Terminal assistant\n'
              'Fully close Steam, the game and Windows applications.\n'
              'Nothing is installed before final confirmation. Ctrl+C cancels.')
        plan = build_plan(home)
        review_and_install(plan, state)
        input('\nPress Enter to close the assistant.')
        return 0
    except (KeyboardInterrupt, EOFError):
        print('\nCancelled. If installation was interrupted, check the setup log; there is no automatic rollback.')
        return 130
    except (SetupError, OSError, UnicodeError, ValueError) as error:
        print('\nERROR: '+str(error))
        print('Installation log (if started): '+str(state/'setup.log'))
        print('Existing backups are kept; there is no automatic rollback.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
