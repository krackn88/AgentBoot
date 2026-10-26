using System;
using System.Collections.ObjectModel;
using System.Linq;
using Avalonia.Controls;
using OpenBullet.Linux.Plugins;
using RuriLib.ViewModels;

namespace OpenBullet.Linux.Services;

public sealed class PluginUiHost : ViewModelBase
{
    public ObservableCollection<PluginUiEntry> Plugins { get; } = new();
    public string StatusMessage { get; private set; } = "";

    private LinuxApplicationBridge _app;

    public void Attach(LinuxApplicationBridge app) => _app = app;

    public void Reload()
    {
        Plugins.Clear();
        var result = PluginLoader.Load(LinuxPaths.PluginsFolder);
        if (_app == null)
        {
            StatusMessage = "Plugin host not attached to application bridge";
            OnPropertyChanged(nameof(StatusMessage));
            return;
        }

        var app = _app;
        foreach (var type in result.UiPluginTypes)
        {
            try
            {
                var (_, panel) = PluginUiFactory.Build(type, app);
                Plugins.Add(new PluginUiEntry(type.Name, panel));
            }
            catch (Exception ex)
            {
                Plugins.Add(new PluginUiEntry(type.Name, new TextBlock { Text = ex.Message }));
            }
        }

        StatusMessage = result.UiPluginTypes.Count == 0
            ? "No IPlugin UI assemblies in Plugins/ (block plugins are separate)"
            : $"Loaded {result.UiPluginTypes.Count} UI plugin(s)";
        OnPropertyChanged(nameof(StatusMessage));
    }
}

public sealed class PluginUiEntry
{
    public PluginUiEntry(string name, Control content)
    {
        Name = name;
        Content = content;
    }

    public string Name { get; }
    public Control Content { get; }
}
