"""Build a new Windows portable folder without downloading models or credentials.

Install requirements-build.txt in a build venv first. Output must not exist.
"""
from __future__ import annotations
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if os.name != 'nt':
        parser.error('Windows build requires Windows; cross compilation is not supported.')
    output = args.out.resolve()
    if output.exists():
        parser.error('Output already exists. Choose a new folder; nothing was overwritten.')
    output.mkdir(parents=True)
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--windowed', '--onedir',
                    '--name', 'ClearWrite', '--paths', str(ROOT / 'src'),
                    '--add-data', str(ROOT / 'src/clearwrite/web') + os.pathsep + 'clearwrite/web',
                    '--distpath', str(output / 'dist'), '--workpath', str(output / 'build'),
                    '--specpath', str(output), str(ROOT / 'scripts/desktop_entry.py')], check=True, cwd=ROOT)
    app = output / 'dist/ClearWrite'
    for name in ('index.html', 'app.css', 'app.js'):
        if not (app / '_internal/clearwrite/web' / name).is_file():
            raise RuntimeError('Packaged editor asset is missing: ' + name)
    for name in ('LICENSE', 'THIRD_PARTY_NOTICES.md', 'SECURITY.md'):
        shutil.copy2(ROOT / name, app / name)
    shutil.copytree(ROOT / 'licenses', app / 'licenses')
    shutil.copy2(ROOT / 'docs/DESKTOP.md', app / '사용설명서.md')
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if python_license.is_file():
        shutil.copy2(python_license, app / 'licenses/Python-runtime-LICENSE.txt')
    for dependency in ('pyinstaller', 'pyinstaller-hooks-contrib'):
        for item in importlib.metadata.files(dependency) or []:
            if item.name.upper() in {'COPYING.TXT', 'LICENSE', 'LICENSE.TXT'}:
                source = Path(importlib.metadata.distribution(dependency).locate_file(item))
                if source.is_file():
                    shutil.copy2(source, app / 'licenses' / (dependency + '-' + item.name))
    record = {'platform': platform.platform(), 'python': platform.python_version(),
              'architecture': platform.machine(), 'unsigned': True, 'models_bundled': False,
              'credentials_bundled': False,
              'build_packages': {name: importlib.metadata.version(name) for name in
                                 ('setuptools', 'wheel', 'pyinstaller', 'pyinstaller-hooks-contrib')}}
    (app / 'BUILD-INFO.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(str(app))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
