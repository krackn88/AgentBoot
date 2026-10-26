using System;
using System.IO;

namespace OpenBullet.Linux.Services;

public static class LinuxPaths
{
    public static string PluginsFolder => Path.Combine(AppContext.BaseDirectory, "Plugins");
    public static string SettingsFolder => Path.Combine(AppContext.BaseDirectory, "Settings");
    public static string EnvironmentIni => Path.Combine(SettingsFolder, "Environment.ini");
    public static string RlSettingsJson => Path.Combine(SettingsFolder, "RLSettings.json");

    public static void EnsureLayout()
    {
        Directory.CreateDirectory(PluginsFolder);
        Directory.CreateDirectory(SettingsFolder);
    }
}
