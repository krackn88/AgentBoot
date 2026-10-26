using Avalonia.Controls;
using Avalonia.Interactivity;
using Avalonia.Media;
using OpenBullet.Linux.Services;
using OpenBullet.Linux.Views;

namespace OpenBullet.Linux;

public partial class MainWindow : Window
{
    private readonly RunnerHost _runnerHost = new();

    public MainWindow()
    {
        InitializeComponent();
        _runnerHost.LoadDefaultSmokeFixturesIfEmpty();
        ShowRunner();
    }

    private void ShowRunner()
    {
        PageHost.Content = new RunnerView { DataContext = _runnerHost };
        RunnerTab.Foreground = new SolidColorBrush(Color.Parse("#1E90FF"));
        AboutTab.Foreground = new SolidColorBrush(Color.Parse("#DCDCDC"));
    }

    private void ShowAbout()
    {
        PageHost.Content = new AboutView();
        AboutTab.Foreground = new SolidColorBrush(Color.Parse("#1E90FF"));
        RunnerTab.Foreground = new SolidColorBrush(Color.Parse("#DCDCDC"));
    }

    private void OnRunnerTab(object sender, RoutedEventArgs e) => ShowRunner();

    private void OnAboutTab(object sender, RoutedEventArgs e) => ShowAbout();
}
