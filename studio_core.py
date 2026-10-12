"""HTML APK Studio 0.4: importación segura, gestión de proyectos y generación Android.

No requiere Tkinter para las operaciones CLI ni para ejecutar las pruebas.
"""
from __future__ import annotations

import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import uuid
import zipfile
from urllib.parse import unquote, urlsplit
from xml.sax.saxutils import escape as xml_escape

ROOT = Path(__file__).resolve().parent
TEMPLATE = ROOT / 'android-template'
VERSION = '0.5.0'
MAX_BYTES = 250_000_000
MAX_FILES = 5000
MAX_RATIO = 200
MAX_ICON_BYTES = 5_000_000
ANDROID_PACKAGE = re.compile(r'[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+')
BAD_WIN = re.compile(r'^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$', re.I)


def data_dir() -> Path:
    override = os.environ.get('HTMLAPK_STUDIO_HOME')
    if override:
        return Path(override).expanduser().resolve()
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local') / 'HTMLAPKStudio'
    return Path.home() / '.html-apk-studio'


def project_dir(project_id: str) -> Path:
    if not re.fullmatch(r'[0-9a-f]{32}', project_id):
        raise ValueError('Identificador de proyecto inválido')
    return data_dir() / 'projects' / project_id


def _safe_parts(name: str) -> tuple[str, ...]:
    name = unicodedata.normalize('NFC', name.replace('\\', '/'))
    if not name or name.startswith('/') or '\x00' in name or ':' in name:
        raise ValueError(f'Ruta insegura: {name!r}')
    parts = tuple(name.split('/'))
    if any(not p or p in ('.', '..') or p.endswith((' ', '.')) or BAD_WIN.fullmatch(p) for p in parts):
        raise ValueError(f'Nombre no compatible con Windows: {name!r}')
    if any(any(ord(c) < 32 or c in '<>"|?*' for c in p) for p in parts):
        raise ValueError(f'Nombre de archivo inválido: {name!r}')
    if len(name) > 1000 or any(len(p) > 255 for p in parts):
        raise ValueError('Ruta excesivamente larga')
    return parts


def safe_unpack(archive: str | Path, destination: str | Path) -> None:
    """Valida todo el ZIP antes de extraer y bloquea traversal, enlaces y colisiones Windows."""
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        members = z.infolist()
        if len(members) > MAX_FILES or sum(m.file_size for m in members) > MAX_BYTES:
            raise ValueError('ZIP supera límites de tamaño o archivos')
        seen = set()
        for m in members:
            name = m.filename.replace('\\', '/').rstrip('/')
            parts = _safe_parts(name)
            key = '/'.join(parts).casefold()
            if key in seen:
                raise ValueError(f'ZIP contiene rutas duplicadas: {name}')
            seen.add(key)
            mode = (m.external_attr >> 16) & 0o170000
            if mode not in (0, 0o100000, 0o040000):
                raise ValueError('ZIP contiene enlace simbólico o archivo especial')
            if m.file_size > 1_000_000 and m.file_size > MAX_RATIO * max(1, m.compress_size):
                raise ValueError('ZIP con compresión sospechosa')
            target = destination.joinpath(*parts).resolve()
            if not target.is_relative_to(destination):
                raise ValueError('ZIP intenta escapar del destino')
        # Un archivo no puede ser también el directorio padre de otro miembro.
        files = {'/'.join(_safe_parts(m.filename.replace('\\', '/').rstrip('/'))).casefold()
                 for m in members if not m.is_dir()}
        for name in seen:
            segments = name.split('/')
            if any('/'.join(segments[:i]) in files for i in range(1, len(segments))):
                raise ValueError('ZIP contiene conflicto entre archivo y carpeta')
        for m in members:
            target = destination.joinpath(*_safe_parts(m.filename.replace('\\', '/').rstrip('/')))
            if m.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(m) as inp, target.open('xb') as out:
                    shutil.copyfileobj(inp, out, length=1024 * 1024)


