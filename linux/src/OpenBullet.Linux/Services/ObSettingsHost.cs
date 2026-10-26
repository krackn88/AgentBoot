using System;
using System.IO;
using Newtonsoft.Json;
using OpenBullet.Linux.Settings;
using RuriLib.ViewModels;

namespace OpenBullet.Linux.Services;

public sealed class ObSettingsHost : ViewModelBase
{
    public ObSettingsViewModel Settings { get; private set; }
    public string StatusMessage { get; private set; } = "";

    public event Action SettingsSaved;

    public ObSettingsHost()
    {
        Reload();
    }

    public static void ApplyThemeFromDisk()
    {
        var themes = File.Exists(LinuxPaths.ObSettingsJson)
            ? ObSettingsIo.Load(LinuxPaths.ObSettingsJson).Themes
            : new Settings.ObSettingsThemes();
        ObThemeRuntime.Apply(themes);
    }

    public void Reload()
    {
        Settings = File.Exists(LinuxPaths.ObSettingsJson)
            ? ObSettingsIo.Load(LinuxPaths.ObSettingsJson)
            : new ObSettingsViewModel();
        OnPropertyChanged(nameof(Settings));
        SetStatus("OpenBullet settings loaded");
    }

    public void Save()
    {
        LinuxPaths.EnsureLayout();
        ObSettingsIo.Save(LinuxPaths.ObSettingsJson, Settings);
        ObThemeRuntime.Apply(Settings.Themes);
        SetStatus($"Saved {LinuxPaths.ObSettingsJson}");
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

internal static class ObSettingsIo
{
    private static readonly JsonSerializerSettings JsonSettings = new()
    {
        Formatting = Formatting.Indented,
        TypeNameHandling = TypeNameHandling.Auto
    };

    public static void Save(string path, ObSettingsViewModel settings) =>
        File.WriteAllText(path, JsonConvert.SerializeObject(settings, JsonSettings));

    public static ObSettingsViewModel Load(string path) =>
        JsonConvert.DeserializeObject<ObSettingsViewModel>(File.ReadAllText(path), JsonSettings)
        ?? new ObSettingsViewModel();
}
