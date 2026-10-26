using System.IO;
using RuriLib.ViewModels;

namespace OpenBullet.Linux.Services;

/// <summary>Shared app state for Runner, Configs, and Stacker.</summary>
public sealed class AppShell
{
    public RunnerHost Runner { get; } = new();
    public ConfigManagerHost Configs { get; } = new();
    public StackerHost Stacker { get; } = new();

    public AppShell()
    {
        LinuxPaths.EnsureLayout();
        Configs.EnsureSmokeFixtureImported();
        Runner.LoadDefaultSmokeFixturesIfEmpty();
    }

    public void LoadConfigIntoRunner(ConfigViewModel config)
    {
        if (config?.Config == null) return;
        var path = Path.Combine(LinuxPaths.ConfigsFolder, $"{config.FileName}.loli");
        if (File.Exists(path))
            Runner.ConfigPath = path;
        Runner.TryApplyConfigAndWordlist();
    }
}
