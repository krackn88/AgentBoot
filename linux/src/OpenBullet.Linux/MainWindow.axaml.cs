using Avalonia.Controls;
using Avalonia.Interactivity;
using Avalonia.Media;
using OpenBullet.Linux.Services;
using OpenBullet.Linux.Views;

namespace OpenBullet.Linux;

public partial class MainWindow : Window
{
    private readonly AppShell _shell = new();
    private readonly ConfigsSectionView _configsSection = new();
    private readonly WordlistManagerView _wordlistsView = new();
    private readonly ProxyManagerView _proxiesView = new();
    private readonly HitsDbView _hitsView = new();
    private readonly SettingsHubView _settingsView = new();
    private readonly PluginsView _pluginsView = new();
    private readonly RunnerView _runnerView = new();

    public MainWindow()
    {
        InitializeComponent();
        _shell.Runner.SetUiOwner(this);
        _runnerView.DataContext = _shell.Runner;
        _configsSection.Attach(_shell, ShowRunner);
        _wordlistsView.Attach(_shell.Wordlists);
        _proxiesView.Attach(_shell.Proxies);
        _hitsView.Attach(_shell.Hits);
        _settingsView.Attach(_shell.RuriSettings, _shell.ObSettings);
        _shell.PluginUi.Attach(_shell.Application);
        _pluginsView.Attach(_shell.PluginUi);
        ShowRunner();
        ScreenshotCapture.Schedule(this, PageHost);
    }

    private void HighlightTab(Button active)
    {
        foreach (var tab in new[] { RunnerTab, ConfigsTab, WordlistsTab, ProxiesTab, HitsTab, PluginsTab, ToolsTab, SettingsTab, AboutTab })
        {
            tab.Foreground = new SolidColorBrush(tab == active ? Color.Parse("#1E90FF") : Color.Parse("#DCDCDC"));
        }
    }

    private void ShowRunner()
    {
        PageHost.Content = _runnerView;
        HighlightTab(RunnerTab);
    }

    private void ShowConfigs()
    {
        PageHost.Content = _configsSection;
        HighlightTab(ConfigsTab);
    }

    private void ShowPlaceholder(string title, Button tab)
    {
        PageHost.Content = new PlaceholderView(title);
        HighlightTab(tab);
    }

    private void ShowTools()
    {
        PageHost.Content = new CamoufoxToolsView();
        HighlightTab(ToolsTab);
    }

    private void ShowAbout()
    {
        PageHost.Content = new AboutView();
        HighlightTab(AboutTab);
    }

    private void OnRunnerTab(object sender, RoutedEventArgs e) => ShowRunner();

    private void OnConfigsTab(object sender, RoutedEventArgs e) => ShowConfigs();

    private void OnWordlistsTab(object sender, RoutedEventArgs e)
    {
        PageHost.Content = _wordlistsView;
        HighlightTab(WordlistsTab);
    }

    private void OnProxiesTab(object sender, RoutedEventArgs e)
    {
        PageHost.Content = _proxiesView;
        HighlightTab(ProxiesTab);
    }

    private void OnHitsTab(object sender, RoutedEventArgs e)
    {
        PageHost.Content = _hitsView;
        HighlightTab(HitsTab);
    }

    private void OnPluginsTab(object sender, RoutedEventArgs e)
    {
        PageHost.Content = _pluginsView;
        HighlightTab(PluginsTab);
    }

    private void OnToolsTab(object sender, RoutedEventArgs e) => ShowTools();

    private void OnSettingsTab(object sender, RoutedEventArgs e)
    {
        PageHost.Content = _settingsView;
        HighlightTab(SettingsTab);
    }

    private void OnAboutTab(object sender, RoutedEventArgs e) => ShowAbout();
}