def safe_copy_tree(source: str | Path, target: str | Path) -> None:
    source = Path(source).resolve()
    target = Path(target).resolve()
    if target == source or target.is_relative_to(source):
        raise ValueError('El destino no puede estar dentro de la carpeta origen')
    if not source.is_dir():
        raise ValueError('La carpeta de origen no existe')
    paths = list(source.rglob('*'))
    if len(paths) > MAX_FILES * 3:
        raise ValueError('Demasiadas entradas en la carpeta')
    files, total, seen = [], 0, set()
    for path in paths:
        if path.is_symlink():
            raise ValueError('No se permiten enlaces simbólicos')
        relative = path.relative_to(source)
        parts = _safe_parts(relative.as_posix())
        key = '/'.join(parts).casefold()
        if key in seen:
            raise ValueError('Hay nombres incompatibles con Windows por mayúsculas/minúsculas')
        seen.add(key)
        if path.is_file():
            total += path.stat().st_size
            files.append((path, parts))
            if len(files) > MAX_FILES or total > MAX_BYTES:
                raise ValueError('Proyecto supera límites de tamaño o archivos')
        elif not path.is_dir():
            raise ValueError('El proyecto contiene archivos especiales')
    target.mkdir(parents=True, exist_ok=True)
    for path, parts in files:
        dest = target.joinpath(*parts)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)


def stage_web(source: str | Path, target: str | Path) -> None:
    """Copia un HTML aislado o proyecto completo. Nunca modifica el origen."""
    source, target = Path(source).expanduser(), Path(target)
    if not source.exists():
        raise ValueError('El proyecto de origen no existe')
    target.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        safe_copy_tree(source, target)
    elif source.suffix.lower() == '.zip':
        safe_unpack(source, target)
    elif source.suffix.lower() in ('.html', '.htm'):
        if source.is_symlink() or not source.is_file():
            raise ValueError('HTML debe ser un archivo normal, no un enlace')
        if source.stat().st_size > MAX_BYTES:
            raise ValueError('HTML supera el tamaño permitido')
        if source.resolve() == (target / 'index.html').resolve():
            raise ValueError('El origen y destino no pueden ser iguales')
        shutil.copy2(source, target / 'index.html')
    else:
        raise ValueError('Selecciona un archivo HTML, ZIP o carpeta')
    if not (target / 'index.html').is_file():
        matches = [p for p in target.rglob('*') if p.is_file() and p.name.lower() == 'index.html']
        if len(matches) != 1:
            raise ValueError('Se requiere un único index.html en la raíz o una sola subcarpeta')
        nested = matches[0].parent
        if nested == target:
            matches[0].rename(target / 'index.html')
        else:
            for p in nested.iterdir():
                if (target / p.name).exists():
                    raise ValueError('Conflicto al normalizar index.html')
            for p in list(nested.iterdir()):
                shutil.move(str(p), str(target / p.name))
    if not (target / 'index.html').is_file():
        raise ValueError('No se encontró index.html')


