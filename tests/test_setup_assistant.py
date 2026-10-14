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
import setup_profile
import web

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
        with patch('terminal.require_stopped'), patch('builtins.input',return_value='YES'), patch('builtins.print'):
            terminal.review_and_install(self.plan,self.root/'state')
        self.assertEqual(core.digest((self.game/'version.dll').read_bytes()),core.DLL_SHA256)
        self.assertTrue(list(self.plan.backup_root.glob('*/backup.json')))
        self.assertIn('BACKUP COMPLETE',(self.root/'state/setup.log').read_text())

    def test_terminal_detects_both_targets_without_writes(self):
        answers=['','j','','','','','','','']
        profile=setup_profile.Profile(self.steam,self.game,self.targets[0].compat,self.root/'backups',self.proton,'fixture')
        with patch('terminal.load_profile',return_value=profile), patch('builtins.input',side_effect=answers), patch('builtins.print'):
            plan=terminal.build_plan(self.root)
        self.assertEqual([t.appid for t in plan.targets],[core.APPID,'3000123456'])
        self.assertEqual(plan.account,'123')
        self.assertTrue(plan.runtimes and plan.install_dll and plan.launch_options)
        self.assertIsNone(plan.registry_batch)
        self.assertEqual((self.game/'version.dll').read_bytes(),b'old DLL')

    @patch('core.require_stopped')
    def test_winetricks_download_needs_no_sudo_when_tools_present(self, _):
        self.plan.runtimes=True
        with patch('core.shutil.which',side_effect=lambda name, **kw: None if name=='sudo' else '/bin/'+name), patch('core.os.geteuid',return_value=10234), patch.object(self.runner,'run',side_effect=core.SetupError('stop at helper')) as run:
            with self.assertRaisesRegex(core.SetupError,'stop at helper'):
                core.execute(self.plan,self.runner)
        self.assertEqual(run.call_args.args[0],['bash',core.KIT/'00-host-tools.sh','--install'])
        self.assertFalse(self.plan.backup_root.exists())

    @patch('core.require_stopped')
    def test_missing_tools_without_sudo_stop_before_backup(self, _):
        self.plan.runtimes=True
        with patch('core.shutil.which',side_effect=lambda name, **kw: None if name in ('sudo','cabextract') else '/bin/'+name), patch('core.os.geteuid',return_value=10234), patch.object(self.runner,'run') as run:
            with self.assertRaisesRegex(core.SetupError,'Missing Linux tools: cabextract'):
                core.execute(self.plan,self.runner)
            run.assert_not_called()
        self.assertFalse(self.plan.backup_root.exists())

    @patch('core.require_stopped')
    def test_arm_helper_failure_stops_before_prefix_changes(self, _):
        self.plan.runtimes=True
        before=(self.cfg/'localconfig.vdf').read_bytes()
        with patch('core.platform.machine',return_value='aarch64'), patch('host_tools.prepare',side_effect=core.SetupError('helper download failed')) as prepare:
            with self.assertRaisesRegex(core.SetupError,'helper download failed'):
                core.execute(self.plan,self.runner)
        prepare.assert_called_once()
        self.assertFalse(self.plan.backup_root.exists())
        self.assertEqual((self.game/'version.dll').read_bytes(),b'old DLL')
        self.assertEqual((self.cfg/'localconfig.vdf').read_bytes(),before)

    def test_runtime_skip_and_wrong_arch_record_fails(self):
        target=self.targets[0];(target.compat/'pfx/winetricks.log').write_text('dotnet8\ndotnetdesktop8\nvcrun6\nxaudio29\n')
        out='Microsoft.NETCore.App 8.0.30 [x]\nMicrosoft.WindowsDesktop.App 8.0.30 [x]\n'
        with patch('core.reports',return_value=[(0x14c,out),(0x8664,out)]):
            core.install_runtimes(target,self.plan,self.runner)
        self.assertNotIn('winetricks -q',self.log.getvalue())
        with patch('core.reports',return_value=[(0x14c,out)]):
            with self.assertRaises(core.SetupError):core.install_runtimes(target,self.plan,self.runner)

    def dotnet_warning_fixture(self, verb='dotnet8', code=1, message=None):
        target=self.targets[1]
        pe(target.compat/'pfx/drive_c/Program Files/dotnet/x64/dotnet.exe',0x8664)
        kit=self.root/'runtime-kit';(kit/'tools').mkdir(parents=True,exist_ok=True)
        warning=message or f'warning: {verb} install completed, but installed file {target.compat}/pfx/dosdevices/c:/Program Files/dotnet/dotnet.exe not found'
        (kit/'tools/winetricks').write_text('printf "%s\\n" '+shlex.quote(warning)+'\nexit '+str(code)+'\n')
        both='Microsoft.NETCore.App 8.0.30 [x]\nMicrosoft.WindowsDesktop.App 8.0.30 [x]\n'
        complete=[(0x8664,both),(0x14c,both)]
        before=[(0x8664,both)] if verb=='dotnet8' else [(0x8664,both),(0x14c,'Microsoft.NETCore.App 8.0.12 [x]\n')]
        return target,kit,before,complete

    def test_dotnet_flat_path_warning_requires_working_runtimes_and_skips_on_retry(self):
        for verb in ('dotnet8','dotnetdesktop8'):
            with self.subTest(verb=verb):
                target,kit,before,complete=self.dotnet_warning_fixture(verb)
                with patch('core.KIT',kit),patch('core.reports',side_effect=[before,complete,complete]) as reports:
                    core.install_runtimes(target,self.plan,self.runner)
                    core.install_runtimes(target,self.plan,self.runner)
                self.assertEqual(reports.call_count,3)
                self.assertIn(verb+' verified by working x86/x64',self.log.getvalue())
        self.assertEqual(self.log.getvalue().count(' -q dotnet8\n'),1)
        self.assertEqual(self.log.getvalue().count(' -q dotnetdesktop8\n'),1)

    def test_dotnet_flat_path_warning_does_not_hide_missing_architecture(self):
        target,kit,before,complete=self.dotnet_warning_fixture()
        with patch('core.KIT',kit),patch('core.reports',side_effect=[before,before]):
            with self.assertRaisesRegex(core.SetupError,'not working in both'):
                core.install_runtimes(target,self.plan,self.runner)
        self.assertNotIn('accepted the Winetricks',self.log.getvalue())

    def test_dotnet_other_errors_are_not_accepted(self):
        for code,message in [(1,'MSI failed with error 1603'),(2,None)]:
            with self.subTest(code=code):
                target,kit,before,complete=self.dotnet_warning_fixture(code=code,message=message)
                with patch('core.KIT',kit),patch('core.reports',return_value=before) as reports:
                    with self.assertRaises(core.CommandError) as error:
                        core.install_runtimes(target,self.plan,self.runner)
                self.assertEqual(error.exception.returncode,code)
                self.assertEqual(reports.call_count,1)

    @patch('core.require_stopped')
    def test_desktop_path_reuses_local_cabextract_without_sudo(self, _):
        import shutil
        host=self.root/'host-bin';host.mkdir()
        local=self.root/'.local/bin';local.mkdir(parents=True)
        for name in ['python3','curl','unzip','file']:
            p=host/name;p.write_text('#!/bin/sh\nexit 0\n');p.chmod(0o755)
        (host/'cp').symlink_to(shutil.which('cp'))
        cab=local/'cabextract';cab.write_text('#!/bin/sh\necho "cabextract version 1.11"\n');cab.chmod(0o755)
        kit=self.root/'kit';(kit/'tools').mkdir(parents=True)
        payload=b'verified fixture winetricks'
        (kit/'tools/winetricks').write_bytes(payload)
        self.plan.runtimes=True;self.plan.install_dll=False
        def runtime(target, plan, runner):
            # The same helper must be visible to both host commands and Winetricks.
            env=core.wine_env(target,plan.steam)
            self.assertEqual(env['PATH'].split(':')[:2],[str(self.proton/'files/bin-arm64'),str(local)])
            for scope in [None,env]:
                self.assertIn('version 1.11',runner.run(['cabextract','--version'],env=scope))
        with patch.dict(os.environ,HOME=str(self.root),PATH=str(host)), patch('core.platform.machine',return_value='aarch64'), patch('core.KIT',kit), patch('core.WINETRICKS_SHA256',core.digest(payload)), patch('core.os.geteuid',return_value=10234), patch('core.install_runtimes',side_effect=runtime):
            self.assertIsNone(shutil.which('cabextract'))
            self.assertIsNone(shutil.which('sudo'))
            before=os.environ.copy()
            folder=core.execute(self.plan,self.runner)
            self.assertEqual(os.environ,before)
        self.assertTrue((folder/'backup.json').is_file())
        self.assertIn('Using cabextract: '+str(cab),self.log.getvalue())
        self.assertNotIn('00-host-tools.sh',self.log.getvalue())
        self.assertIn('SETUP COMPLETE',self.log.getvalue())


