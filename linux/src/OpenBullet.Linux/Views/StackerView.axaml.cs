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
        BlockEditor.Attach(_host.BlockEditor);
        _host.PropertyChanged += OnHostPropertyChanged;
        _host.Debugger.PropertyChanged += OnDebuggerPropertyChanged;
        SyncEditorFromHost();
    }

    private void OnDebuggerPropertyChanged(object sender, PropertyChangedEventArgs e)
    {
        if (e.PropertyName == nameof(StackerDebuggerHost.IsRunning))
            DebuggerButton.Content = _host.Debugger.IsRunning ? "Abort" : "Start";
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

    private async void OnAddBlock(object sender, RoutedEventArgs e)
    {
        var win = new AddBlockWindow();
        var owner = TopLevel.GetTopLevel(this) as Window;
        if (owner == null) return;
        var ok = await win.ShowDialog<bool>(owner);
        if (ok && win.SelectedBlock != null)
            _host?.AddBlock(win.SelectedBlock);
    }

    private void OnRemoveBlock(object sender, RoutedEventArgs e) => _host?.RemoveSelectedBlocks();

    private void OnMoveUp(object sender, RoutedEventArgs e) => _host?.MoveSelectedUp();

    private void OnMoveDown(object sender, RoutedEventArgs e) => _host?.MoveSelectedDown();

    private async void OnDebuggerToggle(object sender, RoutedEventArgs e)
    {
        if (_host == null) return;
        await _host.Debugger.ToggleRunAsync(_host);
        DebuggerButton.Content = _host.Debugger.IsRunning ? "Abort" : "Start";
    }
}
