using System;
using System.Linq;
using Avalonia.Controls;
using Avalonia.Interactivity;
using OpenBullet.Linux.Plugins;
using OpenBullet.Linux.Services;
using RuriLib;

namespace OpenBullet.Linux.Views;

public partial class AddBlockWindow : Window
{
    public BlockBase SelectedBlock { get; private set; }

    public AddBlockWindow()
    {
        InitializeComponent();
        RootPanel.Children.Add(new TextBlock { Text = "Default blocks", FontWeight = Avalonia.Media.FontWeight.Bold });
        AddBlockButton("Request", () => new BlockRequest());
        AddBlockButton("Keycheck", () => new BlockKeycheck());
        AddBlockButton("Parse", () => new BlockParse());
        AddBlockButton("Utility", () => new BlockUtility());
        AddBlockButton("Function", () => new BlockFunction());

        var plugins = PluginLoader.Load(LinuxPaths.PluginsFolder).BlockPlugins;
        if (plugins.Any())
        {
            RootPanel.Children.Add(new TextBlock { Text = "Block plugins", FontWeight = Avalonia.Media.FontWeight.Bold, Margin = new Avalonia.Thickness(0, 8, 0, 0) });
            foreach (var p in plugins)
            {
                var type = p.GetType();
                AddBlockButton(p.Name, () => Activator.CreateInstance(type) as BlockBase);
            }
        }
    }

    private void AddBlockButton(string label, Func<BlockBase> factory)
    {
        var btn = new Button { Content = label, HorizontalAlignment = Avalonia.Layout.HorizontalAlignment.Stretch };
        btn.Click += (_, _) =>
        {
            SelectedBlock = factory();
            Close(true);
        };
        RootPanel.Children.Add(btn);
    }
}
