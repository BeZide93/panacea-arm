"""Host-side tests. No Wine, Steam account or package installation is used."""
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'linux-setup/assistant'))
import core
import terminal
import routing

CONFIG = b'''// preserve this comment\n"UserLocalConfigStore" { "Software" { "Valve" { "Steam" { "apps" {
"2552430" { "LaunchOptions" "PROTON_LOG=1 WINEDLLOVERRIDES=\\"version=b;foo=n\\" gamescope -f -- %command% -windowed" "other" "untouched" }
"42" { "LaunchOptions" "do not change" }
} } } } }\n'''


def shortcut_blob(appid=3000123456,options='PROTON_LOG=1 %command%',with_options=True):
    def string(k,v):return b'\x01'+k.encode()+b'\0'+v.encode()+b'\0'
    return (b'\x00shortcuts\0\x000\0\x02appid\0'+struct.pack('<I',appid)+
            string('AppName','OpenKH Mod Manager')+string('Exe','"/tmp/My OpenKH/OpenKh.Tools.ModsManager.exe"')+
            (string('LaunchOptions',options) if with_options else b'')+
            b'\x02AllowOverlay\0\x01\0\0\0\x00tags\0'+string('0','Test tag')+b'\x08\x08\x08\x08')


def pe(path,machine):
    path.parent.mkdir(parents=True,exist_ok=True)
    b=bytearray(128);b[:2]=b'MZ';struct.pack_into('<I',b,0x3c,64);b[64:68]=b'PE\0\0';struct.pack_into('<H',b,68,machine);path.write_bytes(b)


class Parsing(unittest.TestCase):
    def test_text_surgical(self):
        keys=['UserLocalConfigStore','Software','Valve','Steam','apps','2552430','LaunchOptions']
        node=core.descend(core.text_vdf(CONFIG.decode()),keys)
        changed=core.set_text_value(CONFIG,keys,'env TEST=1 %command%')
        self.assertEqual(changed,CONFIG[:node.start]+b'"env TEST=1 %command%"'+CONFIG[node.end:])
        self.assertIn(b'"42" { "LaunchOptions" "do not change" }',changed)

    def test_create_missing_nested_fields(self):
        raw=b'"UserLocalConfigStore" { "Software" { "Valve" { "Steam" { } } } }'
        keys=['UserLocalConfigStore','Software','Valve','Steam','apps','2552430','LaunchOptions']
        new=core.set_text_value(raw,keys,'test')
        self.assertEqual(core.descend(core.text_vdf(new.decode()),keys).value,'test')

    def test_reject_duplicate_and_malformed(self):
        for raw in ['"a" {','"a" bare','"a" "b" EXTRA']:
            with self.assertRaises(core.SetupError):core.text_vdf(raw)
        with self.assertRaises(core.SetupError):core.child(core.text_vdf('"a" "1" "A" "2"'),'a')

    def test_binary_highbit_and_unrelated_fields(self):
        raw=shortcut_blob();s=core.shortcuts(raw)[0]
        self.assertEqual(s.appid,'3000123456')
        n=core.child(s.record.value,'LaunchOptions')
        new=core.set_shortcut_options(raw,s.appid,'env PROTON_USE_WINED3D=1 %command%')
        self.assertEqual(new[:n.start],raw[:n.start])
        self.assertTrue(new.endswith(raw[n.end:]))
        self.assertEqual(core.shortcuts(new)[0].options,'env PROTON_USE_WINED3D=1 %command%')

    def test_missing_shortcut_options(self):
        raw=shortcut_blob(with_options=False)
        new=core.set_shortcut_options(raw,'3000123456','new options')
        self.assertEqual(core.shortcuts(new)[0].options,'new options')

    def test_binary_unknown_type_not_rewritten(self):
        with self.assertRaises(core.SetupError):core.shortcuts(b'\x00shortcuts\0\x09bad\0\x08\x08')
        with self.assertRaises(core.SetupError):core.shortcuts(shortcut_blob()[:-1])

    def test_launch_merge_preserves_wrapper_and_unrelated_override(self):
        old='PROTON_LOG=1 WINEDLLOVERRIDES="version,foo=b;*version=n;bar=b" gamescope -f -- %command% -windowed'
        new=core.merge_options(old,'WINEDLLOVERRIDES','version=n,b;dinput8=n,b;LuaBackend=n,b')
        self.assertIn('foo=b;bar=b;version=n,b;dinput8=n,b;LuaBackend=n,b',new)
        self.assertTrue(new.startswith('PROTON_LOG=1 '));self.assertTrue(new.endswith('gamescope -f -- %command% -windowed'))
        self.assertEqual(core.merge_options(new,'WINEDLLOVERRIDES','version=n,b;dinput8=n,b;LuaBackend=n,b'),new)

    def test_options_insert_and_args_only(self):
        for old in ['','-windowed','gamescope -- %command%']:
            new=core.merge_options(old,'PROTON_USE_WINED3D','1')
            self.assertEqual(new.count('%command%'),1)
            self.assertEqual(core.merge_options(new,'PROTON_USE_WINED3D','1'),new)
        self.assertEqual(core.merge_options('-arg','PROTON_USE_WINED3D','1'),'env PROTON_USE_WINED3D=1 %command% -arg')

    def test_dynamic_options_rejected(self):
        for old in ['$(touch /tmp/nope) %command%', '`bad` %command%', '%command% ; bad', '%command% %command%',
                    'PROTON_USE_WINED3D=0 PROTON_USE_WINED3D=1 %command%', '%command% PROTON_USE_WINED3D=1', 'PROTON_USE_WINED3D=1']:
            with self.assertRaises(core.SetupError):core.merge_options(old,'PROTON_USE_WINED3D','1')


