// ============================================================================
// SlicerFlow Copilot - One-Click Windows Installer
// ============================================================================
// Compiles with native Windows C# compiler (csc.exe) — zero external
// dependencies. Designed for medical/clinical deployment contexts.
// Compatible with .NET Framework 4.0 csc.exe (no C# 6 features).
//
// Build:
//   %SystemRoot%\Microsoft.NET\Framework64\v4.0.30319\csc.exe
//     /nologo /optimize /target:exe
//     /out:SlicerFlow_Setup.exe Installer.cs
//
// Usage:
//   SlicerFlow_Setup.exe              Interactive installation
//   SlicerFlow_Setup.exe /silent      Unattended installation
//   SlicerFlow_Setup.exe /uninstall   Trigger uninstallation
// ============================================================================

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

namespace SlicerFlowInstaller
{
    class Program
    {
        // ====================================================================
        // CONFIGURATION CONSTANTS
        // ====================================================================
        const string APP_NAME       = "SlicerFlow Copilot";
        const string APP_VERSION    = "1.0.0-hackathon";
        const string APP_EXE_NAME   = "SlicerFlow.exe";
        const string CLI_NAME       = "sf";
        const string INSTALL_SUBDIR = @"Programs\SlicerFlow";
        const string SHORTCUT_NAME  = "SlicerFlow Copilot";

        const string MEDICAL_DISCLAIMER =
            "SAFETY DISCLAIMER: SlicerFlow Copilot is a research and medical engineering " +
            "workflow automation software. It does not provide autonomous clinical diagnosis, " +
            "prognostic predictions, or surgical treatment planning. All generated segmentations " +
            "and 3D models require review and approval by qualified medical professionals.";

        // Win32 API for shortcut creation
        [DllImport("shell32.dll")]
        static extern int SHGetFolderPath(IntPtr hwnd, int csidl, IntPtr token, uint flags, StringBuilder path);

        const int CSIDL_DESKTOPDIRECTORY = 0x0010;
        const int CSIDL_PROGRAMS         = 0x0002;

        // ====================================================================
        // MAIN
        // ====================================================================
        static int Main(string[] args)
        {
            Console.OutputEncoding = Encoding.UTF8;

            bool silent    = HasArg(args, "/silent") || HasArg(args, "-silent");
            bool uninstall = HasArg(args, "/uninstall") || HasArg(args, "-uninstall");

            if (uninstall)
            {
                return RunUninstall(silent);
            }

            return RunInstall(silent);
        }

