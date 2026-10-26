using Avalonia.Controls;
using Avalonia.Interactivity;
using OpenBullet.Linux.Services;

namespace OpenBullet.Linux.Views;

public partial class PluginsView : UserControl
{
    private PluginUiHost _host;

    public PluginsView()
    {
        InitializeComponent();
    }

    public void Attach(PluginUiHost host)
    {
        _host = host;
        DataContext = host;
        host.Reload();
    }

    private void OnReload(object sender, RoutedEventArgs e) => _host?.Reload();
}
