import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import studio_core as c


class ImportSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def _zip(self, items):
        path = self.root / 'input.zip'
        with zipfile.ZipFile(path, 'w') as z:
            for key, value in items.items():
                z.writestr(key, value)
        return path

    def test_html_only_copies_selected_file(self):
        (self.root / 'a.html').write_text('<h1>Hola</h1>')
        (self.root / 'secreto.txt').write_text('privado')
        out = self.root / 'out'
        c.stage_web(self.root / 'a.html', out)
        self.assertTrue((out / 'index.html').exists())
        self.assertFalse((out / 'secreto.txt').exists())

    def test_folder_copies_assets(self):
        src = self.root / 'source'
        (src / 'assets').mkdir(parents=True)
        (src / 'index.html').write_text('<script src="assets/app.js"></script>')
        (src / 'assets/app.js').write_text('alert(1)')
        c.stage_web(src, self.root / 'out')
        self.assertEqual(c.analyze_web(self.root / 'out')['warnings'], [])

    def test_zip_traversal(self):
        for name in ['../outside.txt', '/root.txt', 'folder/../bad.txt', 'C:/windows.txt',
                     'dir\\..\\bad.txt', 'CON.txt', 'name:stream', 'a//b']:
            with self.subTest(name=name):
                z = self._zip({name:'bad', 'index.html':'ok'})
                with self.assertRaises(ValueError):
                    c.safe_unpack(z, self.root / 'out')

    def test_case_collision_rejected(self):
        z = self._zip({'Index.html':'A', 'index.html':'B'})
        with self.assertRaises(ValueError):
            c.safe_unpack(z, self.root / 'out')

    def test_zip_file_directory_conflict(self):
        z = self._zip({'assets':'archivo', 'assets/app.js':'codigo', 'index.html':'ok'})
        with self.assertRaises(ValueError):
            c.safe_unpack(z, self.root / 'out')

    def test_html_symlink_rejected(self):
        original = self.root / 'original.html'
        original.write_text('hola')
        link = self.root / 'enlace.html'
        try:
            link.symlink_to(original)
        except OSError:
            self.skipTest('Sistema no admite enlaces simbólicos')
        with self.assertRaises(ValueError):
            c.stage_web(link, self.root / 'out')

    def test_html_same_source_destination_rejected(self):
        out = self.root / 'out'
        out.mkdir()
        html = out / 'index.html'
        html.write_text('hola')
        with self.assertRaises(ValueError):
            c.stage_web(html, out)

    def test_zip_symlink_rejected(self):
        path = self.root / 'symlink.zip'
        with zipfile.ZipFile(path,'w') as z:
            info = zipfile.ZipInfo('link')
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(info, '../elsewhere')
        with self.assertRaises(ValueError):
            c.safe_unpack(path, self.root / 'out')

    def test_compression_bomb_rejected(self):
        path = self.root / 'bomb.zip'
        with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr('index.html', 'a' * 1_500_000)
        with self.assertRaises(ValueError):
            c.safe_unpack(path, self.root / 'out')

    def test_valid_nested_zip(self):
        z = self._zip({'project/index.html':'<h1>Hola</h1>', 'project/app.js':'var x=1'})
        self.assertEqual(c.validate_project(z)['files'],2)

    def test_missing_index(self):
        z = self._zip({'app.html':'<p>sin index</p>'})
        with self.assertRaises(ValueError):
            c.validate_project(z)

    def test_missing_source(self):
        with self.assertRaises(ValueError):
            c.validate_project(self.root / 'missing.html')

    def test_symlink_in_folder_rejected(self):
        src = self.root / 'source'
        src.mkdir()
        (src / 'index.html').write_text('hola')
        try:
            (src / 'link').symlink_to(self.root)
        except OSError:
            self.skipTest('No se permiten symlinks en este entorno')
        with self.assertRaises(ValueError):
            c.stage_web(src, self.root / 'out')

    def test_source_contains_target_rejected(self):
        src = self.root / 'src'
        src.mkdir()
        (src / 'index.html').write_text('hola')
        with self.assertRaises(ValueError):
            c.safe_copy_tree(src, src / 'output')

    def test_remote_resource_warning(self):
        src = self.root / 'a.html'
        src.write_text('<script src="https://cdn.example.com/a.js"></script><link href="missing.css">')
        result = c.validate_project(src)
        self.assertEqual(len(result['warnings']),2)


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {'HTMLAPK_STUDIO_HOME':str(self.root / 'data')})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_project_roundtrip(self):
        source = self.root / 'demo.html'
        source.write_text('<h1>Original</h1>', encoding='utf-8')
        result = c.import_project(source)
        pid = result['project']['id']
        self.assertEqual(c.load_project(pid)['config']['version_code'],1)
        saved = c.project_dir(pid) / 'web/index.html'
        saved.write_text('Editado')
        self.assertEqual(source.read_text(),'<h1>Original</h1>')
        info = c.load_project(pid)
        info['config']['version_code'] = 2
        c.save_project(info)
        self.assertEqual(c.load_project(pid)['config']['version_code'],2)
        self.assertEqual(len(c.list_projects()),1)

    def test_invalid_project_id(self):
        with self.assertRaises(ValueError):
            c.project_dir('../../etc')

    def test_config_invalid(self):
        for kwargs in [dict(name='',package='com.x.app'), dict(name='App',package='no'),
                       dict(name='App',package='com.x.app',version_code=0),
                       dict(name='App',package='com.x.app',orientation='diagonal'),
                       dict(name='App',package='com.x.app',version_name='1.0\nmal')]:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    c.validate_config(**kwargs)

    def test_diagnostics_json(self):
        report = c.diagnostic_report()
        self.assertIn('api35',report)
        self.assertIn('ready_to_try',report)
        json.dumps(report)


class AndroidGenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'app.html'
        self.source.write_text('<h1>Hola</h1>')

    def test_prepares_gradle_project(self):
        dest = self.root / 'android'
        c.prepare_android(self.source, dest, name='Hola & "Amigos"', package='com.prueba.demo',
                          orientation='portrait',internet=True,version_code=7,version_name='2.3')
        manifest = (dest / 'app/src/main/AndroidManifest.xml').read_text()
        gradle = (dest / 'app/build.gradle').read_text()
        self.assertIn('Hola &amp; &quot;Amigos&quot;',manifest)
        self.assertIn('android.permission.INTERNET',manifest)
        self.assertIn('android:screenOrientation="portrait"',manifest)
        self.assertIn('versionCode 7',gradle)
        self.assertIn("applicationId 'com.prueba.demo'",gradle)
        self.assertIn("androidx.webkit:webkit:1.12.1",gradle)
        self.assertTrue((dest / 'app/src/main/assets/index.html').exists())
        ET.fromstring(manifest)

    def test_offline_manifest_no_internet(self):
        dest = self.root / 'android'
        c.prepare_android(self.source,dest,name='Offline',package='com.demo.offline')
        manifest = (dest / 'app/src/main/AndroidManifest.xml').read_text()
        self.assertNotIn('android.permission.INTERNET',manifest)
        self.assertIn('@drawable/studio_icon',manifest)
        self.assertNotIn('_TOKEN',manifest)
        ET.fromstring(manifest)

    def test_no_overwrite_existing_project(self):
        dest = self.root / 'android'
        dest.mkdir()
        with self.assertRaises(FileExistsError):
            c.prepare_android(self.source,dest,name='A',package='com.demo.a')

    def test_icon_png(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Pillow no disponible')
        icon = self.root / 'icon.png'
        Image.new('RGB',(128,128),'red').save(icon)
        dest = self.root / 'android'
        c.prepare_android(self.source,dest,name='App',package='com.demo.app',icon=icon)
        manifest = (dest / 'app/src/main/AndroidManifest.xml').read_text()
        self.assertIn('@mipmap/ic_launcher',manifest)
        self.assertTrue((dest / 'app/src/main/res/mipmap-xxxhdpi/ic_launcher.png').exists())

    def test_icon_rejects_invalid_png(self):
        icon = self.root / 'bad.png'
        icon.write_bytes(b'not a png')
        with self.assertRaises(ValueError):
            c.prepare_android(self.source,self.root / 'android',name='App',package='com.demo.app',icon=icon)
        self.assertFalse((self.root / 'android').exists())

    def test_webview_security_defaults(self):
        java = (c.TEMPLATE / 'app/src/main/java/com/htmlapk/studio/MainActivity.java').read_text()
        for marker in ('WebViewAssetLoader', 'setAllowFileAccess(false)',
                       'setAllowContentAccess(false)', 'MIXED_CONTENT_NEVER_ALLOW',
                       'setJavaScriptCanOpenWindowsAutomatically(false)', '404, "Not Found"'):
            self.assertIn(marker, java)

    def test_verify_apk_rejects_fake_zip(self):
        file = self.root / 'fake.apk'
        with zipfile.ZipFile(file,'w') as z:
            z.writestr('index.html','<h1>NO APK</h1>')
        with self.assertRaises(ValueError):
            c.verify_apk(file)

    def test_build_without_gradle_fails_clearly(self):
        with patch.object(c, 'find_gradle', return_value=None):
            with self.assertRaisesRegex(RuntimeError,'Gradle'):
                c.build(self.source,'App','com.demo.app')

    def test_build_orchestration_with_fake_gradle_not_real_apk(self):
        """Prueba el flujo Python; NO compila bytecode Android ni genera un APK instalable."""
        is_win = os.name == 'nt'
        script = self.root / ('fake_gradle.bat' if is_win else 'fake_gradle')
        if is_win:
            script.write_text('@echo off\npython -c "import pathlib, zipfile; p=pathlib.Path(\'app/build/outputs/apk/debug/app-debug.apk\'); p.parent.mkdir(parents=True,exist_ok=True); z=zipfile.ZipFile(p,\'w\'); z.writestr(\'AndroidManifest.xml\',b\'fake\'); z.writestr(\'resources.arsc\',b\'fake\'); z.writestr(\'classes.dex\',b\'fake\'); z.close()"\necho SIMULATED_GRADLE\n')
        else:
            script.write_text("#!/usr/bin/env python3\nfrom pathlib import Path\nimport zipfile\np=Path('app/build/outputs/apk/debug/app-debug.apk')\np.parent.mkdir(parents=True,exist_ok=True)\nwith zipfile.ZipFile(p,'w') as z:\n    z.writestr('AndroidManifest.xml',b'fake')\n    z.writestr('resources.arsc',b'fake')\n    z.writestr('classes.dex',b'fake')\nprint('SIMULATED_GRADLE')\n")
            script.chmod(0o755)
        logs = []
        with patch.dict(os.environ, {'HTMLAPK_STUDIO_HOME':str(self.root / 'data')}):
            with patch.object(c, 'find_build_tool', return_value=None):
                dest = c.build(self.source,'App','com.demo.app',log=logs.append,
                               gradle_command=str(script), output=self.root / 'outputs')
                self.assertTrue(dest.is_file())
                self.assertTrue(any('SIMULATED_GRADLE' in line for line in logs))
                self.assertEqual(len(c.read_json(c.data_dir() / 'history.json', [])),1)
        # El APK simulado solo pasa comprobación superficial; NO es ejecutable.

    def test_release_requires_keystore(self):
        with self.assertRaisesRegex(ValueError,'keystore'):
            c.build(self.source,'App','com.demo.app',mode='release',gradle_command='fake-gradle')


class CLITests(unittest.TestCase):
    def test_cli_help(self):
        cli = Path(__file__).resolve().parents[1] / 'cli.py'
        p = subprocess.run([sys.executable,str(cli),'--help'],capture_output=True,text=True)
        self.assertEqual(p.returncode,0)
        self.assertIn('prepare',p.stdout)

    def test_cli_validate_demo(self):
        cli = Path(__file__).resolve().parents[1] / 'cli.py'
        demo = Path(__file__).resolve().parents[1] / 'examples/demo'
        p = subprocess.run([sys.executable,str(cli),'validate',str(demo)],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(json.loads(p.stdout)['files'],1)


if __name__ == '__main__':
    unittest.main()
