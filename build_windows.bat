@echo off
setlocal EnableExtensions

set "APP_NAME=2nd & 3rd 95 Analyzer"
set "MAIN_EXE=2nd-and-3rd-95-analysis.exe"
set "VERSION_FILE=version.py"

for /f "tokens=3" %%V in ('findstr /B "__version__" "%VERSION_FILE%"') do set "APP_VERSION=%%~V"
if not defined APP_VERSION (
    echo Could not read application version from version.py
    exit /b 1
)

echo ==============================================
echo   %APP_NAME% - WINDOWS BUILD
echo   Version: %APP_VERSION%
echo ==============================================

call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo Could not activate .venv
    exit /b 1
)

python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

rmdir /s /q run.build 2>nul
rmdir /s /q run.dist 2>nul
rmdir /s /q updater.dist 2>nul
rmdir /s /q update_package 2>nul

echo.
echo [1/3] Building main application...
python -m nuitka --msvc=latest --standalone --windows-console-mode=disable --include-windows-runtime-dlls=yes --windows-icon-from-ico=app.ico --output-filename="%MAIN_EXE%" --enable-plugin=tk-inter --include-package=pystray --include-package=PIL --include-data-dir=app/templates=app/templates --include-data-dir=app/static=app/static --include-data-files=LAMISNMRS.csv=LAMISNMRS.csv --include-data-files=app.ico=app.ico run.py
if errorlevel 1 exit /b 1

echo.
echo [2/3] Building updater...
python -m nuitka --msvc=latest --standalone --windows-console-mode=disable --output-filename=updater.exe updater/updater.py
if errorlevel 1 exit /b 1

if not exist run.dist mkdir run.dist
copy /Y updater.dist\updater.exe run.dist\updater.exe >nul
if errorlevel 1 exit /b 1

robocopy updater.dist run.dist /E /XF updater.exe >nul
if errorlevel 8 exit /b 1
copy /Y app.ico run.dist\app.ico >nul

if exist update_package rmdir /s /q update_package
mkdir update_package

robocopy run.dist update_package /E /XF updater.exe >nul
if errorlevel 8 exit /b 1

rem The running updater cannot replace itself, so keep the installed updater binary out of update ZIPs.

powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'update_package\*' -DestinationPath '2nd-and-3rd-95-analysis-v%APP_VERSION%.zip' -Force"
if errorlevel 1 exit /b 1

powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-Content installer.iss) -replace '^#define MyAppVersion \".*\"$', '#define MyAppVersion \"%APP_VERSION%\"' | Set-Content installer.iss -Encoding UTF8"

echo.
echo [3/3] Build complete.
echo Main distribution : run.dist\
echo Update package    : 2nd-and-3rd-95-analysis-v%APP_VERSION%.zip
echo.
echo Next steps:
echo   1. Create GitHub Release tag v%APP_VERSION%.
echo   2. Upload the ZIP to that release.
echo   3. Calculate SHA-256 of the ZIP.
echo   4. Update update.json with version, URL and SHA-256.
echo   5. Commit/push update.json.
echo.
endlocal
