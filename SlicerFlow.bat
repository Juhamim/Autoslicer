@echo off
setlocal
set "PROJECT_DIR=c:\Users\juhai\Downloads\Slicer-main"
cd /d "%PROJECT_DIR%"
title SlicerFlow Copilot - Native Windows Build

:: Use standalone executable if built, otherwise Python CLI
if exist "%PROJECT_DIR%\dist\SlicerFlow\SlicerFlow.exe" (
    set "SF_CMD=%PROJECT_DIR%\dist\SlicerFlow\SlicerFlow.exe"
) else if exist "%PROJECT_DIR%\SlicerFlow.exe" (
    set "SF_CMD=%PROJECT_DIR%\SlicerFlow.exe"
) else (
    set "SF_CMD=C:\Python313\python.exe %PROJECT_DIR%\cli.py"
)

if not "%~1"=="" (
    %SF_CMD% %*
    goto end
)

:menu
cls
echo =======================================================================
echo          SLICERFLOW COPILOT - NATIVE WINDOWS SUITE
echo    From Natural Language to Verified & Reproducible 3D Workflows
echo =======================================================================
echo.
echo   [1] Launch 3D Slicer Native GUI (with SlicerFlow Copilot Module)
echo   [2] Launch Interactive Terminal AI Copilot Agent (sf)
echo   [3] Run Automated Test Suite (12 unit tests)
echo   [4] Build Windows Standalone Executable (SlicerFlow.exe)
echo   [5] Exit
echo.
set /p choice="Select option [1-5] (default 1): "

if "%choice%"=="2" (
    %SF_CMD%
    goto end
)
if "%choice%"=="3" (
    C:\Python313\python.exe -m pytest "%PROJECT_DIR%\slicerflow-copilot\tests" -v
    pause
    goto menu
)
if "%choice%"=="4" (
    echo Building Windows Standalone Executable with PyInstaller...
    C:\Python313\python.exe -m PyInstaller --noconfirm --onedir --console --name "SlicerFlow" --paths "%PROJECT_DIR%\slicerflow-copilot" --paths "%PROJECT_DIR%" --collect-all "SimpleITK" --add-data "slicerflow-copilot;slicerflow-copilot" "%PROJECT_DIR%\cli.py"
    if exist "%SystemRoot%\Microsoft.NET\Framework64\v4.0.30319\csc.exe" (
        "%SystemRoot%\Microsoft.NET\Framework64\v4.0.30319\csc.exe" /nologo /optimize /target:exe /out:"%PROJECT_DIR%\SlicerFlow.exe" "%PROJECT_DIR%\Launcher.cs"
        "%SystemRoot%\Microsoft.NET\Framework64\v4.0.30319\csc.exe" /nologo /optimize /target:exe /out:"%PROJECT_DIR%\sf.exe" "%PROJECT_DIR%\Launcher.cs"
    )
    echo.
    echo Standalone executable created successfully at:
    echo   - %PROJECT_DIR%\dist\SlicerFlow\SlicerFlow.exe
    echo   - %PROJECT_DIR%\SlicerFlow.exe
    echo   - %PROJECT_DIR%\sf.exe
    pause
    goto menu
)
if "%choice%"=="5" (
    goto end
)

:: Default: Launch 3D Slicer with extension
echo Launching 3D Slicer with SlicerFlow Copilot...
%SF_CMD% --slicer

:end
endlocal