class TemporaryFixture(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='panacea test ; ');self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()


class Environment(TemporaryFixture):
    def test_multiple_libraries_and_prefix_ids(self):
        steam=self.root/'Steam';extra=self.root/'Extra games';(steam/'steamapps').mkdir(parents=True)
        (steam/'steamapps/libraryfolders.vdf').write_text('"libraryfolders" { "0" { "path" '+core.quote(str(steam))+' } "1" { "path" '+core.quote(str(extra))+' } }')
        p=extra/'steamapps/compatdata/3000123456/pfx';p.mkdir(parents=True);(p/'system.reg').touch()
        libs=core.libraries(steam,self.root)
        self.assertIn(extra,libs);self.assertEqual(core.prefixes(libs,'3000123456'),[p.parent])
        with self.assertRaises(core.SetupError):core.prefixes(libs,'$(false)')

    def test_dotnet_nested_architectures_and_newer_8(self):
        prefix=self.root/'pfx'
        x64=prefix/'drive_c/Program Files/dotnet/x64/dotnet.exe';x86=prefix/'drive_c/Program Files (x86)/dotnet/dotnet.exe'
        pe(x64,0x8664);pe(x86,0x14c)
        self.assertEqual(set(core.dotnet_hosts(prefix)),{x64,x86})
        text='Microsoft.NETCore.App 8.0.30 [C:\\some path]\nMicrosoft.WindowsDesktop.App 8.0.30 [C:\\some path]\n'
        reports=[(core.pe_machine(p),text) for p in core.dotnet_hosts(prefix)]
        self.assertTrue(core.runtime_ready(reports,'Microsoft.WindowsDesktop.App'))
        self.assertFalse(core.runtime_ready([(0xaa64,text)],'Microsoft.WindowsDesktop.App'))
        self.assertFalse(core.runtime_ready([(0x8664,text)],'Microsoft.WindowsDesktop.App'))

    def test_atomic_change_guard(self):
        p=self.root/'localconfig.vdf';p.write_bytes(b'old');p.chmod(0o600)
        with self.assertRaises(core.SetupError):core.atomic_replace(p,b'new',b'wrong')
        self.assertEqual(p.read_bytes(),b'old');core.atomic_replace(p,b'new',b'old')
        self.assertEqual(p.stat().st_mode&0o777,0o600)
        link=self.root/'link';link.symlink_to(p)
        with self.assertRaises(core.SetupError):core.atomic_replace(link,b'x',b'new')

    def test_process_detection(self):
        p=self.root/'123';p.mkdir();(p/'comm').write_text('steam\n')
        self.assertEqual(core.running_clients(self.root),['steam (PID 123)'])

    def test_lock_excludes_second_run(self):
        with core.setup_lock(self.root):
            with self.assertRaises(core.SetupError):
                with core.setup_lock(self.root):pass


