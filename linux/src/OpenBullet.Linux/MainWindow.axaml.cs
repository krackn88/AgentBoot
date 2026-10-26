using System;
using System.IO;
using System.Threading.Tasks;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Interactivity;
using Avalonia.Media;
using Avalonia.Media.Imaging;
using Avalonia.Threading;
using OpenBullet.Linux.Services;
using OpenBullet.Linux.Views;

namespace OpenBullet.Linux;

public partial class MainWindow : Window
{
    private readonly AppShell _shell = new();
    private readonly ConfigsSectionView _configsSection = new();

    public MainWindow()
    {
        InitializeComponent();
        _configsSection.Attach(_shell);
        ShowRunner();
        Opened += OnOpenedCaptureScreenshot;
    }

    private void OnOpenedCaptureScreenshot(object sender, EventArgs e)
    {
        var path = Environment.GetEnvironmentVariable("OPENBULLET_SCREENSHOT");
        if (string.IsNullOrWhiteSpace(path)) return;

        Dispatcher.UIThread.Post(async () =>
        {
            await Task.Delay(800);
            var width = Math.Max(1, (int)Bounds.Width);
            var height = Math.Max(1, (int)Bounds.Height);
            var bmp = new RenderTargetBitmap(new PixelSize(width, height), new Vector(96, 96));
            bmp.Render(this);
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(path)) ?? ".");
            await using var fs = File.Create(path);
            bmp.Save(fs);
            Environment.Exit(0);
        });
    }

    private void HighlightTab(Button active)
    {
        foreach (var tab in new[] { RunnerTab, ConfigsTab, WordlistsTab, ProxiesTab, HitsTab, ToolsTab, SettingsTab, AboutTab })
        {
            tab.Foreground = new SolidColorBrush(tab == active ? Color.Parse("#1E90FF") : Color.Parse("#DCDCDC"));
        }
    }

    private void ShowRunner()
    {
        PageHost.Content = new RunnerView { DataContext = _shell.Runner };
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

    private void OnWordlistsTab(object sender, RoutedEventArgs e) => ShowPlaceholder("Wordlists — Phase 4", WordlistsTab);

    private void OnProxiesTab(object sender, RoutedEventArgs e) => ShowPlaceholder("Proxies — Phase 4", ProxiesTab);

    private void OnHitsTab(object sender, RoutedEventArgs e) => ShowPlaceholder("Hits DB — Phase 4", HitsTab);

    private void OnToolsTab(object sender, RoutedEventArgs e) => ShowTools();

    private void OnSettingsTab(object sender, RoutedEventArgs e) => ShowPlaceholder("Settings — Phase 4", SettingsTab);

    private void OnAboutTab(object sender, RoutedEventArgs e) => ShowAbout();
}
