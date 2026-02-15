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
  --windowed ^
  --name SuperEXIF ^
  --icon image\superexif.ico ^
  --add-data "EXIF.cfg;." ^
  --add-data "image/superexif.png;image" ^
  --add-data "image/superexif.ico;image" ^
  main.py
if errorlevel 1 goto :end

echo [OK] 打包完成: dist\SuperEXIF

:end
endlocal