class Execution(TemporaryFixture):
    def setUp(self):
        super().setUp()
        self.steam=self.root/'Steam';(self.steam/'steamapps').mkdir(parents=True)
        self.cfg=self.steam/'userdata/123/config';self.cfg.mkdir(parents=True)
        (self.cfg/'localconfig.vdf').write_bytes(CONFIG)
        (self.cfg/'shortcuts.vdf').write_bytes(shortcut_blob())
        self.proton=self.root/'Proton path';b=self.proton/'files/bin-arm64';b.mkdir(parents=True)
        for name in ['wine','wineserver']:
            (b/name).write_text('#!/bin/sh\necho WINE_TEST_OK\nexit 0\n');(b/name).chmod(0o755)
        self.targets=[]
        for appid in [core.APPID,'3000123456']:
            c=self.steam/f'steamapps/compatdata/{appid}';(c/'pfx/drive_c').mkdir(parents=True)
            (c/'pfx/system.reg').write_text('original registry')
            (c/'pfx/drive_c/save.dat').write_bytes(b'save data')
            self.targets.append(core.Target('KH' if appid==core.APPID else 'OpenKH',appid,c,self.proton,appid==core.APPID))
        self.game=self.root/'KINGDOM HEARTS ; weird $(path)';self.game.mkdir()
        (self.game/'KINGDOM HEARTS II FINAL MIX.exe').touch();(self.game/'version.dll').write_bytes(b'old DLL')
        self.plan=core.Plan(self.steam,'123',self.game,self.root/'backups',self.targets,runtimes=False)
        self.log=io.StringIO();self.runner=core.Runner(lambda s:None,self.log)
        self.proc=self.root/'proc';self.proc.mkdir()
        for index,t in enumerate(self.targets):
            process=self.proc/str(100+index);process.mkdir()
            (process/'exe').symlink_to(self.proton/'files/bin-arm64/wine')
            values={'SteamAppId':t.appid,'STEAM_COMPAT_CLIENT_INSTALL_PATH':str(self.steam),
                    'STEAM_COMPAT_DATA_PATH':str(t.compat),'WINEPREFIX':str(t.compat/'pfx')}
            (process/'environ').write_bytes(b'\0'.join(f'{k}={v}'.encode() for k,v in values.items()))
            t.evidence=routing.observe(self.steam,'123',t.appid,[self.steam],[self.proton],self.proc)


    @patch('core.require_stopped')
    def test_full_install_both_prefixes_backup_and_idempotency(self,stopped):
        folder=core.execute(self.plan,self.runner)
        meta=json.loads((folder/'backup.json').read_text());self.assertTrue(meta['complete'])
        self.assertEqual(len(meta['prefixes']),2)
        for item in meta['prefixes']:
            self.assertEqual((Path(item['backup'])/'drive_c/save.dat').read_bytes(),b'save data')
        self.assertEqual(core.digest((self.game/'version.dll').read_bytes()),core.DLL_SHA256)
        openkh=core.shortcuts((self.cfg/'shortcuts.vdf').read_bytes())[0]
        self.assertIn('PROTON_USE_WINED3D=1',openkh.options)
        kh=(self.cfg/'localconfig.vdf').read_text();self.assertNotIn('PROTON_USE_WINED3D',kh);self.assertIn('foo=n',kh)
        self.assertEqual(core.launch_edits(self.plan),[])
        self.assertGreaterEqual(stopped.call_count,3)

    @patch('core.require_stopped')
    def test_failure_preserves_dll_config_and_backup(self,_):
        (self.proton/'files/bin-arm64/wine').write_text('#!/bin/sh\nexit 7\n')
        for t in self.targets:
            t.evidence=routing.observe(self.steam,'123',t.appid,[self.steam],[self.proton],self.proc)
        before=(self.cfg/'localconfig.vdf').read_bytes()
        with self.assertRaises(core.SetupError):core.execute(self.plan,self.runner)
        self.assertEqual((self.game/'version.dll').read_bytes(),b'old DLL')
        self.assertEqual((self.cfg/'localconfig.vdf').read_bytes(),before)
        backups=list(self.plan.backup_root.glob('*/backup.json'));self.assertEqual(len(backups),1)
        self.assertTrue(json.loads(backups[0].read_text())['complete'])

    def test_backup_inside_prefix_and_wrong_id_rejected(self):
        self.plan.backup_root=self.targets[0].compat/'pfx/backup'
        with self.assertRaises(core.SetupError):self.plan.validate()
        self.plan.backup_root=self.root/'backups';self.targets[0].appid='42'
        with self.assertRaises(core.SetupError):self.plan.validate()

    def test_file_changes_between_review_and_commit(self):
        p=self.cfg/'localconfig.vdf';before=p.read_bytes();p.write_bytes(b'changed by Steam')
        with self.assertRaises(core.SetupError):core.atomic_replace(p,b'new',before)
        self.assertEqual(p.read_bytes(),b'changed by Steam')

    @patch('core.require_stopped')
    def test_no_install_on_bad_launch_options(self,_):
        p=self.cfg/'shortcuts.vdf';p.write_bytes(shortcut_blob(options='$(bad) %command%'))
        with self.assertRaises(core.SetupError):core.execute(self.plan,self.runner)
        self.assertFalse(self.plan.backup_root.exists())

    @patch('core.require_stopped')
    def test_terminal_review_cancel_does_not_mutate(self, _):
        before=(self.cfg/'localconfig.vdf').read_bytes()
        with patch('terminal.require_stopped'), patch('builtins.input',return_value=''), patch('builtins.print'), patch('terminal.execute') as execute:
            terminal.review_and_install(self.plan,self.root/'state')
            execute.assert_not_called()
        self.assertEqual((self.cfg/'localconfig.vdf').read_bytes(),before)
        self.assertFalse((self.root/'state').exists())
        self.assertFalse(self.plan.backup_root.exists())

    @patch('core.require_stopped')
    def test_terminal_confirmation_uses_real_backups_and_installer(self, _):
        with patch('terminal.require_stopped'), patch('builtins.input',return_value='JA'), patch('builtins.print'):
            terminal.review_and_install(self.plan,self.root/'state')
        self.assertEqual(core.digest((self.game/'version.dll').read_bytes()),core.DLL_SHA256)
        self.assertTrue(list(self.plan.backup_root.glob('*/backup.json')))
        self.assertIn('BACKUP COMPLETE',(self.root/'state/setup.log').read_text())

    def test_terminal_detects_both_targets_without_writes(self):
        answers=['','', 'j', '', '', '', '', '', '', '', '', '', '', '', '']
        with patch('terminal.steam_roots',return_value=[self.steam]), patch('terminal.proton_candidates',return_value=[self.proton]), patch('terminal.game_dirs',return_value=[self.game]), patch('terminal.observe',side_effect=[t.evidence for t in self.targets]), patch('builtins.input',side_effect=answers), patch('builtins.print'):
            plan=terminal.build_plan(self.root)
        self.assertEqual([t.appid for t in plan.targets],[core.APPID,'3000123456'])
        self.assertEqual(plan.account,'123')
        self.assertTrue(plan.runtimes and plan.install_dll and plan.launch_options)
        self.assertIsNone(plan.registry_batch)
        self.assertEqual((self.game/'version.dll').read_bytes(),b'old DLL')

    @patch('core.require_stopped')
    def test_winetricks_download_needs_no_sudo_when_tools_present(self, _):
        self.plan.runtimes=True
        with patch('core.shutil.which',side_effect=lambda name: None if name=='sudo' else '/bin/'+name), patch('core.os.geteuid',return_value=10234), patch.object(self.runner,'run',side_effect=core.SetupError('stop at helper')) as run:
            with self.assertRaisesRegex(core.SetupError,'stop at helper'):
                core.execute(self.plan,self.runner)
        self.assertEqual(run.call_args.args[0],['bash',core.KIT/'00-host-tools.sh','--install'])
        self.assertFalse(self.plan.backup_root.exists())

    @patch('core.require_stopped')
    def test_missing_tools_without_sudo_stop_before_backup(self, _):
        self.plan.runtimes=True
        with patch('core.shutil.which',side_effect=lambda name: None if name in ('sudo','cabextract') else '/bin/'+name), patch('core.os.geteuid',return_value=10234), patch.object(self.runner,'run') as run:
            with self.assertRaisesRegex(core.SetupError,'Missing Linux tools: cabextract'):
                core.execute(self.plan,self.runner)
            run.assert_not_called()
        self.assertFalse(self.plan.backup_root.exists())

    def set_mapping(self, name='droiddeck-proton-arm64', key=None):
        path=self.steam/'config/config.vdf';path.parent.mkdir(exist_ok=True)
        path.write_text('"InstallConfigStore" { "Software" { "Valve" { "Steam" { "CompatToolMapping" { "'+(key or core.APPID)+'" { "name" "'+name+'" } } } } } }')
        folder=self.steam/'compatibilitytools.d'/name;folder.mkdir(parents=True,exist_ok=True)
        (folder/'compatibilitytool.vdf').write_text('"compatibilitytools" { "compat_tools" { "'+name+'" { "display_name" "Proton" } } }')
        (folder/'toolmanifest.vdf').write_text('"manifest" { "commandline" "/droiddeck-proton" }')
        (folder/'droiddeck-proton').write_text('#!/bin/sh\n# wrapper fixture\n')
        return folder

    def process_env(self, index=0, **changes):
        path=self.proc/str(100+index)/'environ'
        values=dict(item.split('=',1) for item in path.read_text().split('\0') if '=' in item)
        values.update(changes)
        path.write_bytes(b'\0'.join(f'{k}={v}'.encode() for k,v in values.items()))

    def observe_game(self, candidates=None):
        return routing.observe(self.steam,'123',core.APPID,[self.steam],candidates or [self.proton],self.proc)

    def test_routing_default_and_per_app_mapping(self):
        self.set_mapping('default',key='0')
        self.assertEqual(routing.mapping_choice(self.steam,core.APPID),('default','Steam-Standard'))
        self.set_mapping('specific')
        self.assertEqual(routing.mapping_choice(self.steam,core.APPID),('specific','Steam-Zuordnung für diese App'))

    def test_routing_wrapper_may_launch_different_wine_tree(self):
        wrapper=self.set_mapping()
        self.process_env(STEAM_COMPAT_TOOL_PATHS=str(wrapper),WINEESYNC='1',BL_SYNC_PACK='test-pack')
        proof=self.observe_game()
        self.assertEqual(proof.proton,self.proton)
        self.assertNotEqual(proof.proton,wrapper)
        self.targets[0].evidence=proof
        env=core.wine_env(self.targets[0],self.steam)
        self.assertEqual(env['WINEESYNC'],'1')
        self.assertEqual(env['BL_SYNC_PACK'],'test-pack')
        self.assertEqual(env['WINESERVER'],str(self.proton/'files/bin-arm64/wineserver'))

    def test_routing_saved_tool_conflict_rejected(self):
        self.set_mapping()
        self.process_env(STEAM_COMPAT_TOOL_PATHS='/different/tool')
        with self.assertRaisesRegex(core.SetupError,'widersprechen'):
            self.observe_game()

    def test_routing_actual_prefix_wins_over_duplicate_old_prefix(self):
        other=self.root/'other/steamapps/compatdata'/core.APPID
        (other/'pfx/drive_c').mkdir(parents=True);(other/'pfx/system.reg').touch()
        (other/'config_info').write_text('/old/proton/files/share/wine\n')
        proof=self.observe_game()
        self.assertEqual(proof.compat,self.targets[0].compat)
        self.assertNotEqual(proof.compat,other)

    def test_routing_no_process_old_config_is_not_proof(self):
        (self.proc/'100/environ').unlink()
        (self.targets[0].compat/'config_info').write_text(str(self.proton)+'/files/share/wine\n')
        with self.assertRaisesRegex(core.SetupError,'Kein eindeutiger'):
            self.observe_game()

    def test_routing_shortcut_unsigned_game_id(self):
        self.process_env(1,SteamAppId='0',STEAM_COMPAT_APP_ID='0',SteamGameId=str((3000123456 << 32) | 0x02000000))
        proof=routing.observe(self.steam,'123','3000123456',[self.steam],[self.proton],self.proc)
        self.assertEqual(proof.compat,self.targets[1].compat)

    def test_routing_wrong_prefix_and_mixed_server_rejected(self):
        self.process_env(WINEPREFIX='/wrong/pfx')
        with self.assertRaisesRegex(core.SetupError,'WINEPREFIX'):
            self.observe_game()
        self.process_env(WINEPREFIX=str(self.targets[0].compat/'pfx'),WINESERVER='/other/files/bin-arm64/wineserver')
        with self.assertRaisesRegex(core.SetupError,'WINESERVER'):
            self.observe_game()

    def test_routing_multiple_running_prefixes_rejected(self):
        import shutil
        shutil.copytree(self.proc/'100',self.proc/'200',symlinks=True)
        other=self.root/'other'/core.APPID
        (other/'pfx/drive_c').mkdir(parents=True);(other/'pfx/system.reg').touch()
        env=self.proc/'200/environ';env.write_text(env.read_text().replace(str(self.targets[0].compat),str(other)))
        with self.assertRaisesRegex(core.SetupError,'Kein eindeutiger'):
            self.observe_game()

    def test_routing_hardlinks_disambiguated_by_live_path(self):
        other=self.root/'shadow';b=other/'files/bin-arm64';b.mkdir(parents=True)
        os.link(self.proton/'files/bin-arm64/wine',b/'wine')
        os.link(self.proton/'files/bin-arm64/wineserver',b/'wineserver')
        exe=self.proc/'100/exe';exe.unlink();exe.symlink_to(b/'wine')
        self.assertEqual(self.observe_game([self.proton,other]).proton,other)

    def test_routing_changes_and_expired_evidence_rejected(self):
        proof=self.targets[0].evidence
        proof.captured-=1801
        with self.assertRaisesRegex(core.SetupError,'30 Minuten'):
            routing.validate_targets(self.plan)
        self.targets[0].evidence=self.observe_game()
        self.set_mapping()
        with self.assertRaisesRegex(core.SetupError,'geändert'):
            routing.validate_targets(self.plan)

    @patch('core.require_stopped')
    def test_routing_changed_build_stops_before_any_backup(self,_):
        (self.proton/'files/bin-arm64/wineserver').write_text('# changed\n')
        with self.assertRaisesRegex(core.SetupError,'geändert'):
            core.execute(self.plan,self.runner)
        self.assertFalse(self.plan.backup_root.exists())

    @patch('core.require_stopped')
    def test_routing_manual_path_without_evidence_cannot_install(self,_):
        self.targets[0].evidence=None
        with self.assertRaisesRegex(core.SetupError,'noch nicht'):
            core.execute(self.plan,self.runner)
        self.assertFalse(self.plan.backup_root.exists())

    def test_runtime_skip_and_wrong_arch_record_fails(self):
        target=self.targets[0];(target.compat/'pfx/winetricks.log').write_text('dotnet8\ndotnetdesktop8\nvcrun6\nxaudio29\n')
        out='Microsoft.NETCore.App 8.0.30 [x]\nMicrosoft.WindowsDesktop.App 8.0.30 [x]\n'
        with patch('core.reports',return_value=[(0x14c,out),(0x8664,out)]):
            core.install_runtimes(target,self.plan,self.runner)
        self.assertNotIn('winetricks -q',self.log.getvalue())
        with patch('core.reports',return_value=[(0x14c,out)]):
            with self.assertRaises(core.SetupError):core.install_runtimes(target,self.plan,self.runner)


