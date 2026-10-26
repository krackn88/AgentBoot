using System.Linq;
using Avalonia.Controls;
using Avalonia.Interactivity;
using Avalonia.Platform.Storage;
using OpenBullet.Linux.Services;
using RuriLib.Models;

namespace OpenBullet.Linux.Views;

public partial class ProxyManagerView : UserControl
{
    private ProxyManagerHost _host;

    public ProxyManagerView()
    {
        InitializeComponent();
    }

    public void Attach(ProxyManagerHost host) => DataContext = _host = host;

    private async void OnImport(object sender, RoutedEventArgs e)
    {
        var top = TopLevel.GetTopLevel(this);
        var files = await top.StorageProvider.OpenFilePickerAsync(new FilePickerOpenOptions
        {
            Title = "Import proxies",
            AllowMultiple = false,
            FileTypeFilter = new[] { new FilePickerFileType("Text") { Patterns = new[] { "*.txt" } } }
        });
        var file = files.FirstOrDefault();
        if (file != null)
            _host?.ImportFile(file.Path.LocalPath);
    }

    private async void OnCheck(object sender, RoutedEventArgs e)
    {
        if (_host == null) return;
        CheckButton.Content = _host.IsChecking ? "ABORT" : "CHECK";
        await _host.ToggleCheckAsync();
        CheckButton.Content = "CHECK";
    }

    private void OnDelete(object sender, RoutedEventArgs e)
    {
        var selected = ProxyList.SelectedItems?.Cast<CProxy>().ToList();
        if (selected?.Count > 0)
            _host?.DeleteSelected(selected);
    }

    private void OnDeleteAll(object sender, RoutedEventArgs e) => _host?.DeleteAll();

    private void OnDeleteBad(object sender, RoutedEventArgs e) => _host?.DeleteNotWorking();

    private async void OnExport(object sender, RoutedEventArgs e)
    {
        var selected = ProxyList.SelectedItems?.Cast<CProxy>().ToList();
        if (selected == null || selected.Count == 0) return;
        var top = TopLevel.GetTopLevel(this);
        var file = await top.StorageProvider.SaveFilePickerAsync(new FilePickerSaveOptions
        {
            Title = "Export proxies",
            DefaultExtension = "txt",
            SuggestedFileName = "proxies.txt"
        });
        if (file != null)
            _host?.ExportSelected(selected, file.Path.LocalPath);
    }

    private void OnRefresh(object sender, RoutedEventArgs e) => _host?.Refresh();
}
