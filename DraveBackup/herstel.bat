@echo off
REM ========================================================
REM  DraveBackup - herstel (.venv wissen en herbouwen)
REM ========================================================
setlocal
cd /d "%~dp0"

echo Dit verwijdert de map .venv en installeert alles opnieuw.
echo (Je back-uptaken in DraveBackup-data blijven staan.)
pause
if exist ".venv" rmdir /s /q ".venv"
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
%PYEXE% -m venv .venv
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip --quiet
python -m pip install --only-binary=:all: -r requirements.txt
echo Klaar.
pause
