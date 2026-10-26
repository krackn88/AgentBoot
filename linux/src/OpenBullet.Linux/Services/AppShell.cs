using System.IO;
using RuriLib.Models;
using RuriLib.ViewModels;

namespace OpenBullet.Linux.Services;

/// <summary>Shared app state for Runner, Configs, and Stacker.</summary>
public sealed class AppShell
{
    public RunnerHost Runner { get; } = new();
    public ConfigManagerHost Configs { get; } = new();
    public StackerHost Stacker { get; } = new();
    public WordlistManagerHost Wordlists { get; } = new();

    public AppShell()
    {
        LinuxPaths.EnsureLayout();
        Configs.EnsureSmokeFixtureImported();
        EnsureSmokeWordlistImported();
        Runner.LoadDefaultSmokeFixturesIfEmpty();
    }

    private static void EnsureSmokeWordlistImported()
    {
        var smokePath = Path.Combine(LinuxPaths.FindRepoLinuxDir() ?? "", "fixtures", "smoke-wordlist.txt");
        if (!File.Exists(smokePath)) return;
        var dest = Path.Combine(LinuxPaths.WordlistsFolder, "smoke-wordlist.txt");
        if (!File.Exists(dest))
            File.Copy(smokePath, dest);
    }

    public void LoadConfigIntoRunner(ConfigViewModel config, Wordlist wordlist = null)
    {
        if (config?.Config == null) return;
        var path = Path.Combine(LinuxPaths.ConfigsFolder, $"{config.FileName}.loli");
        if (File.Exists(path))
            Runner.ConfigPath = path;

        wordlist ??= Wordlists.Selected;
        if (wordlist != null && File.Exists(wordlist.Path))
            Runner.WordlistPath = wordlist.Path;

        Runner.TryApplyConfigAndWordlist();
    }
}
