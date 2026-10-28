@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\ACTIVAR_AUTOARRANQUE_WINDOWS.ps1"
set "RESULT=%ERRORLEVEL%"
echo.
if not "%RESULT%"=="0" (
  echo Ocurrio un error. Revisa el mensaje anterior.
) else (
  echo Operacion finalizada.
)
pause
exit /b %RESULT%