class BrowserInterface(unittest.TestCase):
    def setUp(self):
        self.fixture=Execution(methodName='runTest');self.fixture.setUp()
        f=self.fixture
        self.profile=setup_profile.Profile(f.steam,f.game,f.targets[0].compat,f.root/'backups',f.proton,'fixture')
        self.profile_patch=patch('web.load_profile',return_value=self.profile);self.profile_patch.start()
        self.stopped_patch=patch('web.require_stopped');self.stopped_patch.start()
        self.app=web.Application(f.root)
        self.app.state_dir=f.root/'state'
        self.data={'account':'123','shortcut':'3000123456','game':True,'openkh':True,
                   'runtimes':False,'dll':True,'launch':True,'backup':str(f.root/'backups'),
                   'batch':'','batch_target':core.APPID}
    def tearDown(self):
        self.stopped_patch.stop();self.profile_patch.stop();self.fixture.tearDown()

    def test_review_creates_no_files_and_requires_confirmation(self):
        review=self.app.review(self.data)
        self.assertIn('OpenKH',review['summary'])
        self.assertFalse(self.app.state_dir.exists())
        self.assertFalse(self.profile.backup.exists())
        with self.assertRaisesRegex(core.SetupError,'first'):
            self.app.start('invalid')

    def test_profile_change_after_review_rejected(self):
        review=self.app.review(self.data)
        self.profile.backup=self.fixture.root/'different'
        # Backup is explicitly chosen in the UI; change a fixed profile path.
        self.profile.game=self.fixture.root/'not a game'
        with self.assertRaises(core.SetupError):self.app.start(review['review_id'])
        self.assertFalse(self.app.busy)
        self.assertFalse(self.fixture.plan.backup_root.exists())

    def test_launch_config_change_after_review_rejected(self):
        review=self.app.review(self.data)
        path=self.fixture.cfg/'localconfig.vdf'
        path.write_bytes(path.read_bytes().replace(b'PROTON_LOG=1',b'PROTON_LOG=0'))
        with self.assertRaisesRegex(core.SetupError,'changed'):
            self.app.start(review['review_id'])

    def test_http_auth_origin_and_host_before_mutations(self):
        import http.client
        import threading
        server=web.Server(self.app)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            def request(headers):
                connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
                connection.request('POST','/api/review',json.dumps(self.data),headers)
                response=connection.getresponse();status=response.status;response.read();connection.close();return status
            headers={'Content-Type':'application/json'}
            self.assertEqual(request(headers),403)
            headers['Authorization']='Bearer '+server.token
            headers['Origin']='https://unrelated.example'
            self.assertEqual(request(headers),403)
            headers['Origin']=server.origin;headers['Host']='unrelated.example'
            self.assertEqual(request(headers),403)
            headers['Host']=server.origin.removeprefix('http://')
            self.assertEqual(request(headers),200)
            self.assertFalse(self.app.state_dir.exists())
            self.assertFalse(self.profile.backup.exists())
        finally:
            server.shutdown();server.server_close();thread.join()

    def test_busy_and_replayed_start_rejected(self):
        review=self.app.review(self.data)
        with patch('web.threading.Thread') as thread:
            self.app.start(review['review_id'])
            self.assertTrue(self.app.busy)
            with self.assertRaisesRegex(core.SetupError,'already'):self.app.start(review['review_id'])
            thread.assert_called_once()
        self.app.busy=False
        with self.assertRaisesRegex(core.SetupError,'first'):self.app.start(review['review_id'])


