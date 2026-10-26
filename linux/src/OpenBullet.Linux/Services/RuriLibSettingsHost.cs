using System;
using System.IO;
using RuriLib;
using RuriLib.ViewModels;

namespace OpenBullet.Linux.Services;

public sealed class RuriLibSettingsHost : ViewModelBase
{
    public RLSettingsViewModel Settings { get; private set; }

    public string StatusMessage { get; private set; } = "";

    public event Action SettingsSaved;

    public RuriLibSettingsHost()
    {
        Reload();
    }

    public void Reload()
    {
        Settings = File.Exists(LinuxPaths.RlSettingsJson)
            ? IOManager.LoadSettings<RLSettingsViewModel>(LinuxPaths.RlSettingsJson)
            : new RLSettingsViewModel();
        OnPropertyChanged(nameof(Settings));
        SetStatus("Settings loaded");
    }

    public void Save()
    {
        LinuxPaths.EnsureLayout();
        IOManager.SaveSettings(LinuxPaths.RlSettingsJson, Settings);
        SetStatus($"Saved {LinuxPaths.RlSettingsJson}");
        SettingsSaved?.Invoke();
    }

    public void ResetToDefaults()
    {
        Settings.Reset();
        OnPropertyChanged(nameof(Settings));
        SetStatus("Reset to defaults (not saved yet)");
    }

    private void SetStatus(string msg)
    {
        StatusMessage = msg;
        OnPropertyChanged(nameof(StatusMessage));
    }
}
