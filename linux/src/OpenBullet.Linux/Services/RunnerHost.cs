using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Avalonia.Controls;
using Avalonia.Threading;
using OpenBullet.Linux.Plugins;
using OpenBullet.Linux.Views;
using RuriLib;
using RuriLib.Functions.Files;
using RuriLib.Models;
using RuriLib.Runner;
using RuriLib.ViewModels;

namespace OpenBullet.Linux.Services;

public sealed class RunnerHost : ViewModelBase
{
    private readonly Random _random = new();
    private readonly HitsDbHost _hitsDb;
    private readonly ObSettingsHost _obSettings;
    private readonly StackerHost _stacker;
    private Window _inputOwner;
    private PluginLoadResult _plugins = new();

    public RunnerViewModel Runner { get; private set; }
    public RLSettingsViewModel Settings { get; private set; }
    public EnvironmentSettings Environment { get; private set; }

    public string LogText { get; private set; } = "";
    public string PluginSummary { get; private set; } = "Plugins: 0 block(s)";
    public string StartButtonLabel { get; private set; } = "START";

    public string ConfigPath { get; set; } = "";
    public string WordlistPath { get; set; } = "";

    public RunnerHitsFilter HitsFilter { get; private set; } = RunnerHitsFilter.Hits;

    public IEnumerable<ValidData> DisplayedHits
    {
        get
        {
            if (Runner == null) return Array.Empty<ValidData>();
            return HitsFilter switch
            {
                RunnerHitsFilter.Custom => Runner.CustomList,
                RunnerHitsFilter.ToCheck => Runner.ToCheckList,
                _ => Runner.HitsList
            };
        }
    }

    public bool FilterHitsActive => HitsFilter == RunnerHitsFilter.Hits;
    public bool FilterCustomActive => HitsFilter == RunnerHitsFilter.Custom;
    public bool FilterToCheckActive => HitsFilter == RunnerHitsFilter.ToCheck;

    public void SetUiOwner(Window owner) => _inputOwner = owner;

    public RunnerHost(
        RuriLibSettingsHost sharedSettings = null,
        HitsDbHost hitsDb = null,
        ObSettingsHost obSettings = null,
        StackerHost stacker = null)
    {
        _hitsDb = hitsDb;
        _obSettings = obSettings;
        _stacker = stacker;
        LinuxPaths.EnsureLayout();
        EnsureSettingsFiles();
        Environment = IOManager.ParseEnvironmentSettings(LinuxPaths.EnvironmentIni);
        if (sharedSettings != null)
            sharedSettings.SettingsSaved += ReloadSettingsFromDisk;
        ReloadSettingsFromDisk();
        ReloadPlugins();
    }

    public void SetHitsFilter(RunnerHitsFilter filter)
    {
        HitsFilter = filter;
        OnPropertyChanged(nameof(HitsFilter));
        OnPropertyChanged(nameof(DisplayedHits));
        OnPropertyChanged(nameof(FilterHitsActive));
        OnPropertyChanged(nameof(FilterCustomActive));
        OnPropertyChanged(nameof(FilterToCheckActive));
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
        Runner.FoundHit += (_, hit) =>
        {
            AppendLog($"[HIT][{hit.Type}] {hit.Data}");
            PersistHit(hit);
            TryPlayHitSound(hit);
            OnPropertyChanged(nameof(DisplayedHits));
        };
        Runner.PropertyChanged += (_, e) =>
        {
            if (e.PropertyName is "HitsList" or "CustomList" or "ToCheckList" or "HitCount" or "CustomCount" or "ToCheckCount")
            {
                OnPropertyChanged(nameof(DisplayedHits));
                OnPropertyChanged(nameof(Runner));
            }
        };
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
        Runner.AskCustomInputs += _ => Dispatcher.UIThread.Invoke(CollectCustomInputs);
    }

    public void SendHitToDebugger(ValidData hit)
    {
        if (hit == null) return;
        _stacker?.ReceiveFromRunner(hit.Data, hit.Proxy, hit.ProxyType);
        AppendLog("Sent selected hit to Stacker debugger");
    }

    private void CollectCustomInputs()
    {
        Runner.CustomInputs = new List<KeyValuePair<string, string>>();
        if (Runner.Config?.Settings?.CustomInputs == null)
        {
            Runner.CustomInputsInitialized = true;
            return;
        }

        foreach (var input in Runner.Config.Settings.CustomInputs)
        {
            var dlg = CustomInputWindow.Create(input.Description);
            var ok = dlg.ShowDialog<bool>(_inputOwner).GetAwaiter().GetResult();
            if (ok)
                Runner.CustomInputs.Add(new KeyValuePair<string, string>(input.VariableName, dlg.Answer));
        }

        Runner.CustomInputsInitialized = true;
    }

    private void TryPlayHitSound(Hit hit)
    {
        if (_obSettings?.Settings?.Sounds?.EnableSounds != true || hit.Type != "SUCCESS")
            return;
        RunnerSoundPlayer.TryPlay(Path.Combine("Sounds", _obSettings.Settings.Sounds.OnHitSound));
    }

    public void AppendLog(string line)
    {
        LogText = $"{DateTime.Now:HH:mm:ss} {line}{System.Environment.NewLine}{LogText}";
        if (LogText.Length > 12000)
            LogText = LogText[..12000];
        OnPropertyChanged(nameof(LogText));
    }

    private void PersistHit(Hit hit)
    {
        if (Runner?.Config?.Settings?.SaveHitsToTextFile == true)
        {
            try
            {
                var folderName = Path.Combine(AppContext.BaseDirectory, "Hits",
                    Files.MakeValidFileName(Runner.Config.Settings.Name));
                Directory.CreateDirectory(folderName);
                var fileName = Path.Combine(folderName, $"{hit.Type}.txt");
                File.AppendAllText(fileName, $"{hit.Data} | {hit.CapturedString}{System.Environment.NewLine}");
            }
            catch (Exception ex)
            {
                AppendLog($"Failed to write hit file: {ex.Message}");
            }

            return;
        }

        _hitsDb?.AddFromRunner(hit);
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
