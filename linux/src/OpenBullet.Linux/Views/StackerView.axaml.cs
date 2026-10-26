using Avalonia.Controls;
using Avalonia.Interactivity;
using OpenBullet.Linux.Services;

namespace OpenBullet.Linux.Views;

public partial class StackerView : UserControl
{
    public StackerView()
    {
        InitializeComponent();
    }

    public void Attach(AppShell shell) => DataContext = shell.Stacker;

    private void OnApply(object sender, RoutedEventArgs e)
    {
        if (DataContext is StackerHost host)
            host.ApplyScriptToConfig();
    }

    private void OnScriptLostFocus(object sender, RoutedEventArgs e)
    {
        if (DataContext is StackerHost host)
            host.RefreshBlockList();
    }
}
