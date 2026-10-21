@echo off
REM ========================================================
REM  DraveBackup - bouw losse .exe (onefile, PyInstaller)
REM ========================================================
setlocal
cd /d "%~dp0"

set "PYEXE="
for %%V in (3.13 3.12 3.11 3.10) do (
    if not defined PYEXE (
        py -%%V -c "import sys" >nul 2>&1 && set "PYEXE=py -%%V"
    )
)
if not defined PYEXE python -c "import sys" >nul 2>&1 && set "PYEXE=python"
if not defined PYEXE (
    echo Geen geschikte Python gevonden ^(3.10 t/m 3.13^).
    echo Installeer Python van https://www.python.org en probeer opnieuw.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" %PYEXE% -m venv .venv
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip --quiet
python -m pip install --only-binary=:all: -r requirements.txt
python -m pip install --only-binary=:all: pyinstaller pillow
if exist "logo.png" python maak_icoon.py
echo Bouwen...
pyinstaller --noconfirm app.spec
echo.
echo Klaar. De .exe staat in de map dist\.
pause
