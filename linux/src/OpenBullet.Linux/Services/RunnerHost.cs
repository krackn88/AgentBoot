using System;
using System.IO;
using System.Linq;
using Avalonia.Threading;
using OpenBullet.Linux.Plugins;
using RuriLib;
using RuriLib.Models;
using RuriLib.Runner;
using RuriLib.ViewModels;

namespace OpenBullet.Linux.Services;

public sealed class RunnerHost : ViewModelBase
{
    private readonly Random _random = new();
    private PluginLoadResult _plugins = new();

    public RunnerViewModel Runner { get; private set; }
    public RLSettingsViewModel Settings { get; private set; }
    public EnvironmentSettings Environment { get; private set; }

    public string LogText { get; private set; } = "";
    public string PluginSummary { get; private set; } = "Plugins: 0 block(s)";
    public string StartButtonLabel { get; private set; } = "START";

    public string ConfigPath { get; set; } = "";
    public string WordlistPath { get; set; } = "";

    public RunnerHost(RuriLibSettingsHost sharedSettings = null)
    {
        LinuxPaths.EnsureLayout();
        EnsureSettingsFiles();
        Environment = IOManager.ParseEnvironmentSettings(LinuxPaths.EnvironmentIni);
        if (sharedSettings != null)
            sharedSettings.SettingsSaved += ReloadSettingsFromDisk;
        ReloadSettingsFromDisk();
        ReloadPlugins();
    }

    public void ReloadSettingsFromDisk()
    {
        Settings = File.Exists(LinuxPaths.RlSettingsJson)
            ? IOManager.LoadSettings<RLSettingsViewModel>(LinuxPaths.RlSettingsJson)
            : new RLSettingsViewModel();

        if (Runner?.Master?.Status == RuriLib.Runner.WorkerStatus.Running)
            return;

        Runner = new RunnerViewModel(Environment, Settings, _random);
        WireRunner();
        OnPropertyChanged(nameof(Runner));
        OnPropertyChanged(nameof(Settings));
    }

    public void ReloadPlugins()
    {
        _plugins = PluginLoader.Load(LinuxPaths.PluginsFolder);
        PluginSummary = $"Plugins: {_plugins.BlockPlugins.Count} block(s), {_plugins.PluginNames.Count} UI plugin(s)";
        if (_plugins.Errors.Count > 0)
            AppendLog($"Plugin load warnings: {string.Join("; ", _plugins.Errors)}");
        OnPropertyChanged(nameof(PluginSummary));
    }

    public void LoadDefaultSmokeFixturesIfEmpty()
    {
        if (!string.IsNullOrEmpty(ConfigPath) && !string.IsNullOrEmpty(WordlistPath))
            return;

        var baseDir = FindRepoLinuxDir();
        if (baseDir == null) return;

        ConfigPath = Path.Combine(baseDir, "fixtures", "smoke.loli");
        WordlistPath = Path.Combine(baseDir, "fixtures", "smoke-wordlist.txt");
        OnPropertyChanged(nameof(ConfigPath));
        OnPropertyChanged(nameof(WordlistPath));
        TryApplyConfigAndWordlist();
    }

    public void TryApplyConfigAndWordlist()
    {
        if (!File.Exists(ConfigPath) || !File.Exists(WordlistPath))
            return;

        Runner.SetConfig(IOManager.LoadConfig(ConfigPath), false);
        Runner.SetWordlist(new Wordlist(WordlistPath, Path.GetFileName(WordlistPath), "Default", ""));
        AppendLog($"Loaded config {Path.GetFileName(ConfigPath)} and wordlist {Path.GetFileName(WordlistPath)}");
    }

    public void ToggleRunner()
    {
        switch (Runner.Master.Status)
        {
            case WorkerStatus.Idle:
                if (!File.Exists(ConfigPath) || !File.Exists(WordlistPath))
                {
                    AppendLog("Select a valid config and wordlist before starting.");
                    return;
                }

                TryApplyConfigAndWordlist();
                CheckRequiredPlugins();
                StartButtonLabel = "STOP";
                OnPropertyChanged(nameof(StartButtonLabel));
                Runner.Start();
                break;

            case WorkerStatus.Running:
                Runner.Stop();
                StartButtonLabel = "HARD ABORT";
                OnPropertyChanged(nameof(StartButtonLabel));
                break;

            case WorkerStatus.Stopping:
                Runner.ForceStop();
                StartButtonLabel = "START";
                OnPropertyChanged(nameof(StartButtonLabel));
                break;
        }
    }

    private void CheckRequiredPlugins()
    {
        var available = _plugins.BlockPlugins.Select(p => p.Name).ToList();
        foreach (var required in Runner.Config.Settings.RequiredPlugins)
        {
            if (!available.Contains(required))
                throw new Exception($"Missing required plugin: {required}");
        }
    }

    private void WireRunner()
    {
        Runner.DispatchAction += (_, action) => Dispatcher.UIThread.Post(action);
        Runner.MessageArrived += (_, level, message, _, _) => AppendLog($"[{level}] {message}");
        Runner.FoundHit += (_, hit) => AppendLog($"[HIT][{hit.Type}] {hit.Data}");
        Runner.WorkerStatusChanged += _ =>
        {
            OnPropertyChanged(nameof(Runner));
            if (Runner.Master.Status == WorkerStatus.Idle)
            {
                StartButtonLabel = "START";
                OnPropertyChanged(nameof(StartButtonLabel));
                AppendLog("Runner idle.");
            }
        };
        Runner.AskCustomInputs += _ =>
        {
            // Phase 2: no modal custom-input UI yet — skip unless configs define inputs.
            Runner.CustomInputsInitialized = true;
        };
    }

    public void AppendLog(string line)
    {
        LogText = $"{DateTime.Now:HH:mm:ss} {line}{System.Environment.NewLine}{LogText}";
        if (LogText.Length > 12000)
            LogText = LogText[..12000];
        OnPropertyChanged(nameof(LogText));
    }

    private static void EnsureSettingsFiles()
    {
        if (!File.Exists(LinuxPaths.EnvironmentIni))
        {
            var defaultIni = Path.Combine(AppContext.BaseDirectory, "DefaultEnvFile.ini");
            if (File.Exists(defaultIni))
                File.Copy(defaultIni, LinuxPaths.EnvironmentIni);
        }

        if (!File.Exists(LinuxPaths.RlSettingsJson))
            IOManager.SaveSettings(LinuxPaths.RlSettingsJson, new RLSettingsViewModel());
    }

    private static string FindRepoLinuxDir()
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
