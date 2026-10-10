@echo off
setlocal
cd /d "%~dp0.."
if not exist "coffeepos.db" (
  echo Database not found. No backup was made.
  exit /b 1
)
py -3.12 scripts\backup_db.py
exit /b %errorlevel%
