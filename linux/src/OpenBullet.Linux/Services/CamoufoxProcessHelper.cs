using System;
using System.Diagnostics;
using System.IO;
using RuriLib.Camoufox;

namespace OpenBullet.Linux.Services;

/// <summary>Process cleanup for Camoufox / Playwright Firefox (Linux port).</summary>
public static class CamoufoxProcessHelper
{
    public static void StopOwnedServer() => CamoufoxLauncher.StopServerIfOwned();

    public static void KillCamoufoxPython()
    {
        KillByPattern("camoufox");
        KillByPattern("python3 -m camoufox");
    }

    public static void KillPlaywrightFirefox()
    {
        KillByPattern("firefox");
        KillByPattern("camoufox");
    }

    public static void DeleteFirefoxTempProfiles()
    {
        var temp = Path.GetTempPath();
        foreach (var dir in Directory.EnumerateDirectories(temp))
        {
            var name = Path.GetFileName(dir);
            if (name.Contains("rust_mozprofile", StringComparison.OrdinalIgnoreCase)
                || name.Contains("playwright", StringComparison.OrdinalIgnoreCase))
            {
                try { Directory.Delete(dir, true); } catch { }
            }
        }
    }

    private static void KillByPattern(string pattern)
    {
        try
        {
            Process.Start(new ProcessStartInfo("pkill", $"-f {pattern}")
            {
                CreateNoWindow = true,
                UseShellExecute = false
            })?.WaitForExit(3000);
        }
        catch
        {
            // Best-effort cleanup.
        }
    }
}
