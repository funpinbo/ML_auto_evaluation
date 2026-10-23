@echo off
rem AI-DLC Monitor one-click launcher for Windows (SCOPE-01, ADR-001). run.py does the real work.
rem   run.bat [--port N] [--no-browser]   (double-click works)
rem Python 3.11+ lookup: "py -3" first, then "python". Each candidate is actually executed with a
rem version check, so the Microsoft Store alias (python.exe stub in WindowsApps that only prints an
rem install hint and exits 9009) is skipped, while a real Store-installed Python still works.
rem Messages here are ASCII on purpose: cmd reads .bat files in the OEM code page (cp949/cp437).
rem On failure the window stays open (pause) so a double-click user can read the error (PO Q-P3).
rem This file must keep CRLF line endings.
setlocal
set "PYCMD="
py -3 -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
if not errorlevel 1 set "PYCMD=py -3"
if defined PYCMD goto run
python -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
if not errorlevel 1 set "PYCMD=python"
if defined PYCMD goto run
echo [monitor] Python 3.11 or newer is required (not found via "py -3" or "python").
echo [monitor] Install it from https://www.python.org/downloads/ (check "Add python.exe to PATH") and run again.
set "RC=1"
goto fail

:run
%PYCMD% "%~dp0run.py" %*
set "RC=%ERRORLEVEL%"
if "%RC%"=="0" goto done

:fail
echo.
echo [monitor] Launcher stopped (exit code %RC%). See the messages above.
pause
:done
endlocal & exit /b %RC%
