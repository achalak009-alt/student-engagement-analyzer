"""One-command launcher: creates a local environment, installs dependencies, runs Flask."""
from pathlib import Path
import os
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
if sys.version_info < (3, 9):
    raise SystemExit('Please install Python 3.9 or newer.')
env = ROOT / '.venv'
python = env / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
try:
    if not python.exists():
        print('First run: preparing the Python environment…', flush=True)
        venv.EnvBuilder(with_pip=True).create(env)
    installed = subprocess.run([str(python), '-c', 'import flask, openpyxl'], capture_output=True)
    if installed.returncode:
        subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(ROOT / 'requirements.txt')], check=True)
    print('\nStarting Engage Lab Analytics. Open http://127.0.0.1:5000\n', flush=True)
    subprocess.run([str(python), str(ROOT / 'app.py')], check=True)
except KeyboardInterrupt:
    print('\nServer stopped.')
except (OSError, subprocess.CalledProcessError) as error:
    print(f'Could not start: {error}\nCheck your internet connection for the first dependency install. See README.md for manual setup.')
    raise SystemExit(1)