        // ====================================================================
        // INSTALL
        // ====================================================================
        static int RunInstall(bool silent)
        {
            PrintBanner();

            if (!silent)
            {
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine("\n  This installer will:");
                Console.ResetColor();
                Console.WriteLine("    1. Install SlicerFlow Copilot to %LocalAppData%\\Programs\\SlicerFlow");
                Console.WriteLine("    2. Auto-detect installed 3D Slicer versions");
                Console.WriteLine("    3. Register the SlicerFlow extension inside 3D Slicer");
                Console.WriteLine("    4. Add the 'sf' command to your PATH");
                Console.WriteLine("    5. Create Desktop and Start Menu shortcuts");
                Console.WriteLine("    6. Deploy Google Gemini AI configuration\n");

                Console.ForegroundColor = ConsoleColor.Cyan;
                Console.Write("  Press ENTER to install, or Ctrl+C to cancel... ");
                Console.ResetColor();
                Console.ReadLine();
            }

            int totalSteps = 7;
            int currentStep = 0;
            int failures = 0;

            // ---------------------------------------------------------
            // STEP 1: Determine paths
            // ---------------------------------------------------------
            currentStep++;
            PrintStep(currentStep, totalSteps, "Resolving installation paths");

            string sourceDir = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
            string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            string installDir = Path.Combine(localAppData, INSTALL_SUBDIR);
            string copilotSrc = Path.Combine(sourceDir, "slicerflow-copilot");
            string myExtSrc   = Path.Combine(sourceDir, "MyExtension");
            string cliSrc     = Path.Combine(sourceDir, "cli.py");
            string envSrc     = Path.Combine(sourceDir, ".env");
            string launcherSrc = Path.Combine(sourceDir, "SlicerFlow.exe");

            // Check that source payload exists
            if (!Directory.Exists(copilotSrc))
            {
                string parentDir = sourceDir;
                DirectoryInfo parentInfo = Directory.GetParent(sourceDir);
                if (parentInfo != null)
                    parentDir = parentInfo.FullName;

                if (Directory.Exists(Path.Combine(parentDir, "slicerflow-copilot")))
                {
                    sourceDir = parentDir;
                    copilotSrc = Path.Combine(sourceDir, "slicerflow-copilot");
                    myExtSrc   = Path.Combine(sourceDir, "MyExtension");
                    cliSrc     = Path.Combine(sourceDir, "cli.py");
                    envSrc     = Path.Combine(sourceDir, ".env");
                    launcherSrc = Path.Combine(sourceDir, "SlicerFlow.exe");
                }
            }

            PrintOk("Source:  " + sourceDir);
            PrintOk("Install: " + installDir);

            // ---------------------------------------------------------
            // STEP 2: Copy files to install directory
            // ---------------------------------------------------------
            currentStep++;
            PrintStep(currentStep, totalSteps, "Copying SlicerFlow Copilot files");

            try
            {
                Directory.CreateDirectory(installDir);

                // Copy slicerflow-copilot package
                if (Directory.Exists(copilotSrc))
                {
                    CopyDirectory(copilotSrc, Path.Combine(installDir, "slicerflow-copilot"));
                    PrintOk("Copied slicerflow-copilot package");
                }
                else
                {
                    PrintWarn("slicerflow-copilot directory not found in source");
                    failures++;
                }

                // Copy MyExtension (Slicer module)
                if (Directory.Exists(myExtSrc))
                {
                    CopyDirectory(myExtSrc, Path.Combine(installDir, "MyExtension"));
                    PrintOk("Copied MyExtension (3D Slicer Module)");
                }

                // Copy cli.py
                if (File.Exists(cliSrc))
                {
                    File.Copy(cliSrc, Path.Combine(installDir, "cli.py"), true);
                    PrintOk("Copied cli.py entry point");
                }

                // Copy agent.py and slicer_agent.py from source root
                string agentSrc = Path.Combine(sourceDir, "agent.py");
                string slicerAgentSrc = Path.Combine(sourceDir, "slicer_agent.py");
                if (File.Exists(agentSrc))
                    File.Copy(agentSrc, Path.Combine(installDir, "agent.py"), true);
                if (File.Exists(slicerAgentSrc))
                    File.Copy(slicerAgentSrc, Path.Combine(installDir, "slicer_agent.py"), true);

                // Copy .env
                if (File.Exists(envSrc))
                {
                    File.Copy(envSrc, Path.Combine(installDir, ".env"), true);
                    PrintOk("Deployed .env with Google Gemini AI credentials");
                }

                // Copy launcher exe if exists
                if (File.Exists(launcherSrc))
                {
                    File.Copy(launcherSrc, Path.Combine(installDir, "SlicerFlow.exe"), true);
                    File.Copy(launcherSrc, Path.Combine(installDir, "sf.exe"), true);
                    PrintOk("Deployed SlicerFlow.exe and sf.exe launchers");
                }

                // Copy dist folder if exists (PyInstaller bundle)
                string distSrc = Path.Combine(sourceDir, "dist");
                if (Directory.Exists(distSrc))
                {
                    CopyDirectory(distSrc, Path.Combine(installDir, "dist"));
                    PrintOk("Deployed standalone PyInstaller bundle (dist/)");
                }

                // Copy batch/cmd wrappers
                string[] wrappers = new string[] { "sf.bat", "sf.cmd", "sf.ps1", "SlicerFlow.bat" };
                foreach (string wrapper in wrappers)
                {
                    string wrapperPath = Path.Combine(sourceDir, wrapper);
                    if (File.Exists(wrapperPath))
                        File.Copy(wrapperPath, Path.Combine(installDir, wrapper), true);
                }
            }
            catch (Exception ex)
            {
                PrintFail("File copy error: " + ex.Message);
                failures++;
            }

            // ---------------------------------------------------------
            // STEP 3: Auto-detect 3D Slicer
            // ---------------------------------------------------------
            currentStep++;
            PrintStep(currentStep, totalSteps, "Detecting 3D Slicer installation");

            List<string> slicerPaths = FindSlicerInstallations();
            string detectedSlicer = "";

            if (slicerPaths.Count > 0)
            {
                detectedSlicer = slicerPaths[0];
                PrintOk("Found 3D Slicer: " + detectedSlicer);
                for (int i = 1; i < slicerPaths.Count; i++)
                    PrintOk("  Also found: " + slicerPaths[i]);
            }
            else
            {
                PrintWarn("3D Slicer not detected. Install from https://download.slicer.org");
                PrintWarn("SlicerFlow CLI (sf) will still work in standalone mode.");
            }

            // ---------------------------------------------------------
            // STEP 4: Register extension in Slicer.ini
            // ---------------------------------------------------------
            currentStep++;
            PrintStep(currentStep, totalSteps, "Registering SlicerFlow extension in 3D Slicer");

            if (!string.IsNullOrEmpty(detectedSlicer))
            {
                try
                {
                    RegisterSlicerExtension(detectedSlicer, installDir);
                    PrintOk("Extension registered in Slicer.ini (AdditionalPaths + HomeModule)");
                }
                catch (Exception ex)
                {
                    PrintWarn("Could not register extension: " + ex.Message);
                    PrintWarn("You can manually add the module path in 3D Slicer > Edit > Application Settings > Modules.");
                }
            }
            else
            {
                PrintWarn("Skipped (no 3D Slicer detected)");
            }

            // ---------------------------------------------------------
            // STEP 5: Add to PATH
            // ---------------------------------------------------------
            currentStep++;
            PrintStep(currentStep, totalSteps, "Adding 'sf' command to system PATH");

            try
            {
                AddToPath(installDir);
                PrintOk("Added " + installDir + " to User PATH");
                PrintOk("The 'sf' command is now available globally.");
            }
            catch (Exception ex)
            {
                PrintWarn("Could not modify PATH: " + ex.Message);
                PrintWarn("Manually add '" + installDir + "' to your PATH environment variable.");
                failures++;
            }

            // ---------------------------------------------------------
            // STEP 6: Create shortcuts
            // ---------------------------------------------------------
            currentStep++;
            PrintStep(currentStep, totalSteps, "Creating Desktop and Start Menu shortcuts");

            try
            {
                CreateShortcuts(installDir);
                PrintOk("Desktop shortcut created: SlicerFlow Copilot");
                PrintOk("Start Menu shortcut created: SlicerFlow Copilot");
            }
            catch (Exception ex)
            {
                PrintWarn("Shortcut creation issue: " + ex.Message);
            }

            // ---------------------------------------------------------
            // STEP 7: Generate uninstaller
            // ---------------------------------------------------------
            currentStep++;
            PrintStep(currentStep, totalSteps, "Creating uninstaller");

            try
            {
                CreateUninstaller(installDir);
                PrintOk("Uninstaller created: Uninstall-SlicerFlow.bat");
            }
            catch (Exception ex)
            {
                PrintWarn("Uninstaller creation issue: " + ex.Message);
            }

            // ---------------------------------------------------------
            // SUMMARY
            // ---------------------------------------------------------
            Console.WriteLine();
            Console.ForegroundColor = ConsoleColor.DarkGray;
            Console.WriteLine("  " + new string('=', 68));
            Console.ResetColor();

            if (failures == 0)
            {
                Console.ForegroundColor = ConsoleColor.Green;
                Console.WriteLine("\n  INSTALLATION COMPLETED SUCCESSFULLY!");
                Console.ResetColor();
            }
            else
            {
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine(string.Format("\n  Installation completed with {0} warning(s). See above.", failures));
                Console.ResetColor();
            }

            Console.WriteLine("\n  Install Location:  " + installDir);
            Console.WriteLine("  CLI Command:       sf --help");
            Console.WriteLine("  Interactive Mode:  sf");
            Console.WriteLine("  Launch 3D Slicer:  sf --slicer");

            Console.ForegroundColor = ConsoleColor.DarkGray;
            Console.WriteLine("\n  " + MEDICAL_DISCLAIMER + "\n");
            Console.ResetColor();

            if (!silent)
            {
                Console.ForegroundColor = ConsoleColor.Cyan;
                Console.Write("  Press ENTER to exit... ");
                Console.ResetColor();
                Console.ReadLine();
            }

            return failures > 0 ? 1 : 0;
        }