class ManualProfile(TemporaryFixture):
    def make_proton(self, name):
        p=self.root/'.local/share/droiddeck-esync/dist'/name
        b=p/'files/bin-arm64';b.mkdir(parents=True)
        for name in ['wine','wineserver']:
            (b/name).write_text('#!/bin/sh\n');(b/name).chmod(0o755)
        return p

    def test_fixed_locations_ignore_other_library_and_stock_proton(self):
        known=self.make_proton(setup_profile.KNOWN_BUILD)
        self.make_proton('newer-build')
        p=setup_profile.load_profile(self.root, self.root)
        self.assertEqual(p.proton,known)
        self.assertEqual(p.steam,self.root/'.local/share/Steam')
        self.assertEqual(p.game_compat,p.steam/'steamapps/compatdata/2552430')
        self.assertEqual(p.compat('4018651221'),p.steam/'steamapps/compatdata/4018651221')
        self.assertEqual(p.game,self.root/'Games/Windows/steamapps/common'/setup_profile.GAME_FOLDER)

    def test_unique_esync_after_update_and_no_guess_between_multiple(self):
        only=self.make_proton('replacement')
        self.assertEqual(setup_profile.load_profile(self.root,self.root).require_proton(),only)
        self.make_proton('another')
        with self.assertRaisesRegex(core.SetupError,'No unique'):
            setup_profile.load_profile(self.root,self.root).require_proton()

    def test_existing_config_overrides_defaults_without_execution(self):
        p=self.make_proton('configured')
        config=self.root/'config.env'
        config.write_text('KH_APPID=2552430\nKH_STEAM_ROOT="$HOME/custom Steam"\nKH_COMPATDATA="$KH_STEAM_ROOT/steamapps/compatdata/$KH_APPID"\nKH_PROTON_ROOT="'+str(p)+'"\nKH_REGISTRY_BAT=""\n')
        result=setup_profile.load_profile(self.root,self.root)
        self.assertEqual(result.steam,self.root/'custom Steam')
        self.assertEqual(result.game_compat,result.steam/'steamapps/compatdata/2552430')
        self.assertEqual(result.require_proton(),p)
        config.write_text('KH_PROTON_ROOT="$(touch '+str(self.root/'executed')+')"\n')
        with self.assertRaises(core.SetupError):setup_profile.load_profile(self.root,self.root)
        self.assertFalse((self.root/'executed').exists())

    def test_missing_configured_build_never_falls_back(self):
        self.make_proton(setup_profile.KNOWN_BUILD)
        (self.root/'config.env').write_text('KH_PROTON_ROOT="/missing/proton"\n')
        with self.assertRaisesRegex(core.SetupError,'config.env'):
            setup_profile.load_profile(self.root,self.root).require_proton()

    def test_missing_default_prefix_does_not_use_other_library(self):
        self.make_proton(setup_profile.KNOWN_BUILD)
        other=self.root/'Games/Windows/steamapps/compatdata/2552430/pfx'
        (other/'drive_c').mkdir(parents=True);(other/'system.reg').touch()
        profile=setup_profile.load_profile(self.root,self.root)
        with patch('terminal.load_profile',return_value=profile), patch('terminal.accounts',return_value=['123']), patch('builtins.input',side_effect=['','','','','','']), patch('builtins.print'):
            with self.assertRaisesRegex(core.SetupError,'expected location'):
                terminal.build_plan(self.root)
        self.assertFalse(profile.game_compat.exists())


