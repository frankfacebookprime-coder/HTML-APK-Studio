"""CLI sin interfaz: útil para DeepSeek Harness y pruebas automáticas."""
import argparse
import json
from pathlib import Path
import tempfile
import sys
import studio_core as core


def parser():
    p = argparse.ArgumentParser(description='HTML APK Studio Professional 0.4')
    sub = p.add_subparsers(dest='action', required=True)
    sub.add_parser('doctor', help='Revisar herramientas de compilación')
    val = sub.add_parser('validate', help='Analizar un HTML, ZIP o carpeta')
    val.add_argument('source')
    prep = sub.add_parser('prepare', help='Generar proyecto Android Gradle sin compilar')
    build = sub.add_parser('build', help='Compilar APK real usando Gradle')
    for cmd in (prep, build):
        cmd.add_argument('source')
        cmd.add_argument('--name', required=True)
        cmd.add_argument('--package', required=True)
        cmd.add_argument('--orientation', choices=['unspecified','portrait','landscape'], default='unspecified')
        cmd.add_argument('--internet', action='store_true')
        cmd.add_argument('--icon')
        cmd.add_argument('--version-code', type=int, default=1)
        cmd.add_argument('--version-name', default='1.0')
    prep.add_argument('--dest', required=True)
    build.add_argument('--output')
    build.add_argument('--mode', choices=['debug','release'], default='debug')
    build.add_argument('--keystore')
    build.add_argument('--alias', dest='key_alias')
    # Contraseñas por variables de entorno, nunca en el historial de la terminal.
    sub.add_parser('projects', help='Listar proyectos importados')
    sub.add_parser('demo', help='Mostrar ruta del HTML de ejemplo')
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.action == 'doctor':
            print(json.dumps(core.diagnostic_report(), ensure_ascii=False, indent=2))
        elif args.action == 'validate':
            print(json.dumps(core.validate_project(args.source), ensure_ascii=False, indent=2))
        elif args.action == 'prepare':
            info = core.prepare_android(args.source, args.dest, name=args.name, package=args.package,
                                        orientation=args.orientation, internet=args.internet, icon=args.icon,
                                        version_code=args.version_code, version_name=args.version_name)
            print(json.dumps({'project': str(Path(args.dest).resolve()), 'report': info,
                              'apk_compiled': False}, ensure_ascii=False, indent=2))
        elif args.action == 'build':
            import os
            dest = core.build(args.source, args.name, args.package,
                              orientation=args.orientation, internet=args.internet, icon=args.icon,
                              version_code=args.version_code, version_name=args.version_name,
                              mode=args.mode, output=args.output, keystore=args.keystore,
                              key_alias=args.key_alias,
                              store_password=os.environ.get('HTMLAPK_STORE_PASSWORD'),
                              key_password=os.environ.get('HTMLAPK_KEY_PASSWORD'))
            print('APK: ' + str(dest))
        elif args.action == 'projects':
            print(json.dumps(core.list_projects(), ensure_ascii=False, indent=2))
        elif args.action == 'demo':
            print(Path(__file__).resolve().parent / 'examples' / 'demo' / 'index.html')
        return 0
    except (OSError, ValueError, RuntimeError, FileNotFoundError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