        // ====================================================================
        // UNINSTALL
        // ====================================================================
        static int RunUninstall(bool silent)
        {
            string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            string installDir = Path.Combine(localAppData, INSTALL_SUBDIR);

            Console.ForegroundColor = ConsoleColor.Yellow;
            Console.WriteLine("\n  Uninstalling " + APP_NAME + " from " + installDir + "...\n");
            Console.ResetColor();

            // Remove from PATH
            try
            {
                RemoveFromPath(installDir);
                PrintOk("Removed from User PATH");
            }
            catch { }

            // Remove shortcuts
            try
            {
                string desktopDir = GetSpecialFolderPath(CSIDL_DESKTOPDIRECTORY);
                string startDir   = GetSpecialFolderPath(CSIDL_PROGRAMS);
                string deskShortcut = Path.Combine(desktopDir, SHORTCUT_NAME + ".lnk");
                string startShortcut = Path.Combine(startDir, SHORTCUT_NAME + ".lnk");
                if (File.Exists(deskShortcut)) { File.Delete(deskShortcut); PrintOk("Removed desktop shortcut"); }
                if (File.Exists(startShortcut)) { File.Delete(startShortcut); PrintOk("Removed Start Menu shortcut"); }
            }
            catch { }

            // Remove install directory
            try
            {
                if (Directory.Exists(installDir))
                {
                    Directory.Delete(installDir, true);
                    PrintOk("Removed " + installDir);
                }
            }
            catch (Exception ex)
            {
                PrintWarn("Could not fully remove install directory: " + ex.Message);
            }

            Console.ForegroundColor = ConsoleColor.Green;
            Console.WriteLine("\n  Uninstallation complete.\n");
            Console.ResetColor();

            if (!silent)
            {
                Console.Write("  Press ENTER to exit... ");
                Console.ReadLine();
            }

            return 0;
        }

