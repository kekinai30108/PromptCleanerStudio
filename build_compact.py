"""Build a Windows x64 one-file distribution with bundled Tcl/Tk and DnD."""
from __future__ import annotations
import platform
import subprocess
import sys
from pathlib import Path


def main() -> None:
    if sys.platform != 'win32' or platform.architecture()[0] != '64bit':
        raise SystemExit('Build on Windows x64.')
    if sys.version_info[:2] != (3, 12): raise SystemExit('Python 3.12 is required.')
    root = Path(__file__).resolve().parent
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--windowed',
                    '--name', 'PromptCleanerStudio', '--distpath', str(root/'release_compact'),
                    '--icon', str(root/'assets/PromptCleanerStudio.ico'),
                    '--add-data', f'{root / "assets"};assets',
                    '--exclude-module', 'numpy', '--exclude-module', 'pandas', '--exclude-module', 'matplotlib',
                    '--exclude-module', 'pytest', '--exclude-module', 'IPython', str(root/'app.py')], cwd=root, check=True)
    print(root/'release_compact/PromptCleanerStudio.exe')


if __name__ == '__main__': main()
