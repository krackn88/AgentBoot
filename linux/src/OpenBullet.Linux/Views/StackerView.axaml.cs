using System.ComponentModel;
using Avalonia.Controls;
using Avalonia.Interactivity;
using OpenBullet.Linux.Services;

namespace OpenBullet.Linux.Views;

public partial class StackerView : UserControl
{
    private StackerHost _host;
    private bool _syncingEditor;

    public StackerView()
    {
        InitializeComponent();
        ScriptEditor.TextChanged += OnEditorTextChanged;
    }

    public void Attach(AppShell shell)
    {
        _host = shell.Stacker;
        DataContext = _host;
        _host.PropertyChanged += OnHostPropertyChanged;
        SyncEditorFromHost();
    }

    private void OnHostPropertyChanged(object sender, PropertyChangedEventArgs e)
    {
        if (e.PropertyName == nameof(StackerHost.Script))
            SyncEditorFromHost();
    }

    private void SyncEditorFromHost()
    {
        if (_host == null) return;
        _syncingEditor = true;
        ScriptEditor.Text = _host.Script ?? "";
        _syncingEditor = false;
    }

    private void OnEditorTextChanged(object sender, System.EventArgs e)
    {
        if (_syncingEditor || _host == null) return;
        _host.Script = ScriptEditor.Text;
    }

    private void OnApply(object sender, RoutedEventArgs e) => _host?.ApplyScriptToConfig();
}
