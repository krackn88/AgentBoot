using System;
using Avalonia;
using Avalonia.Media;
using OpenBullet.Linux.Settings;

namespace OpenBullet.Linux.Services;

/// <summary>Applies OB theme color strings to application resources (MetroDark palette).</summary>
public static class ObThemeRuntime
{
    public static void Apply(ObSettingsThemes themes)
    {
        if (themes == null || Application.Current == null) return;

        SetBrush("ObBackgroundMain", themes.BackgroundMain);
        SetBrush("ObBackgroundSecondary", themes.BackgroundSecondary);
        SetBrush("ObForegroundMain", themes.ForegroundMain);
        SetBrush("ObForegroundGood", themes.ForegroundGood);
        SetBrush("ObForegroundBad", themes.ForegroundBad);
        SetBrush("ObForegroundCustom", themes.ForegroundCustom);
        SetBrush("ObForegroundRetry", themes.ForegroundRetry);
        SetBrush("ObForegroundToCheck", themes.ForegroundToCheck);
        SetBrush("ObForegroundMenuSelected", themes.ForegroundMenuSelected);
    }

    private static void SetBrush(string key, string htmlColor)
    {
        try
        {
            Application.Current.Resources[key] = new SolidColorBrush(Color.Parse(htmlColor));
        }
        catch
        {
            // ignore invalid color strings
        }
    }
}