class Startup(TemporaryFixture):
    def test_missing_tk_starts_browser_without_package_manager(self):
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
        env=dict(os.environ,HOME=str(self.root),PATH=str(bin_dir)+':'+os.environ['PATH'],CALLS=str(calls))
        result=subprocess.run(['bash',str(ROOT/'linux-setup/start-setup.sh')],env=env,input='',text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(calls.read_text().splitlines(),['-c import tkinter','assistant/web.py'])

    def test_host_tools_reuse_skips_packages_and_verifies_download(self):
        import shutil
        kit=self.root/'kit';kit.mkdir()
        (kit/'common.sh').write_bytes((ROOT/'linux-setup/common.sh').read_bytes())
        # Use a fixture payload and its real checksum; no network/install commands.
        payload=b'fixture winetricks\n'
        script=(ROOT/'linux-setup/00-host-tools.sh').read_text().replace(core.WINETRICKS_SHA256,core.digest(payload))
        (kit/'00-host-tools.sh').write_text(script)
        bin_dir=self.root/'bin';bin_dir.mkdir()
        for name in ['dirname','mkdir','mktemp','sha256sum','chmod','mv','rm','uname']:
            (bin_dir/name).symlink_to(shutil.which(name))
        for name in ['python3','unzip','file']:
            path=bin_dir/name;path.write_text('#!/bin/sh\nexit 0\n');path.chmod(0o755)
        local_bin=self.root/'.local/bin';local_bin.mkdir(parents=True)
        cab=local_bin/'cabextract';cab.write_text('#!/bin/sh\nexit 0\n');cab.chmod(0o755)
        curl=bin_dir/'curl'
        curl.write_text('#!/bin/sh\nwhile [ "$1" != -o ]; do shift; done\nprintf "fixture winetricks\\n" > "$2"\n');curl.chmod(0o755)
        env=dict(os.environ,HOME=str(self.root),PATH=str(bin_dir))
        result=subprocess.run(['/bin/bash',str(kit/'00-host-tools.sh'),'--install'],env=env,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('package installation skipped',result.stdout)
        self.assertEqual((kit/'tools/winetricks').read_bytes(),payload)

    def test_ambiguous_selection_has_no_silent_default(self):
        with patch('builtins.input',side_effect=['','2']) as prompt, patch('builtins.print'):
            self.assertEqual(terminal.choose('Proton',['old','new']), 'new')
        self.assertNotIn('[1]',prompt.call_args_list[0].args[0])


class FrozenEnvironment(unittest.TestCase):
    def test_external_programs_do_not_inherit_bundled_libraries(self):
        from unittest.mock import patch
        with patch('core.sys.frozen',True,create=True), patch.dict('os.environ',{'LD_LIBRARY_PATH':'/bundle/lib','LD_LIBRARY_PATH_ORIG':'/host/lib','TCL_LIBRARY':'/bundle/tcl','TK_LIBRARY':'/bundle/tk'}):
            env=core.host_env()
            self.assertEqual(env['LD_LIBRARY_PATH'],'/host/lib')
            self.assertNotIn('TCL_LIBRARY',env)
            self.assertNotIn('TK_LIBRARY',env)
        with patch('core.sys.frozen',True,create=True), patch.dict('os.environ',{'LD_LIBRARY_PATH':'/bundle/lib'},clear=True):
            self.assertNotIn('LD_LIBRARY_PATH',core.host_env())


if __name__=='__main__':unittest.main()
