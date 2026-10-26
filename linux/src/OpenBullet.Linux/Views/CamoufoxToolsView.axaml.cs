using Avalonia.Controls;
using Avalonia.Interactivity;
using OpenBullet.Linux.Services;

namespace OpenBullet.Linux.Views;

public partial class CamoufoxToolsView : UserControl
{
    public CamoufoxToolsView()
    {
        InitializeComponent();
    }

    private void OnStopServer(object sender, RoutedEventArgs e) => CamoufoxProcessHelper.StopOwnedServer();

    private void OnKillCamoufox(object sender, RoutedEventArgs e) => CamoufoxProcessHelper.KillCamoufoxPython();

    private void OnKillFirefox(object sender, RoutedEventArgs e) => CamoufoxProcessHelper.KillPlaywrightFirefox();

    private void OnDeleteTemp(object sender, RoutedEventArgs e) => CamoufoxProcessHelper.DeleteFirefoxTempProfiles();
}