class Startup(TemporaryFixture):
    def test_missing_tk_starts_terminal_without_package_manager(self):
        bin_dir=self.root/'bin';bin_dir.mkdir()
        calls=self.root/'calls'
        for name,body in {
            'uname':'echo aarch64',
            'python3':'echo "$*" >> "$CALLS"; if [ "$1" = -c ]; then exit 1; fi',
            'sudo':'echo UNEXPECTED_SUDO >> "$CALLS"; exit 99',
            'pacman':'echo UNEXPECTED_PACMAN >> "$CALLS"; exit 99',
            'apt-get':'echo UNEXPECTED_APT >> "$CALLS"; exit 99',
        }.items():
            path=bin_dir/name;path.write_text('#!/bin/sh\n'+body+'\n');path.chmod(0o755)
        env=dict(os.environ,PATH=str(bin_dir)+':'+os.environ['PATH'],CALLS=str(calls))
        result=subprocess.run(['bash',str(ROOT/'linux-setup/start-setup.sh')],env=env,input='',text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(calls.read_text().splitlines(),['-c import tkinter','assistant/terminal.py'])

    def test_host_tools_reuse_skips_packages_and_verifies_download(self):
        import shutil
        kit=self.root/'kit';kit.mkdir()
        (kit/'common.sh').write_bytes((ROOT/'linux-setup/common.sh').read_bytes())
        # Use a fixture payload and its real checksum; no network/install commands.
        payload=b'fixture winetricks\n'
        script=(ROOT/'linux-setup/00-host-tools.sh').read_text().replace(core.WINETRICKS_SHA256,core.digest(payload))
        (kit/'00-host-tools.sh').write_text(script)
        bin_dir=self.root/'bin';bin_dir.mkdir()
        for name in ['dirname','mkdir','mktemp','sha256sum','chmod','mv','rm']:
            (bin_dir/name).symlink_to(shutil.which(name))
        for name in ['python3','cabextract','unzip','file']:
            path=bin_dir/name;path.write_text('#!/bin/sh\nexit 0\n');path.chmod(0o755)
        curl=bin_dir/'curl'
        curl.write_text('#!/bin/sh\nwhile [ "$1" != -o ]; do shift; done\nprintf "fixture winetricks\\n" > "$2"\n');curl.chmod(0o755)
        env=dict(os.environ,PATH=str(bin_dir))
        result=subprocess.run(['/bin/bash',str(kit/'00-host-tools.sh'),'--install'],env=env,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('package installation skipped',result.stdout)
        self.assertEqual((kit/'tools/winetricks').read_bytes(),payload)

    def test_ambiguous_selection_has_no_silent_default(self):
        with patch('builtins.input',side_effect=['','2']) as prompt, patch('builtins.print'):
            self.assertEqual(terminal.choose('Proton',['old','new']), 'new')
        self.assertNotIn('[1]',prompt.call_args_list[0].args[0])


if __name__=='__main__':unittest.main()
