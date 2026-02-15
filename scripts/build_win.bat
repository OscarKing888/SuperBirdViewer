@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT_DIR=%%~fI"
cd /d "%ROOT_DIR%"

where py >nul 2>nul
if %errorlevel%==0 (
  set "PYTHON_BIN=py -3"
) else (
  set "PYTHON_BIN=python"
)

%PYTHON_BIN% -m PyInstaller ^
  --noconfirm ^
  --clean ^
  SuperEXIF_win.spec
if errorlevel 1 goto :end

echo [OK] 打包完成: dist\SuperEXIF

:end
endlocal
