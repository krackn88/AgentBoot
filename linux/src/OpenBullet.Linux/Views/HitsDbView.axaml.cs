using System.Linq;
using Avalonia.Controls;
using Avalonia.Interactivity;
using Avalonia.Platform.Storage;
using OpenBullet.Linux.Services;
using RuriLib.Models;

namespace OpenBullet.Linux.Views;

public partial class HitsDbView : UserControl
{
    private HitsDbHost _host;

    public HitsDbView()
    {
        InitializeComponent();
    }

    public void Attach(HitsDbHost host) => DataContext = _host = host;

    private void OnRefresh(object sender, RoutedEventArgs e) => _host?.Refresh();

    private void OnDelete(object sender, RoutedEventArgs e)
    {
        var selected = HitsList.SelectedItems?.Cast<Hit>().ToList();
        if (selected?.Count > 0)
            _host?.DeleteSelected(selected);
    }

    private void OnDeleteAll(object sender, RoutedEventArgs e) => _host?.DeleteAll();

    private async void OnExport(object sender, RoutedEventArgs e) => await ExportAsync(false);

    private async void OnExportFull(object sender, RoutedEventArgs e) => await ExportAsync(true);

    private async System.Threading.Tasks.Task ExportAsync(bool full)
    {
        var selected = HitsList.SelectedItems?.Cast<Hit>().ToList();
        if (selected == null || selected.Count == 0) return;
        var top = TopLevel.GetTopLevel(this);
        var file = await top.StorageProvider.SaveFilePickerAsync(new FilePickerSaveOptions
        {
            Title = "Export hits",
            DefaultExtension = "txt",
            SuggestedFileName = "hits.txt"
        });
        if (file != null)
            _host?.ExportSelected(selected, file.Path.LocalPath, full);
    }
}