        // ====================================================================
        // SLICER DETECTION
        // ====================================================================
        static List<string> FindSlicerInstallations()
        {
            List<string> found = new List<string>();
            string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);

            // Search %LocalAppData%\slicer.org\3D Slicer *
            string slicerOrgDir = Path.Combine(localAppData, "slicer.org");
            if (Directory.Exists(slicerOrgDir))
            {
                foreach (string dir in Directory.GetDirectories(slicerOrgDir, "3D Slicer*"))
                {
                    string exe = Path.Combine(dir, "Slicer.exe");
                    if (File.Exists(exe))
                        found.Add(exe);
                }
            }

            // Search %ProgramFiles%
            string[] progDirs = new string[] {
                Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
                Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86)
            };
            foreach (string pd in progDirs)
            {
                if (string.IsNullOrEmpty(pd) || !Directory.Exists(pd)) continue;
                try
                {
                    foreach (string dir in Directory.GetDirectories(pd, "Slicer*"))
                    {
                        string exe = Path.Combine(dir, "Slicer.exe");
                        if (File.Exists(exe))
                            found.Add(exe);
                    }
                }
                catch { }
            }

            // Check known path from .env
            string knownPath = @"C:\Users\juhai\AppData\Local\slicer.org\3D Slicer 5.12.3\Slicer.exe";
            if (File.Exists(knownPath) && !found.Contains(knownPath))
                found.Insert(0, knownPath);

