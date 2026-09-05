@echo off
title SlicerFlow Copilot - Installer Build Script
setlocal

set "PROJECT_DIR=%~dp0"
set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"
set "CSC=%SystemRoot%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"

echo.
echo ====================================================================
echo   SlicerFlow Copilot - Build Pipeline
echo ====================================================================
echo.

:: -------------------------------------------------------
:: Step 1: Compile SlicerFlow_Setup.exe (Installer)
:: -------------------------------------------------------
echo [1/4] Compiling SlicerFlow_Setup.exe (One-Click Installer)...

if not exist "%CSC%" (
    echo [!] C# compiler not found at: %CSC%
    echo [!] Trying 32-bit .NET Framework...
    set "CSC=%SystemRoot%\Microsoft.NET\Framework\v4.0.30319\csc.exe"
)

if not exist "%CSC%" (
    echo [ERROR] No .NET Framework C# compiler (csc.exe) found.
    echo [ERROR] Install .NET Framework 4.x Developer Pack.
    pause
    exit /b 1
)

"%CSC%" /nologo /optimize /target:exe /platform:anycpu /out:"%PROJECT_DIR%\SlicerFlow_Setup.exe" "%PROJECT_DIR%\Installer.cs"

if %ERRORLEVEL% NEQ 0 (
    echo [FAIL] Installer compilation failed!
    pause
    exit /b 1
)
echo [OK] SlicerFlow_Setup.exe compiled successfully.

:: -------------------------------------------------------
:: Step 2: Compile Launcher binaries
:: -------------------------------------------------------
echo.
echo [2/4] Compiling SlicerFlow.exe and sf.exe launchers...

"%CSC%" /nologo /optimize /target:exe /out:"%PROJECT_DIR%\SlicerFlow.exe" "%PROJECT_DIR%\Launcher.cs"
"%CSC%" /nologo /optimize /target:exe /out:"%PROJECT_DIR%\sf.exe" "%PROJECT_DIR%\Launcher.cs"

if %ERRORLEVEL% NEQ 0 (
    echo [WARN] Launcher compilation had issues.
) else (
    echo [OK] SlicerFlow.exe and sf.exe compiled successfully.
)

:: -------------------------------------------------------
:: Step 3: Run Test Suite
:: -------------------------------------------------------
echo.
echo [3/4] Running automated test suite...

C:\Python313\python.exe -m pytest "%PROJECT_DIR%\slicerflow-copilot\tests" -v --tb=short

if %ERRORLEVEL% NEQ 0 (
    echo [WARN] Some tests failed. Review output above.
) else (
    echo [OK] All tests passed.
)

:: -------------------------------------------------------
:: Step 4: Summary
:: -------------------------------------------------------
echo.
echo ====================================================================
echo   BUILD COMPLETE
echo ====================================================================
echo.
echo   Artifacts:
echo     - SlicerFlow_Setup.exe   (One-Click Installer)
echo     - SlicerFlow.exe         (Native Launcher)
echo     - sf.exe                 (CLI Launcher)
echo.
echo   To install:
echo     .\SlicerFlow_Setup.exe
echo.
echo   For unattended install:
echo     .\SlicerFlow_Setup.exe /silent
echo.
echo ====================================================================
echo.
pause

endlocal
