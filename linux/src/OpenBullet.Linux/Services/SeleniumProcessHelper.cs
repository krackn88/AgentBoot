using System.Diagnostics;
using System.Runtime.InteropServices;

namespace OpenBullet.Linux.Services;

/// <summary>Cross-platform replacements for upstream SeleniumTools Win32 taskkill usage.</summary>
public static class SeleniumProcessHelper
{
    public static void KillChromedriver() => KillByName("chromedriver");

    public static void KillGeckodriver() => KillByName("geckodriver");

    public static void KillChrome() => KillByName(RuntimeInformation.IsOSPlatform(OSPlatform.Windows) ? "chrome" : "chrome");

    public static void KillFirefox() => KillByName(RuntimeInformation.IsOSPlatform(OSPlatform.Windows) ? "firefox" : "firefox");

    private static void KillByName(string processName)
    {
        if (RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
        {
            Process.Start(new ProcessStartInfo("taskkill", $"/F /IM {processName}.exe /T")
            {
                CreateNoWindow = true,
                UseShellExecute = false
            });
            return;
        }

        try
        {
            Process.Start(new ProcessStartInfo("pkill", $"-f {processName}")
            {
                CreateNoWindow = true,
                UseShellExecute = false
            })?.WaitForExit(5000);
        }
        catch
        {
            // Best-effort cleanup for dev tools UI.
        }
    }
}
