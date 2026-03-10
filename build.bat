@echo off
echo ============================================================
echo  Tokenificator — Build
echo ============================================================

:: Check pyinstaller is installed
pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
)

:: Clean previous build
if exist dist\Tokenificator rmdir /s /q dist\Tokenificator
if exist build rmdir /s /q build

:: Build
echo.
echo Building...
pyinstaller tokenificator.spec

if errorlevel 1 (
    echo.
    echo BUILD FAILED. Check the output above for errors.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  Done!  Output: dist\Tokenificator\Tokenificator.exe
echo
echo  To distribute: zip the entire dist\Tokenificator\ folder.
echo  Users unzip it and run Tokenificator.exe.
echo  They can add custom masks/frames next to Tokenificator.exe.
echo ============================================================
pause
