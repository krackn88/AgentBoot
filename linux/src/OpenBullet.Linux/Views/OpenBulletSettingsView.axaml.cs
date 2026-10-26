using Avalonia.Controls;
using Avalonia.Interactivity;
using OpenBullet.Linux.Services;

namespace OpenBullet.Linux.Views;

public partial class OpenBulletSettingsView : UserControl
{
    private ObSettingsHost _host;

    public OpenBulletSettingsView()
    {
        InitializeComponent();
    }

    public void Attach(ObSettingsHost host) => DataContext = _host = host;

    private void OnSave(object sender, RoutedEventArgs e) => _host?.Save();

    private void OnReload(object sender, RoutedEventArgs e) => _host?.Reload();

    private void OnReset(object sender, RoutedEventArgs e) => _host?.ResetToDefaults();
}