            return found;
        }

        // ====================================================================
        // SLICER.INI REGISTRATION
        // ====================================================================
        static void RegisterSlicerExtension(string slicerExePath, string installDir)
        {
            string modulePath = Path.Combine(installDir, "MyExtension", "MyModule");

            // Find Slicer.ini
            string iniPath = Path.Combine(Path.GetDirectoryName(slicerExePath), "Slicer.ini");

            // Some Slicer installations store ini in AppData\Roaming
            if (!File.Exists(iniPath))
            {
                string roaming = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
                string slicerRoaming = Path.Combine(roaming, "slicer.org");
                if (Directory.Exists(slicerRoaming))
                {
                    foreach (string dir in Directory.GetDirectories(slicerRoaming, "3D Slicer*"))
                    {
                        string candidate = Path.Combine(dir, "Slicer.ini");
                        if (File.Exists(candidate))
                        {
                            iniPath = candidate;
                            break;
                        }
                    }
                }
            }

            // Also check in the slicer.org directory under LocalAppData
            if (!File.Exists(iniPath))
            {
                string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
                string slicerOrgDir = Path.Combine(localAppData, "slicer.org");
                if (Directory.Exists(slicerOrgDir))
                {
                    foreach (string dir in Directory.GetDirectories(slicerOrgDir, "3D Slicer*"))
                    {
                        string candidate = Path.Combine(dir, "Slicer.ini");
                        if (File.Exists(candidate))
                        {
                            iniPath = candidate;
                            break;
                        }
                    }
                }
            }

            if (!File.Exists(iniPath))
            {
                // Create minimal Slicer.ini
                File.WriteAllText(iniPath, "[Modules]\n");
            }

            // Read and modify ini
            string iniContent = File.ReadAllText(iniPath, Encoding.UTF8);
            string normalizedModulePath = modulePath.Replace("\\", "/");

            // Add to AdditionalPaths if not already present
            if (!iniContent.Contains(normalizedModulePath))
            {
                int modulesIdx = iniContent.IndexOf("[Modules]", StringComparison.OrdinalIgnoreCase);
                if (modulesIdx < 0)
                {
                    iniContent += "\n[Modules]\n";
                    modulesIdx = iniContent.LastIndexOf("[Modules]", StringComparison.OrdinalIgnoreCase);
                }

                string additionalLine = "AdditionalPaths=" + normalizedModulePath;
                int apIdx = iniContent.IndexOf("AdditionalPaths=", StringComparison.OrdinalIgnoreCase);
                if (apIdx >= 0)
                {
                    int lineEnd = iniContent.IndexOf('\n', apIdx);
                    if (lineEnd < 0) lineEnd = iniContent.Length;
                    string existingValue = iniContent.Substring(apIdx + "AdditionalPaths=".Length, lineEnd - apIdx - "AdditionalPaths=".Length).Trim();
                    if (!existingValue.Contains(normalizedModulePath))
                    {
                        string newValue = existingValue + ", " + normalizedModulePath;
                        iniContent = iniContent.Substring(0, apIdx) + "AdditionalPaths=" + newValue + iniContent.Substring(lineEnd);
                    }
                }
                else
                {
                    int insertAt = iniContent.IndexOf('\n', modulesIdx);
                    if (insertAt < 0) insertAt = iniContent.Length;
                    iniContent = iniContent.Insert(insertAt + 1, additionalLine + "\n");
                }
            }

            // Set HomeModule
            if (!iniContent.Contains("HomeModule=MyModule"))
            {
                int hmIdx = iniContent.IndexOf("HomeModule=", StringComparison.OrdinalIgnoreCase);
                if (hmIdx >= 0)
                {
                    int lineEnd = iniContent.IndexOf('\n', hmIdx);
                    if (lineEnd < 0) lineEnd = iniContent.Length;
                    iniContent = iniContent.Substring(0, hmIdx) + "HomeModule=MyModule" + iniContent.Substring(lineEnd);
                }
                else
                {
                    int modulesIdx = iniContent.IndexOf("[Modules]", StringComparison.OrdinalIgnoreCase);
                    int insertAt = iniContent.IndexOf('\n', modulesIdx);
                    if (insertAt < 0) insertAt = iniContent.Length;
                    iniContent = iniContent.Insert(insertAt + 1, "HomeModule=MyModule\n");
                }
            }

            File.WriteAllText(iniPath, iniContent, Encoding.UTF8);
        }

        // ====================================================================
        // PATH MANAGEMENT
        // ====================================================================
        static void AddToPath(string dir)
        {
            string currentPath = Environment.GetEnvironmentVariable("PATH", EnvironmentVariableTarget.User) ?? "";
            if (currentPath.ToLower().Contains(dir.ToLower()))
                return;

            string newPath = currentPath.TrimEnd(';') + ";" + dir;
            Environment.SetEnvironmentVariable("PATH", newPath, EnvironmentVariableTarget.User);
        }

        static void RemoveFromPath(string dir)
        {
            string currentPath = Environment.GetEnvironmentVariable("PATH", EnvironmentVariableTarget.User) ?? "";
            string[] parts = currentPath.Split(';');
            List<string> cleaned = new List<string>();
            foreach (string p in parts)
            {
                if (!string.IsNullOrWhiteSpace(p) && !p.Trim().Equals(dir, StringComparison.OrdinalIgnoreCase))
                    cleaned.Add(p);
            }
            Environment.SetEnvironmentVariable("PATH", string.Join(";", cleaned.ToArray()), EnvironmentVariableTarget.User);
        }

        // ====================================================================
        // SHORTCUTS
        // ====================================================================
        static void CreateShortcuts(string installDir)
        {
            string targetExe = Path.Combine(installDir, "SlicerFlow.bat");
            if (!File.Exists(targetExe))
                targetExe = Path.Combine(installDir, "SlicerFlow.exe");

            string desktopDir = GetSpecialFolderPath(CSIDL_DESKTOPDIRECTORY);
            string startDir   = GetSpecialFolderPath(CSIDL_PROGRAMS);

            CreateShortcutViaPS(
                Path.Combine(desktopDir, SHORTCUT_NAME + ".lnk"),
                targetExe,
                installDir,
                "SlicerFlow Copilot - Natural Language 3D Medical Imaging Pipeline"
            );

            CreateShortcutViaPS(
                Path.Combine(startDir, SHORTCUT_NAME + ".lnk"),
                targetExe,
                installDir,
                "SlicerFlow Copilot - Natural Language 3D Medical Imaging Pipeline"
            );
        }

        static void CreateShortcutViaPS(string shortcutPath, string targetPath, string workingDir, string description)
        {
            string psScript =
                "$ws = New-Object -ComObject WScript.Shell; " +
                "$sc = $ws.CreateShortcut('" + shortcutPath.Replace("'", "''") + "'); " +
                "$sc.TargetPath = '" + targetPath.Replace("'", "''") + "'; " +
                "$sc.WorkingDirectory = '" + workingDir.Replace("'", "''") + "'; " +
                "$sc.Description = '" + description.Replace("'", "''") + "'; " +
                "$sc.Save()";

            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = "powershell.exe";
            psi.Arguments = "-NoProfile -ExecutionPolicy Bypass -Command \"" + psScript + "\"";
            psi.UseShellExecute = false;
            psi.CreateNoWindow = true;
            psi.RedirectStandardOutput = true;
            psi.RedirectStandardError = true;

            try
            {
                using (Process proc = Process.Start(psi))
                {
                    proc.WaitForExit(5000);
                }
            }
            catch { }
        }

        // ====================================================================
        // UNINSTALLER SCRIPT
        // ====================================================================
        static void CreateUninstaller(string installDir)
        {
            string uninstallBat = Path.Combine(installDir, "Uninstall-SlicerFlow.bat");
            string content = "@echo off\r\n" +
                "title Uninstall SlicerFlow Copilot\r\n" +
                "echo.\r\n" +
                "echo ========================================\r\n" +
                "echo   Uninstalling SlicerFlow Copilot...\r\n" +
                "echo ========================================\r\n" +
                "echo.\r\n" +
                "\r\n" +
                "set \"INSTALL_DIR=%~dp0\"\r\n" +
                "set \"INSTALL_DIR=%INSTALL_DIR:~0,-1%\"\r\n" +
                "\r\n" +
                "echo Removing from PATH...\r\n" +
                "powershell -NoProfile -Command \"$p = [Environment]::GetEnvironmentVariable('PATH','User'); $parts = $p -split ';' | Where-Object { $_ -ne '%INSTALL_DIR%' }; [Environment]::SetEnvironmentVariable('PATH', ($parts -join ';'), 'User')\"\r\n" +
                "\r\n" +
                "echo Removing Desktop shortcut...\r\n" +
                "del \"%USERPROFILE%\\Desktop\\SlicerFlow Copilot.lnk\" 2>nul\r\n" +
                "\r\n" +
                "echo Removing Start Menu shortcut...\r\n" +
                "del \"%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\SlicerFlow Copilot.lnk\" 2>nul\r\n" +
                "\r\n" +
                "echo Removing installation files...\r\n" +
                "timeout /t 2 >nul\r\n" +
                "cd /d \"%TEMP%\"\r\n" +
                "rmdir /s /q \"%INSTALL_DIR%\" 2>nul\r\n" +
                "\r\n" +
                "echo.\r\n" +
                "echo ========================================\r\n" +
                "echo   SlicerFlow Copilot uninstalled.\r\n" +
                "echo ========================================\r\n" +
                "echo.\r\n" +
                "pause\r\n";
            File.WriteAllText(uninstallBat, content, Encoding.ASCII);
        }

        // ====================================================================
        // UI HELPERS
        // ====================================================================
        static void PrintBanner()
        {
            try { Console.Clear(); } catch { }
            Console.ForegroundColor = ConsoleColor.Cyan;
            Console.WriteLine("");
            Console.WriteLine("  ======================================================================");
            Console.WriteLine("  |                                                                    |");
            Console.WriteLine("  |       ____  __ _                 ______ __                         |");
            Console.WriteLine("  |      / __/ / /(_)_____ ___  ____/ ____// /___  _      __           |");
            Console.WriteLine("  |     _\\ \\  / // // __// -_)/ __// __/ / // __ \\| | /| / /           |");
            Console.WriteLine("  |    /___/ /_//_/ \\__/ \\__//_/  /_/   /_/ \\____/|_|/ |/_/            |");
            Console.WriteLine("  |                                                                    |");
            Console.WriteLine("  |                  COPILOT WINDOWS INSTALLER                         |");
            Console.WriteLine("  |                                                                    |");
            Console.WriteLine("  |    Natural Language -> Validated Workflow -> 3D Medical Pipeline    |");
            Console.WriteLine("  |                                                                    |");
            Console.WriteLine("  ======================================================================");
            Console.WriteLine("");
            Console.ResetColor();
            Console.ForegroundColor = ConsoleColor.DarkGray;
            Console.WriteLine("  Version: " + APP_VERSION);
            Console.ResetColor();
        }

        static void PrintStep(int current, int total, string message)
        {
            int barWidth = 40;
            double pct = (double)current / total;
            int filled = (int)(barWidth * pct);
            string bar = new string('#', filled) + new string('-', barWidth - filled);

            Console.ForegroundColor = ConsoleColor.DarkGray;
            Console.Write(string.Format("\n  [{0}] {1}%  ", bar, (int)(pct * 100)));
            Console.ForegroundColor = ConsoleColor.White;
            Console.WriteLine(string.Format("Step {0}/{1}: {2}", current, total, message));
            Console.ResetColor();
        }

        static void PrintOk(string message)
        {
            Console.ForegroundColor = ConsoleColor.Green;
            Console.Write("    [OK] ");
            Console.ResetColor();
            Console.WriteLine(message);
        }

        static void PrintWarn(string message)
        {
            Console.ForegroundColor = ConsoleColor.Yellow;
            Console.Write("    [!!] ");
            Console.ResetColor();
            Console.WriteLine(message);
        }

        static void PrintFail(string message)
        {
            Console.ForegroundColor = ConsoleColor.Red;
            Console.Write("    [XX] ");
            Console.ResetColor();
            Console.WriteLine(message);
        }

        // ====================================================================
        // FILE HELPERS
        // ====================================================================
        static void CopyDirectory(string sourceDir, string destDir)
        {
            Directory.CreateDirectory(destDir);

            foreach (string file in Directory.GetFiles(sourceDir))
            {
                string fileName = Path.GetFileName(file);
                if (fileName.EndsWith(".pyc") || fileName == ".gitignore")
                    continue;
                File.Copy(file, Path.Combine(destDir, fileName), true);
            }

            foreach (string dir in Directory.GetDirectories(sourceDir))
            {
                string dirName = Path.GetFileName(dir);
                if (dirName == "__pycache__" || dirName == ".git" || dirName == ".pytest_cache" || dirName == "build")
                    continue;
                CopyDirectory(dir, Path.Combine(destDir, dirName));
            }
        }

        static bool HasArg(string[] args, string flag)
        {
            if (args == null) return false;
            foreach (string a in args)
                if (a.Equals(flag, StringComparison.OrdinalIgnoreCase))
                    return true;
            return false;
        }

        static string GetSpecialFolderPath(int csidl)
        {
            StringBuilder sb = new StringBuilder(260);
            SHGetFolderPath(IntPtr.Zero, csidl, IntPtr.Zero, 0, sb);
            return sb.ToString();
        }
    }
}
