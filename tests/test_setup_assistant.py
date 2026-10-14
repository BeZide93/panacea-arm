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

    def test_no_newest_proton_guess(self):
        candidates=[self.root/'older',self.root/'newer']
        self.assertIsNone(core.proton_hint(self.root,candidates))
        (self.root/'config_info').write_text(str(candidates[0])+'/files/share/wine\n')
        self.assertEqual(core.proton_hint(self.root,candidates),candidates[0])

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

    def test_runtime_skip_and_wrong_arch_record_fails(self):
        target=self.targets[0];(target.compat/'pfx/winetricks.log').write_text('dotnet8\ndotnetdesktop8\nvcrun6\nxaudio29\n')
        out='Microsoft.NETCore.App 8.0.30 [x]\nMicrosoft.WindowsDesktop.App 8.0.30 [x]\n'
        with patch('core.reports',return_value=[(0x14c,out),(0x8664,out)]):
            core.install_runtimes(target,self.plan,self.runner)
        self.assertNotIn('winetricks -q',self.log.getvalue())
        with patch('core.reports',return_value=[(0x14c,out)]):
            with self.assertRaises(core.SetupError):core.install_runtimes(target,self.plan,self.runner)


if __name__=='__main__':unittest.main()
