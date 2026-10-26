using System.Linq;
using Avalonia.Controls;
using Avalonia.Interactivity;
using OpenBullet.Linux.Services;
using RuriLib.ViewModels;

namespace OpenBullet.Linux.Views;

public partial class ConfigManagerView : UserControl
{
    private AppShell _shell;
    private System.Action _navigateRunner;

    public ConfigManagerView()
    {
        InitializeComponent();
    }

    public void Attach(AppShell shell, System.Action navigateRunner = null)
    {
        _shell = shell;
        _navigateRunner = navigateRunner;
        DataContext = shell.Configs;
    }

    private ConfigManagerHost Host => _shell?.Configs;

    private void OnNew(object sender, RoutedEventArgs e) => Host?.CreateNew(null);

    private void OnEdit(object sender, RoutedEventArgs e)
    {
        if (ConfigList.SelectedItem is ConfigViewModel vm)
            Host?.LoadSelected(vm);
    }

    private void OnSave(object sender, RoutedEventArgs e) => Host?.SaveCurrent();

    private void OnDelete(object sender, RoutedEventArgs e)
    {
        var selected = ConfigList.SelectedItems?.Cast<ConfigViewModel>().ToList();
        if (selected?.Count > 0)
            Host?.DeleteSelected(selected);
    }

    private void OnRescan(object sender, RoutedEventArgs e) => Host?.Rescan();

    private void OnOpenInRunner(object sender, RoutedEventArgs e)
    {
        var vm = ConfigList.SelectedItem as ConfigViewModel ?? Host?.CurrentConfig;
        if (vm == null) return;
        _shell?.LoadConfigIntoRunner(vm);
        _navigateRunner?.Invoke();
    }

    private void OnSelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (ConfigList.SelectedItem is ConfigViewModel vm)
        {
            Host?.Select(vm);
            _shell?.Stacker.BindConfig(vm);
        }
    }
}
