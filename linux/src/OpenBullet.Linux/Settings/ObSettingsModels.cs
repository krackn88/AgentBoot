using System.Collections.ObjectModel;
using System.Reflection;
using RuriLib.ViewModels;

namespace OpenBullet.Linux.Settings;

/// <summary>JSON-compatible with upstream Settings/OBSettings.json (OpenBullet 1.2.2).</summary>
public sealed class ObSettingsViewModel
{
    public ObSettingsGeneral General { get; set; } = new();
    public ObSettingsSounds Sounds { get; set; } = new();
    public ObSettingsSources Sources { get; set; } = new();
    public ObSettingsThemes Themes { get; set; } = new();

    public void Reset()
    {
        General.Reset();
        Sounds.Reset();
        Sources.Reset();
        Themes.Reset();
    }
}

public sealed class ObSettingsGeneral : ViewModelBase
{
    public bool DisplayLoliScriptOnLoad { get; set; }
    public bool RecommendedBots { get; set; } = true;
    public int StartingWidth { get; set; } = 800;
    public int StartingHeight { get; set; } = 620;
    public bool ChangeRunnerInterface { get; set; }
    public bool DisableQuitWarning { get; set; }
    public bool DisableNotSavedWarning { get; set; }
    public string DefaultAuthor { get; set; } = "";
    public bool LiveConfigUpdates { get; set; }
    public bool DisableHTMLView { get; set; }
    public bool AlwaysOnTop { get; set; }
    public bool AutoCreateRunner { get; set; }
    public bool PersistDebuggerLog { get; set; }
    public bool DisableSyntaxHelper { get; set; }
    public bool DisplayCapturesLast { get; set; }
    public bool DisableCopyPasteBlocks { get; set; }
    public bool EnableLogging { get; set; }
    public bool LogToFile { get; set; }
    public int LogBufferSize { get; set; } = 10000;
    public bool BackupDB { get; set; } = true;
    public bool IgnoreWordlistOnHitDedupe { get; set; }

    public void Reset() => ObSettingsResetHelper.CopyDefaults(new ObSettingsGeneral(), this);
}

public sealed class ObSettingsSounds : ViewModelBase
{
    public bool EnableSounds { get; set; }
    public string OnHitSound { get; set; } = "rifle_hit.wav";
    public string OnReloadSound { get; set; } = "rifle_reload.wav";

    public void Reset() => ObSettingsResetHelper.CopyDefaults(new ObSettingsSounds(), this);
}

public sealed class ObSettingsSourceEntry : ViewModelBase
{
    public int Id { get; set; }
    public string ApiUrl { get; set; } = "";
    public int Auth { get; set; }
    public string ApiKey { get; set; } = "";
    public string Username { get; set; } = "";
    public string Password { get; set; } = "";
}

public sealed class ObSettingsSources : ViewModelBase
{
    public ObservableCollection<ObSettingsSourceEntry> Sources { get; set; } = new();

    public void Reset() => Sources = new ObservableCollection<ObSettingsSourceEntry>();
}

public sealed class ObSettingsThemes : ViewModelBase
{
    public string BackgroundMain { get; set; } = "#222";
    public string BackgroundSecondary { get; set; } = "#111";
    public string ForegroundMain { get; set; } = "#dcdcdc";
    public string ForegroundGood { get; set; } = "#adff2f";
    public string ForegroundBad { get; set; } = "#ff6347";
    public string ForegroundCustom { get; set; } = "#ff8c00";
    public string ForegroundRetry { get; set; } = "#ffff00";
    public string ForegroundToCheck { get; set; } = "#7fffd4";
    public string ForegroundMenuSelected { get; set; } = "#1e90ff";
    public bool UseImage { get; set; }
    public string BackgroundImage { get; set; } = "";
    public int BackgroundImageOpacity { get; set; } = 100;
    public string BackgroundLogo { get; set; } = "";
    public bool EnableSnow { get; set; }
    public int SnowAmount { get; set; } = 100;
    public bool AllowTransparency { get; set; }

    public void Reset() => ObSettingsResetHelper.CopyDefaults(new ObSettingsThemes(), this);
}

internal static class ObSettingsResetHelper
{
    internal static void CopyDefaults<T>(T defaults, T target)
    {
        foreach (var prop in typeof(T).GetProperties(BindingFlags.Public | BindingFlags.Instance))
        {
            if (!prop.CanWrite || !prop.CanRead) continue;
            prop.SetValue(target, prop.GetValue(defaults));
        }
    }
}
