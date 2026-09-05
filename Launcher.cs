using System;
using System.Diagnostics;
using System.IO;

namespace SlicerFlow
{
    class Program
    {
        static int Main(string[] args)
        {
            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string distExe = Path.Combine(baseDir, "dist", "SlicerFlow", "SlicerFlow.exe");
            string pythonExe = @"C:\Python313\python.exe";
            string cliScript = Path.Combine(baseDir, "cli.py");

            ProcessStartInfo psi = new ProcessStartInfo();
            psi.UseShellExecute = false;
            psi.WorkingDirectory = baseDir;

            if (File.Exists(distExe))
            {
                psi.FileName = distExe;
                psi.Arguments = BuildArguments(args);
            }
            else if (File.Exists(pythonExe) && File.Exists(cliScript))
            {
                psi.FileName = pythonExe;
                psi.Arguments = "\"" + cliScript + "\" " + BuildArguments(args);
            }
            else
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine("[-] SlicerFlow executable or Python environment not found.");
                Console.ResetColor();
                return 1;
            }

            try
            {
                using (Process proc = Process.Start(psi))
                {
                    proc.WaitForExit();
                    return proc.ExitCode;
                }
            }
            catch (Exception ex)
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine("[-] Failed to execute SlicerFlow: " + ex.Message);
                Console.ResetColor();
                return 1;
            }
        }

        private static string BuildArguments(string[] args)
        {
            if (args == null || args.Length == 0) return "";
            string[] escaped = new string[args.Length];
            for (int i = 0; i < args.Length; i++)
            {
                string a = args[i];
                if (a.Contains(" ") || a.Contains("\""))
                {
                    escaped[i] = "\"" + a.Replace("\"", "\\\"") + "\"";
                }
                else
                {
                    escaped[i] = a;
                }
            }
            return string.Join(" ", escaped);
        }
    }
}