class _HTMLRefs(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.refs: list[str] = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for key in ('src', 'href', 'poster'):
            if attrs.get(key):
                self.refs.append(attrs[key])


def analyze_web(folder: str | Path) -> dict:
    folder = Path(folder)
    files = [p for p in folder.rglob('*') if p.is_file()]
    if not (folder / 'index.html').is_file():
        raise ValueError('Falta index.html')
    warnings = []
    index = (folder / 'index.html').read_text(encoding='utf-8-sig', errors='replace')
    parser = _HTMLRefs()
    parser.feed(index)
    for ref in parser.refs:
        if ref.startswith(('#', 'data:', 'blob:', 'mailto:', 'tel:', 'javascript:')):
            continue
        parsed = urlsplit(ref)
        if parsed.scheme in ('http', 'https') or ref.startswith('//'):
            warnings.append('Recurso remoto (requiere Internet): ' + ref[:100])
            continue
        if parsed.scheme:
            warnings.append('Esquema no compatible: ' + ref[:100])
            continue
        raw = unquote(parsed.path).replace('\\', '/')
        parts = PurePosixPath(raw.lstrip('/')).parts
        if '..' in parts:
            warnings.append('Referencia fuera de la carpeta: ' + ref[:100])
            continue
        if raw:
            candidate = folder.joinpath(*parts)
            if not candidate.is_file() and not candidate.is_dir():
                warnings.append('No se encontró el recurso: ' + ref[:100])
    if 'serviceWorker.register' in index or 'navigator.serviceWorker' in index:
        warnings.append('Service workers: compatibilidad no garantizada en WebView')
    if '<base ' in index.lower():
        warnings.append('La etiqueta <base> puede alterar rutas locales')
    return {'files': len(files), 'bytes': sum(p.stat().st_size for p in files), 'warnings': list(dict.fromkeys(warnings))[:30]}


def validate_project(source: str | Path) -> dict:
    with tempfile.TemporaryDirectory(prefix='htmlapk_validate_') as td:
        root = Path(td) / 'web'
        stage_web(source, root)
        return analyze_web(root)


def atomic_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp-' + uuid.uuid4().hex)
    try:
        temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def default_config(source: str | Path) -> dict:
    source = Path(source)
    base = source.stem if source.is_file() else source.name
    display = re.sub(r'[_-]+', ' ', base).strip()[:60] or 'Mi aplicación'
    slug = re.sub(r'[^a-z0-9]+', '', base.lower())[:25] or 'demo'
    if not slug[0].isalpha():
        slug = 'app' + slug
    return {'name': display, 'package': f'com.misapps.{slug}', 'orientation': 'unspecified',
            'internet': False, 'icon': '', 'version_code': 1, 'version_name': '1.0', 'mode': 'debug'}


def import_project(source: str | Path) -> dict:
    source = Path(source).expanduser().resolve()
    root = data_dir() / 'projects'
    root.mkdir(parents=True, exist_ok=True)
    pid = uuid.uuid4().hex
    staging = root / ('.pending-' + pid)
    final = project_dir(pid)
    try:
        web = staging / 'web'
        stage_web(source, web)
        report = analyze_web(web)
        info = {'id': pid, 'source': str(source), 'created': time.strftime('%Y-%m-%d %H:%M:%S'),
                'config': default_config(source)}
        atomic_json(staging / 'project.json', info)
        staging.rename(final)
        return {'project': info, 'report': report}
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def load_project(pid: str) -> dict:
    root = project_dir(pid)
    info = read_json(root / 'project.json', None)
    if not isinstance(info, dict) or info.get('id') != pid or not (root / 'web/index.html').is_file():
        raise ValueError('Proyecto guardado inválido')
    return info


def save_project(info: dict) -> None:
    pid = info['id']
    if not (project_dir(pid) / 'web/index.html').is_file():
        raise ValueError('No existe el proyecto')
    validate_config(**{k: info['config'][k] for k in ('name','package','orientation','internet','version_code','version_name')})
    atomic_json(project_dir(pid) / 'project.json', info)


def list_projects() -> list[dict]:
    root = data_dir() / 'projects'
    if not root.is_dir():
        return []
    projects = []
    for p in root.iterdir():
        if p.is_dir() and re.fullmatch('[0-9a-f]{32}', p.name):
            try:
                projects.append(load_project(p.name))
            except (OSError, ValueError):
                continue
    return sorted(projects, key=lambda x: x.get('created', ''), reverse=True)


def validate_config(name: str, package: str, orientation='unspecified', internet=False,
                    version_code=1, version_name='1.0') -> None:
    if not isinstance(name, str) or not name.strip() or len(name) > 60 or any(ord(c) < 32 for c in name):
        raise ValueError('Nombre obligatorio, máximo 60 caracteres, sin saltos de línea')
    if not isinstance(package, str) or not ANDROID_PACKAGE.fullmatch(package):
        raise ValueError('Identificador Android inválido: com.ejemplo.miapp')
    if orientation not in ('unspecified', 'portrait', 'landscape'):
        raise ValueError('Orientación no válida')
    if not isinstance(internet, bool):
        raise ValueError('Permiso de Internet inválido')
    if type(version_code) is not int or not 1 <= version_code <= 2_100_000_000:
        raise ValueError('versionCode debe ser entero positivo')
    if not re.fullmatch(r'[0-9A-Za-z._-]{1,40}', version_name):
        raise ValueError('Versión de texto inválida')


def _png_size(path: Path) -> tuple[int, int]:
    if not path.is_file() or path.suffix.lower() != '.png' or path.stat().st_size > MAX_ICON_BYTES:
        raise ValueError('El ícono debe ser PNG y no superar 5 MB')
    with path.open('rb') as f:
        header = f.read(24)
    if len(header) < 24 or header[:8] != b'\x89PNG\r\n\x1a\n' or header[12:16] != b'IHDR':
        raise ValueError('Ícono PNG inválido')
    width = int.from_bytes(header[16:20], 'big')
    height = int.from_bytes(header[20:24], 'big')
    if not 32 <= width <= 4096 or not 32 <= height <= 4096:
        raise ValueError('Ícono fuera de dimensiones permitidas')
    return width, height


def install_icon(icon: str | Path, project: Path) -> None:
    icon = Path(icon)
    _png_size(icon)
    res = project / 'app/src/main/res'
    try:
        from PIL import Image
        with Image.open(icon) as img:
            img.verify()
        with Image.open(icon) as img:
            rgba = img.convert('RGBA')
            for density, size in [('mdpi',48),('hdpi',72),('xhdpi',96),('xxhdpi',144),('xxxhdpi',192)]:
                folder = res / ('mipmap-' + density)
                folder.mkdir(parents=True, exist_ok=True)
                rgba.resize((size,size), Image.Resampling.LANCZOS).save(folder / 'ic_launcher.png')
        ref = '@mipmap/ic_launcher'
    except ImportError:
        folder = res / 'drawable-nodpi'
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copy2(icon, folder / 'ic_launcher.png')
        ref = '@drawable/ic_launcher'
    manifest = project / 'app/src/main/AndroidManifest.xml'
    text = manifest.read_text(encoding='utf-8')
    manifest.write_text(text.replace('ICON_TOKEN', ref), encoding='utf-8')


def prepare_android(source: str | Path, dest: str | Path, *, name: str, package: str,
                    orientation='unspecified', internet=False, icon=None,
                    version_code=1, version_name='1.0') -> dict:
    """Crea proyecto Gradle listo para compilar, sin afirmar que ya exista un APK."""
    validate_config(name, package, orientation, internet, version_code, version_name)
    dest = Path(dest).resolve()
    if dest.exists():
        raise FileExistsError(f'La carpeta destino ya existe: {dest}')
    if not TEMPLATE.is_dir():
        raise FileNotFoundError('Falta android-template')
    shutil.copytree(TEMPLATE, dest, ignore=shutil.ignore_patterns('build', '.gradle', '__pycache__'))
    try:
        assets = dest / 'app/src/main/assets'
        stage_web(source, assets)
        report = analyze_web(assets)
        manifest = dest / 'app/src/main/AndroidManifest.xml'
        content = manifest.read_text(encoding='utf-8')
        content = content.replace('APP_NAME_TOKEN', xml_escape(name, {'"':'&quot;', "'":'&apos;'}))
        content = content.replace('ORIENTATION_TOKEN', orientation)
        content = content.replace('INTERNET_PERMISSION_TOKEN', '<uses-permission android:name="android.permission.INTERNET" />' if internet else '')
        if icon:
            install_icon(icon, dest)
            content = manifest.read_text(encoding='utf-8')
            content = content.replace('APP_NAME_TOKEN', xml_escape(name, {'"':'&quot;', "'":'&apos;'})).replace('ORIENTATION_TOKEN', orientation)
            content = content.replace('INTERNET_PERMISSION_TOKEN', '<uses-permission android:name="android.permission.INTERNET" />' if internet else '')
        else:
            content = content.replace('ICON_TOKEN', '@drawable/studio_icon')
        manifest.write_text(content, encoding='utf-8')
        gradle = dest / 'app/build.gradle'
        text = gradle.read_text(encoding='utf-8')
        for token, value in [('PACKAGE_TOKEN', package), ('VERSION_CODE_TOKEN', str(version_code)),
                             ('VERSION_NAME_TOKEN', version_name)]:
            text = text.replace(token, value)
        gradle.write_text(text, encoding='utf-8')
        return report
    except Exception:
        shutil.rmtree(dest, ignore_errors=True)
        raise


def find_gradle() -> str | None:
    exe = 'gradle.bat' if os.name == 'nt' else 'gradle'
    candidates = [ROOT / 'tools' / 'gradle-8.9' / 'bin' / exe,
                  ROOT / 'gradle' / 'bin' / exe,
                  ROOT.parent / 'HTML-APK-Studio-v0.5' / 'tools' / 'gradle-8.9' / 'bin' / exe,
                  ROOT.parent / 'HTML-APK-Studio' / 'HTML-APK-Studio-v0.5' / 'tools' / 'gradle-8.9' / 'bin' / exe]
    if os.environ.get('GRADLE_HOME'):
        candidates.append(Path(os.environ['GRADLE_HOME']) / 'bin' / exe)
    for p in candidates:
        if p.is_file():
            return str(p)
    return shutil.which('gradle')


def find_sdk() -> Path | None:
    for raw in [os.environ.get('ANDROID_HOME'), os.environ.get('ANDROID_SDK_ROOT'),
                str(Path(os.environ.get('LOCALAPPDATA', '')) / 'Android' / 'Sdk') if os.name == 'nt' else None]:
        if raw and Path(raw).is_dir():
            return Path(raw)
    return None


def find_build_tool(name: str, env: dict | None = None) -> str | None:
    sdk = find_sdk()
    if not sdk or not (sdk / 'build-tools').is_dir():
        return None
    exe = name + ('.bat' if os.name == 'nt' and name == 'apksigner' else '.exe' if os.name == 'nt' else '')
    folders = sorted((p for p in (sdk / 'build-tools').iterdir() if p.is_dir()),
                     key=lambda p: tuple(int(n) for n in re.findall(r'\d+', p.name)), reverse=True)
    for folder in folders:
        candidate = folder / exe
        if candidate.is_file():
            return str(candidate)
    return None


def _ensure_java_env(env: dict) -> dict:
    if os.name != 'nt':
        return env
    for jdk_path in [
        r'C:\Program Files\Android\openjdk\jdk-21.0.8',
        r'C:\Program Files\Java\jdk-21',
        r'C:\Program Files\Eclipse Adoptium\jdk-21',
    ]:
        java_exe = Path(jdk_path) / 'bin' / 'java.exe'
        if java_exe.is_file():
            env['JAVA_HOME'] = jdk_path
            env['PATH'] = str(Path(jdk_path) / 'bin') + os.pathsep + env.get('PATH', '')
            break
    if not env.get('ANDROID_HOME'):
        sdk = find_sdk()
        if sdk:
            env['ANDROID_HOME'] = str(sdk)
    return env


def find_java() -> tuple[str | None, str | None]:
    """Busca el ejecutable de Java y el JAVA_HOME correspondiente."""
    jh = os.environ.get('JAVA_HOME')
    if jh:
        exe = 'java.exe' if os.name == 'nt' else 'java'
        p = Path(jh) / 'bin' / exe
        if p.is_file(): return str(p), str(jh)
    if os.name == 'nt':
        for base_str in [r"C:\Program Files\Android\openjdk\jdk-21.0.8",
                         r"C:\Program Files\Android\Android Studio\jbr",
                         r"C:\Program Files\Java", r"C:\Program Files\Eclipse Adoptium",
                         r"C:\Program Files\Microsoft", r"C:\Program Files\Temurin",
                         str(Path(os.environ.get('LOCALAPPDATA', '')).joinpath('Programs', 'Android Studio', 'jbr'))]:
            base = Path(base_str)
            if not base.is_dir(): continue
            p = base / 'bin' / 'java.exe'
            if p.is_file(): return str(p), str(base)
            try:
                for sub in base.iterdir():
                    if sub.is_dir() and (sub / 'bin' / 'java.exe').is_file():
                        return str(sub / 'bin' / 'java.exe'), str(sub)
            except OSError: continue
    j = shutil.which('java')
    if j:
        try:
            jh_inf = Path(j).parent.parent
            if (jh_inf / 'bin' / ('javac.exe' if os.name == 'nt' else 'javac')).is_file():
                return str(j), str(jh_inf)
        except Exception: pass
        return str(j), None
    return None, None


def diagnostic_report() -> dict:
    java_exe, java_home = find_java()
    java = java_exe
    javac = shutil.which('javac') or (str(Path(java_exe).parent / 'javac.exe') if java_exe else None)
    major = None
    if java:
        try:
            output = subprocess.run([java, '-version'], capture_output=True, text=True, timeout=6)
            match = re.search(r'version [\"\'](\d+)', output.stderr + output.stdout)
            if match:
                major = int(match.group(1))
        except (OSError, subprocess.TimeoutExpired):
            pass
    java_compatible = bool(javac and major and 17 <= major <= 22)
    gradle = find_gradle()
    sdk = find_sdk()
    installed_api = bool(sdk and (sdk / 'platforms/android-35/android.jar').is_file())
    build_tools = bool(sdk and (sdk / 'build-tools').is_dir() and any((p / ('aapt2.exe' if os.name == 'nt' else 'aapt2')).exists() for p in (sdk / 'build-tools').iterdir()))
    return {'python': sys.version.split()[0], 'java': java, 'javac': javac,
            'java_major': major, 'java_compatible': java_compatible, 'gradle': gradle,
            'sdk': str(sdk) if sdk else None, 'api35': installed_api,
            'build_tools': build_tools, 'apksigner': find_build_tool('apksigner'),
            'ready_to_try': bool(java_compatible and gradle and installed_api and build_tools),
            'note': 'El diagnóstico no prueba que Gradle compile ni que el APK se instale.'}


def verify_apk(apk: str | Path) -> dict:
    """Comprobación estructural mínima; NO equivale a instalar/ejecutar en Android."""
    apk = Path(apk)
    if not apk.is_file() or apk.stat().st_size == 0 or not zipfile.is_zipfile(apk):
        raise ValueError('Gradle no produjo un archivo APK ZIP válido')
    with zipfile.ZipFile(apk) as z:
        names = set(z.namelist())
        required = {'AndroidManifest.xml', 'resources.arsc'}
        if not required.issubset(names) or not any(n.startswith('classes') and n.endswith('.dex') for n in names):
            raise ValueError('El archivo no tiene la estructura mínima de un APK Android')
    return {'size': apk.stat().st_size, 'sha256': hashlib.sha256(apk.read_bytes()).hexdigest()}


def build(source: str | Path, name: str, package: str, log=print, *, orientation='unspecified',
          internet=False, icon=None, version_code=1, version_name='1.0',
          mode='debug', output=None, keystore=None, key_alias=None,
          store_password=None, key_password=None, gradle_command=None) -> Path:
    if mode not in ('debug', 'release'):
        raise ValueError('Modo debe ser debug o release')
    gradle = gradle_command or find_gradle()
    if not gradle:
        raise RuntimeError('Gradle 8.9 no encontrado. Ejecuta setup_windows.ps1 o configura GRADLE_HOME.')
    env = os.environ.copy()
    env = _ensure_java_env(env)
    if mode == 'release':
        if not all((keystore, key_alias, store_password, key_password)):
            raise ValueError('Release requiere keystore, alias y contraseñas (no se guardan)')
        if not Path(keystore).is_file():
            raise ValueError('No se encontró el almacén de claves')
        env.update({'HTMLAPK_KEYSTORE': str(Path(keystore).resolve()), 'HTMLAPK_KEY_ALIAS': key_alias,
                    'HTMLAPK_STORE_PASSWORD': store_password, 'HTMLAPK_KEY_PASSWORD': key_password})
    outdir = Path(output) if output else data_dir() / 'outputs'
    outdir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='htmlapk_build_') as tmp:
        project = Path(tmp) / 'android'
        report = prepare_android(source, project, name=name, package=package,
                                 orientation=orientation, internet=internet, icon=icon,
                                 version_code=version_code, version_name=version_name)
        for warning in report['warnings']:
            log('AVISO: ' + warning)
        log('Iniciando Gradle ' + mode + '...')
        cmd = [str(gradle), '--no-daemon', '--console=plain', 'assemble' + mode.capitalize()]
        # No usamos shell=True; las contraseñas viajan por variables de entorno, no argumentos.
        startup = None
        flags = 0
        if os.name == 'nt':
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = 0
            flags = subprocess.CREATE_NO_WINDOW
        with subprocess.Popen(cmd, cwd=project, env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, errors='replace',
                              startupinfo=startup, creationflags=flags) as proc:
            assert proc.stdout is not None
            for line in proc.stdout:
                log(line.rstrip())
            code = proc.wait()
        if code:
            raise RuntimeError(f'Gradle terminó con código {code}. Revisa el registro.')
        apk = project / f'app/build/outputs/apk/{mode}/app-{mode}.apk'
        if not apk.is_file():
            raise RuntimeError('Gradle terminó, pero no existe el APK esperado')
        details = verify_apk(apk)
        apksigner = find_build_tool('apksigner', env=env)
        if apksigner:
            checked = subprocess.run([apksigner, 'verify', '--verbose', str(apk)],
                                     capture_output=True, text=True, errors='replace', env=env)
            if checked.returncode != 0:
                raise RuntimeError('El APK no pasó la verificación de firma: ' + (checked.stderr or checked.stdout)[-1000:])
            log('Firma APK verificada con apksigner.')
        else:
            log('AVISO: apksigner no disponible; firma no verificada de forma independiente.')
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)[:35]
        unique = time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6]
        dest = outdir / f'{safe_name}-{unique}-{mode}.apk'
        shutil.copy2(apk, dest)
        history = data_dir() / 'history.json'
        records = read_json(history, [])
        if not isinstance(records, list):
            records = []
        records.insert(0, {'date': time.strftime('%Y-%m-%d %H:%M:%S'), 'name': name,
                           'package': package, 'mode': mode, 'version_code': version_code,
                           'apk': str(dest), 'sha256': details['sha256'], 'size': details['size']})
        atomic_json(history, records[:100])
        log('APK generado y validado estructuralmente: ' + str(dest))
        return dest
