#!/usr/bin/env python3
"""Launch a disposable SQLite API + Vite stack and run browser regressions.
Requires npm ci, pip install -e './backend[dev]', and Playwright Chromium.
No external server or database is used. Processes and database are removed on exit.
"""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def main():
    # Vite's configured proxy uses 8000; refuse to share an existing API.
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 8000))
    ui_port = port()
    base = f'http://127.0.0.1:{ui_port}'
    with tempfile.TemporaryDirectory(prefix='coffeepos-browser-') as work:
        env = {**os.environ, 'DATABASE_URL': f'sqlite:///{work}/test.db',
               'SECRET_KEY': uuid4().hex + uuid4().hex, 'SEED_DEMO': '0',
               'ALLOW_PUBLIC_REGISTRATION': '1', 'ENFORCE_LICENSES': '0',
               'UI_BASE_URL': base}
        processes = []
        with open(Path(work) / 'servers.log', 'w+') as log:
            try:
                processes.append(subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app',
                    '--host', '127.0.0.1', '--port', '8000'], cwd=ROOT / 'backend', env=env,
                    stdout=log, stderr=log))
                processes.append(subprocess.Popen(['node', str(ROOT / 'node_modules/vite/bin/vite.js'), '--host', '127.0.0.1',
                    '--port', str(ui_port), '--strictPort'], cwd=ROOT, env=env, stdout=log, stderr=log))
                for _ in range(120):
                    if any(p.poll() is not None for p in processes):
                        raise RuntimeError('Test server stopped before readiness')
                    try:
                        urlopen(base, timeout=1).close()
                        urlopen('http://127.0.0.1:8000/openapi.json', timeout=1).close()
                        break
                    except OSError:
                        time.sleep(.25)
                else:
                    raise RuntimeError('Test server readiness timed out')
                subprocess.run(['node', 'scripts/browser_regression.mjs'], cwd=ROOT, env=env, check=True)
            except Exception:
                log.seek(0)
                print(log.read()[-6000:], file=sys.stderr)
                raise
            finally:
                for process in processes:
                    process.terminate()
                for process in processes:
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()


if __name__ == '__main__':
    main()
