"""Install the adjacent payload after backing up a local Windows CoffeePOS."""
from datetime import datetime
from pathlib import Path
import shutil
import sqlite3
import sys
import zipfile


def main():
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / 'Downloads' / 'coffeepos-feature-floor-map-20261016'
    if not (target / 'backend' / 'app' / 'main.py').is_file() or not (target / 'src' / 'Admin.tsx').is_file():
        raise RuntimeError('CoffeePOS papkasi topilmadi: ' + str(target))
    payload = Path(__file__).resolve().parent / 'payload'
    files = sorted(p for p in payload.rglob('*') if p.is_file())
    if not files:
        raise RuntimeError('Payload topilmadi. ZIPni toliq oching.')
    print('CoffeePOS: ' + str(target))
    print('Server va Vite CMD oynalarida Ctrl+C bosing. Oynalarni yopmang.')
    input('Ikkalasi toxtaganidan keyin Enter bosing: ')
    backup = target / 'update-backups' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup.mkdir(parents=True, exist_ok=False)
    databases = {p for pattern in ('*.db', '*.sqlite', '*.sqlite3') for p in target.glob(pattern)}
    for database in sorted(databases):
        with sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True) as source:
            with sqlite3.connect(backup / database.name) as dest:
                source.backup(dest)
                if dest.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise RuntimeError('Baza nusxasi tekshiruvdan otmadi: ' + database.name)
    # Every destination is recorded, including new files, for source rollback.
    existing = []
    new = []
    with zipfile.ZipFile(backup / 'previous-source.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for source in files:
            rel = source.relative_to(payload)
            dest = target / rel
            if dest.is_file():
                archive.write(dest, rel.as_posix())
                existing.append(rel)
            else:
                new.append(rel)
    try:
        for source in files:
            dest = target / source.relative_to(payload)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
    except Exception:
        with zipfile.ZipFile(backup / 'previous-source.zip') as archive:
            for rel in existing:
                (target / rel).write_bytes(archive.read(rel.as_posix()))
        for rel in new:
            (target / rel).unlink(missing_ok=True)
        raise
    print('Yangilandi. Zaxira: ' + str(backup))
    print('Serverni AVVALGI DATABASE_URL bilan qayta yoqing. Viteni ham qayta yoqing.')
    print('Brauzerda Ctrl+F5. Admin -> Bonus tizimi -> foizlarni tanlang va yoqing.')
    print('Eski APK avtomatik yangilanmaydi. Hozir brauzer orqali tekshiring.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('XATO: ' + str(error))
        raise SystemExit(1)
