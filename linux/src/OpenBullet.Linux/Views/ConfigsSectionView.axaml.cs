using Avalonia.Controls;
using Avalonia.Interactivity;
using Avalonia.Media;
using OpenBullet.Linux.Services;

namespace OpenBullet.Linux.Views;

public partial class ConfigsSectionView : UserControl
{
    private readonly ConfigManagerView _manager = new();
    private readonly StackerView _stacker = new();

    public ConfigsSectionView()
    {
        InitializeComponent();
        ShowManager();
    }

    private System.Action _navigateRunner;

    public void Attach(AppShell shell, System.Action navigateRunner = null)
    {
        _navigateRunner = navigateRunner;
        _manager.Attach(shell, navigateRunner);
        _stacker.Attach(shell);
    }

    private void ShowManager()
    {
        InnerHost.Content = _manager;
        ManagerTab.Foreground = new SolidColorBrush(Color.Parse("#1E90FF"));
        StackerTab.Foreground = new SolidColorBrush(Color.Parse("#DCDCDC"));
    }

    private void ShowStacker()
    {
        InnerHost.Content = _stacker;
        StackerTab.Foreground = new SolidColorBrush(Color.Parse("#1E90FF"));
        ManagerTab.Foreground = new SolidColorBrush(Color.Parse("#DCDCDC"));
    }

    private void OnManager(object sender, RoutedEventArgs e) => ShowManager();

    private void OnStacker(object sender, RoutedEventArgs e) => ShowStacker();
}
