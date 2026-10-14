"""Rootless Linux helper installation tests, with local package/network fixtures."""
import hashlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'linux-setup/assistant'))
import host_tools as ht
from core import SetupError


class Helpers(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='helpers ; ')
        self.addCleanup(self.temp.cleanup)
        self.home=Path(self.temp.name)
        self.logs=[]

    def archive(self,path,entries):
        with tarfile.open(path,'w:xz') as out:
            for name,data in entries.items():
                info=tarfile.TarInfo(name);info.mode=0o755
                if isinstance(data,tuple):
                    info.type=tarfile.SYMTYPE;info.linkname=data[0];out.addfile(info)
                else:
                    info.size=len(data);out.addfile(info,io.BytesIO(data))

    def record(self):
        return dict(name='cabextract',sha256='1'*64,url=ht.MIRRORS[0]+'/aarch64/extra/cabextract-1-aarch64.pkg.tar.xz')

    def test_missing_helper_installed_without_root_and_reused(self):
        env={'HOME':str(self.home),'PATH':'/nonexistent'}
        calls=[]
        def fetch(url,dest,checksum):
            calls.append((url,checksum))
            self.archive(dest,{'usr/bin/cabextract':b'#!/bin/sh\necho "cabextract version 1.11"\n',
                               'usr/share/licenses/cabextract/COPYING':b'fixture license'})
        with patch.dict(os.environ,env),patch('host_tools.platform.machine',return_value='aarch64'),patch('host_tools.resolve_packages',return_value=[self.record()]),patch('host_tools.download',side_effect=fetch):
            self.assertFalse(ht.working('cabextract'))
            ht.install_local(['cabextract'],self.logs.append)
            self.assertTrue(ht.working('cabextract'))
            self.assertEqual(ht.missing_tools(),['curl','unzip','file'])
            result=subprocess.run([str(self.home/'.local/bin/cabextract'),'--version'],capture_output=True,text=True)
            self.assertEqual(result.returncode,0)
            self.assertIn('1.11',result.stdout)
            self.assertEqual(os.environ['PATH'],'/nonexistent')
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0][1],'1'*64)
        self.assertTrue(list((self.home/'.local/share/panacea-arm/host-tools').glob('install-*/packages.json')))

    def test_all_working_skips_download_and_install(self):
        with patch('host_tools.working',return_value=True),patch('host_tools.install_local') as install:
            ht.prepare(self.logs.append)
        install.assert_not_called()

    def test_failed_probe_does_not_replace_existing_helper(self):
        dest=self.home/'.local/bin/cabextract';dest.parent.mkdir(parents=True);dest.write_bytes(b'old helper')
        def fetch(url,path,checksum):self.archive(path,{'usr/bin/cabextract':b'#!/bin/sh\nexit 7\n'})
        with patch.dict(os.environ,HOME=str(self.home)),patch('host_tools.platform.machine',return_value='aarch64'),patch('host_tools.resolve_packages',return_value=[self.record()]),patch('host_tools.download',side_effect=fetch):
            with self.assertRaisesRegex(SetupError,'does not run'):
                ht.install_local(['cabextract'],self.logs.append)
        self.assertEqual(dest.read_bytes(),b'old helper')
        self.assertEqual(list((self.home/'.local/share/panacea-arm/host-tools').iterdir()),[])

    def test_package_paths_and_links_cannot_escape(self):
        for entries in [{'../escape':b'x'},{'/etc/escape':b'x'},{'usr/lib/escape':('../../../../escape',)},
                        {'usr/lib/escape':('/etc/passwd',)}]:
            with self.subTest(entries=entries),tempfile.TemporaryDirectory(dir=self.home) as tmp:
                root=Path(tmp)/'root';root.mkdir();archive=Path(tmp)/'pkg.tar.xz';self.archive(archive,entries)
                with self.assertRaises(SetupError):ht.safe_unpack(archive,root)
        self.assertFalse((self.home/'escape').exists())

    def test_unpack_skips_scripts_and_preserves_relative_libraries(self):
        root=self.home/'root';root.mkdir();archive=self.home/'pkg.tar.xz'
        self.archive(archive,{'.INSTALL':b'exit 99','etc/test':b'ignore',
                              'usr/lib/libfixture.so.1':b'lib','usr/lib/libfixture.so':('libfixture.so.1',)})
        ht.safe_unpack(archive,root)
        self.assertFalse((root/'.INSTALL').exists());self.assertFalse((root/'etc').exists())
        self.assertEqual((root/'usr/lib/libfixture.so').read_bytes(),b'lib')

    def test_metadata_rejects_wrong_arch_missing_hash_and_other_hosts(self):
        r=self.record();valid='|'.join([r['name'],'aarch64',r['sha256'],r['url']])
        self.assertEqual(ht.package_records(valid),[r])
        for bad in [valid.replace('|aarch64|','|x86_64|'),valid.replace('1'*64,'bad'),valid.replace('https://','http://'),valid.replace('ca.us.mirror.archlinuxarm.org','other.invalid')]:
            with self.assertRaises(SetupError):ht.package_records(bad)

    def test_download_hash_failure_removes_payload(self):
        dest=self.home/'download'
        opener=unittest.mock.Mock();opener.open.return_value=io.BytesIO(b'corrupt')
        with patch('host_tools.urllib.request.build_opener',return_value=opener):
            with self.assertRaisesRegex(SetupError,'checksum mismatch'):
                ht.download('https://example.invalid/file',dest,'0'*64)
        self.assertFalse(dest.exists())

    def test_resolution_uses_only_print_and_private_databases(self):
        rec=self.record();out='|'.join([rec['name'],'aarch64',rec['sha256'],rec['url']])
        work=self.home/'work';work.mkdir()
        with patch('host_tools.shutil.which',return_value='/usr/bin/pacman'),patch('host_tools.download') as dl,patch('host_tools.subprocess.run',return_value=subprocess.CompletedProcess([],0,out,'')) as run:
            records=ht.resolve_packages(['cabextract'],work,self.logs.append)
        self.assertEqual(records,[rec]);self.assertEqual(dl.call_count,2)
        args=run.call_args.args[0]
        self.assertIn('-Sp',args);self.assertNotIn('-S',args);self.assertNotIn('sudo',args)
        self.assertEqual(args[args.index('--dbpath')+1],str(work/'db'))

    def test_optional_protontricks_bootstraps_isolated_pip_without_sudo(self):
        import json
        folder=self.home/'venv'
        record={'filename':'pip-26.2.1-py3-none-any.whl',
                'url':'https://files.pythonhosted.org/packages/pip.whl',
                'digests':{'sha256':'2'*64}}
        def create(path):path.mkdir()
        def fetch(url,dest,checksum=None):
            dest.write_text(json.dumps({'urls':[record]}) if dest.name=='pip.json' else 'wheel fixture')
        with patch('host_tools.venv.EnvBuilder') as builder,patch('host_tools.download',side_effect=fetch) as dl,patch('host_tools.subprocess.run',return_value=subprocess.CompletedProcess([],0)) as run:
            builder.return_value.create.side_effect=create
            ht.optional_protontricks(folder)
        builder.assert_called_once_with(with_pip=False)
        self.assertEqual(dl.call_args_list[1].args[2],'2'*64)
        commands=[c.args[0] for c in run.call_args_list]
        self.assertEqual(len(commands),2)
        self.assertTrue(all(c[0]==str(folder/'bin/python') for c in commands))
        self.assertIn('protontricks==1.15.0',commands[1])
        self.assertNotIn('sudo',' '.join(' '.join(c) for c in commands))


if __name__=='__main__':unittest.main()
