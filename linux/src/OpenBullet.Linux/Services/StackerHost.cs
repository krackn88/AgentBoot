using System;
using System.Collections.ObjectModel;
using System.Linq;
using RuriLib;
using RuriLib.LS;
using RuriLib.ViewModels;

namespace OpenBullet.Linux.Services;

public sealed class StackerHost : ViewModelBase
{
    public ConfigViewModel Config { get; private set; }

    private string _script = "";
    public string Script
    {
        get => _script;
        set
        {
            _script = value ?? "";
            OnPropertyChanged(nameof(Script));
            RefreshBlockList();
        }
    }

    public ObservableCollection<string> BlockLines { get; } = new();
    public string ConfigTitle => Config == null ? "(no config loaded)" : Config.Name;
    public string StatusMessage { get; private set; } = "";

    public void BindConfig(ConfigViewModel config)
    {
        Config = config;
        Script = config?.Config?.Script ?? "";
        OnPropertyChanged(nameof(ConfigTitle));
        SetStatus(config == null ? "Load a config from Manager" : $"Editing {config.Name}");
    }

    public void ApplyScriptToConfig()
    {
        if (Config?.Config == null) return;
        Config.Config.Script = Script;
        Config.Config.Settings.LastModified = DateTime.Now;
        SetStatus("Script applied to in-memory config (use Manager → Save)");
    }

    public void RefreshBlockList()
    {
        BlockLines.Clear();
        if (string.IsNullOrWhiteSpace(Script)) return;

        try
        {
            var blocks = new LoliScript(Script).ToBlocks();
            foreach (var block in blocks)
            {
                var kind = block.GetType().Name;
                if (kind.StartsWith("Block", StringComparison.Ordinal))
                    kind = kind["Block".Length..];
                var line = block.Disabled ? $"[OFF] {kind}: {block.Label}" : $"{kind}: {block.Label}";
                BlockLines.Add(line);
            }
        }
        catch (Exception ex)
        {
            BlockLines.Add($"Parse error: {ex.Message}");
        }
    }

    private void SetStatus(string message)
    {
        StatusMessage = message;
        OnPropertyChanged(nameof(StatusMessage));
    }
}
