#!/bin/bash
set -e  # Stop immediately if any command fails

# 0. SAFETY CHECK
if [ ! -f "MyriFetch.py" ]; then
    echo "❌ Error: MyriFetch.py not found in this folder."
    exit 1
fi

if [ ! -f "MyriFetch.desktop" ]; then
    echo "❌ Error: MyriFetch.desktop not found in this folder."
    exit 1
fi

# 1. SETUP VIRTUAL ENVIRONMENT
echo ">>> 📦 Setting up isolated build environment..."
if [ ! -d "build_venv" ]; then
    python3 -m venv build_venv
fi
source build_venv/bin/activate

# 2. INSTALL DEPENDENCIES (Inside venv)
echo ">>> ⬇️  Installing libraries..."
pip install --upgrade pip > /dev/null
pip install pyinstaller pillow requests beautifulsoup4 customtkinter urllib3 > /dev/null

# 3. CLEANUP OLD BUILDS
echo ">>> 🧹 Cleaning up old build artifacts..."
rm -rf build dist AppDir *.AppImage

# 4. BUILD EXECUTABLE
echo ">>> 🔨 Compiling with PyInstaller..."
# Check for icon.ico for the internal binary icon (optional but nice if present)
ICON_ARG=""
if [ -f "icon.ico" ]; then
    ICON_ARG="--icon=icon.ico"
fi

./build_venv/bin/pyinstaller --noconfirm --onedir --windowed --clean \
    --name "MyriFetch" \
    $ICON_ARG \
    --collect-all customtkinter \
    MyriFetch.py

# 5. PREPARE APPIMAGE STRUCTURE
echo ">>> 📂 Creating AppImage structure..."
mkdir -p AppDir/usr/bin
mkdir -p AppDir/usr/share/icons/hicolor/256x256/apps

# Copy the binary folder
cp -r dist/MyriFetch/* AppDir/usr/bin/

# Copy the desktop entry
cp MyriFetch.desktop AppDir/

# --- HANDLE ICON ---
echo ">>> 🎨 Handling Icon..."
if [ -f "icon.png" ]; then
    echo "    - Found custom icon.png!"
    # AppImage needs the icon in the root named correctly (matching .desktop Icon= entry)
    cp icon.png AppDir/myrient.png
    # And in the standard Linux icon path
    cp icon.png AppDir/usr/share/icons/hicolor/256x256/apps/myrient.png
else
    echo "    - No icon.png found. Generating temporary placeholder..."
    convert -size 256x256 xc:#00f2ff AppDir/myrient.png 2>/dev/null || touch AppDir/myrient.png
    cp AppDir/myrient.png AppDir/usr/share/icons/hicolor/256x256/apps/myrient.png
fi
# -------------------

# Create the AppRun symlink
ln -sr AppDir/usr/bin/MyriFetch AppDir/AppRun

# 6. GET APPIMAGETOOL
if [ ! -f appimagetool-x86_64.AppImage ]; then
    echo ">>> 📥 Downloading AppImageTool..."
    wget -q https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x appimagetool-x86_64.AppImage
fi

# 7. PACKAGE IT
echo ">>> 📦 Packaging AppImage..."
ARCH=x86_64 ./appimagetool-x86_64.AppImage --appimage-extract-and-run AppDir MyriFetch-x86_64.AppImage

# 8. CLEANUP VENV
deactivate

echo ">>> ✅ DONE! Run your app: ./MyriFetch-x86_64.AppImage"
