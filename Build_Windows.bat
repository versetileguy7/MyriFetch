@echo off
setlocal
TITLE MyriFetch Clean Builder

echo ==========================================
echo      MYRIFETCH CLEAN BUILDER (Windows)
echo ==========================================

:: 1. CHECK FOR ICON
set ICON_FLAG=
if exist icon.ico (
    echo [INFO] Found icon.ico - embedding in executable.
    set ICON_FLAG=--icon "icon.ico"
) else (
    echo [WARNING] icon.ico not found. Using default icon.
)

:: 2. CHECK PYTHON
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in your PATH.
    pause
    exit /b
)

:: 3. CLEANUP OLD ARTIFACTS
echo.
echo [1/5] Cleaning old build files...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist build_venv rmdir /s /q build_venv
if exist *.spec del *.spec

:: 4. CREATE ISOLATED VIRTUAL ENVIRONMENT
echo.
echo [2/5] Creating isolated build environment...
python -m venv build_venv

:: 5. ACTIVATE & INSTALL DEPENDENCIES
echo.
echo [3/5] Installing dependencies into isolation...
call build_venv\Scripts\activate
python -m pip install --upgrade pip
pip install pyinstaller pillow requests beautifulsoup4 customtkinter urllib3

:: 6. BUILD EXE
echo.
echo [4/5] Compiling MyriFetch.py...
:: Added %ICON_FLAG% to the command below
pyinstaller --noconfirm --onefile --noconsole --clean ^
    --name "MyriFetch" ^
    %ICON_FLAG% ^
    --collect-all customtkinter ^
    MyriFetch.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Build failed!
    call deactivate
    pause
    exit /b
)

:: 7. CLEANUP ENVIRONMENT
echo.
echo [5/5] Cleaning up temporary environment...
call deactivate
rmdir /s /q build_venv

echo.
echo ==========================================
echo      BUILD SUCCESSFUL!
echo ==========================================
echo.
echo Your app is ready: dist\MyriFetch.exe
echo.
pause
