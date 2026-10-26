using System;
using Avalonia.Controls;
using Avalonia.Interactivity;
using OpenBullet.Linux.Services;

namespace OpenBullet.Linux.Views;

public partial class RunnerView : UserControl
{
    public RunnerView()
    {
        InitializeComponent();
    }

    private RunnerHost Host => DataContext as RunnerHost;

    private void OnLoadClicked(object sender, RoutedEventArgs e) => Host?.TryApplyConfigAndWordlist();

    private void OnStartClicked(object sender, RoutedEventArgs e)
    {
        try
        {
            Host?.ToggleRunner();
        }
        catch (Exception ex)
        {
            Host?.AppendLog($"ERROR: {ex.Message}");
        }
    }

    private void OnStopCamoufoxServer(object sender, RoutedEventArgs e) => CamoufoxProcessHelper.StopOwnedServer();

    private void OnKillCamoufox(object sender, RoutedEventArgs e) => CamoufoxProcessHelper.KillCamoufoxPython();

    private void OnReloadPlugins(object sender, RoutedEventArgs e) => Host?.ReloadPlugins();
}
