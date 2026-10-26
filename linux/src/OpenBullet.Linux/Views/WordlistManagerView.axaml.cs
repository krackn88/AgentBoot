using System.Linq;
using Avalonia.Controls;
using Avalonia.Interactivity;
using Avalonia.Platform.Storage;
using OpenBullet.Linux.Services;
using RuriLib.Models;

namespace OpenBullet.Linux.Views;

public partial class WordlistManagerView : UserControl
{
    private WordlistManagerHost _host;

    public WordlistManagerView()
    {
        InitializeComponent();
    }

    public void Attach(WordlistManagerHost host) => DataContext = _host = host;

    private async void OnAdd(object sender, RoutedEventArgs e)
    {
        var top = TopLevel.GetTopLevel(this);
        if (top?.StorageProvider == null) return;
        var files = await top.StorageProvider.OpenFilePickerAsync(new FilePickerOpenOptions
        {
            Title = "Add wordlist",
            AllowMultiple = false,
            FileTypeFilter = new[] { new FilePickerFileType("Text") { Patterns = new[] { "*.txt" } } }
        });
        var file = files.FirstOrDefault();
        if (file == null) return;
        _host?.AddFromPath(file.Path.LocalPath);
    }

    private void OnDelete(object sender, RoutedEventArgs e)
    {
        if (WordlistList.SelectedItem is Wordlist wl)
            _host?.DeleteSelected(wl);
    }

    private void OnRescan(object sender, RoutedEventArgs e) => _host?.RefreshView();

    private void OnDeleteMissing(object sender, RoutedEventArgs e) => _host?.DeleteNotFound();

    private void OnSelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (WordlistList.SelectedItem is Wordlist wl)
            _host?.Select(wl);
    }
}
