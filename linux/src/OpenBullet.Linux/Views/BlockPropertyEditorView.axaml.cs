using Avalonia.Controls;
using Avalonia.Interactivity;
using OpenBullet.Linux.Services;

namespace OpenBullet.Linux.Views;

public partial class BlockPropertyEditorView : UserControl
{
    private BlockPropertyEditorHost _host;

    public BlockPropertyEditorView()
    {
        InitializeComponent();
    }

    public void Attach(BlockPropertyEditorHost host) => DataContext = _host = host;

    private void OnFieldLostFocus(object sender, RoutedEventArgs e)
    {
        if (sender is TextBox box && box.DataContext is BlockPropertyRow row)
            _host?.ApplyRow(row);
    }

    private void OnBoolChanged(object sender, RoutedEventArgs e)
    {
        if (sender is CheckBox cb && cb.DataContext is BlockPropertyRow row)
        {
            row.BoolValue = cb.IsChecked == true;
            _host?.ApplyRow(row);
        }
    }

    private void OnEnumChanged(object sender, SelectionChangedEventArgs e)
    {
        if (sender is ComboBox combo && combo.DataContext is BlockPropertyRow row && combo.SelectedItem is string s)
        {
            row.Value = s;
            _host?.ApplyRow(row);
        }
    }
}
