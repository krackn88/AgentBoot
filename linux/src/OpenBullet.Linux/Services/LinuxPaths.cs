using System;
using System.IO;

namespace OpenBullet.Linux.Services;

public static class LinuxPaths
{
    public static string PluginsFolder => Path.Combine(AppContext.BaseDirectory, "Plugins");
    public static string SettingsFolder => Path.Combine(AppContext.BaseDirectory, "Settings");
    public static string ConfigsFolder => Path.Combine(AppContext.BaseDirectory, "Configs");
    public static string EnvironmentIni => Path.Combine(SettingsFolder, "Environment.ini");
    public static string RlSettingsJson => Path.Combine(SettingsFolder, "RLSettings.json");

    public static void EnsureLayout()
    {
        Directory.CreateDirectory(PluginsFolder);
        Directory.CreateDirectory(SettingsFolder);
        Directory.CreateDirectory(ConfigsFolder);
    }

    public static string FindRepoLinuxDir()
    {
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        for (var i = 0; i < 8 && dir != null; i++, dir = dir.Parent)
        {
            if (Directory.Exists(Path.Combine(dir.FullName, "fixtures")))
                return dir.FullName;
        }

        return null;
    }
}
