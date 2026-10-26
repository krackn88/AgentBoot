using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Linq;
using Extreme.Net;
using RuriLib;
using RuriLib.LS;
using RuriLib.ViewModels;

namespace OpenBullet.Linux.Services;

public sealed class StackerHost : ViewModelBase
{
    private readonly List<BlockBase> _blocks = new();
    private bool _syncingScript;

    public ConfigViewModel Config { get; private set; }
    public StackerDebuggerHost Debugger { get; } = new();

    private string _script = "";
    public string Script
    {
        get => _script;
        set
        {
            _script = value ?? "";
            OnPropertyChanged(nameof(Script));
            if (!_syncingScript)
                ReloadBlocksFromScript();
        }
    }

    public ObservableCollection<BlockStackItem> Blocks { get; } = new();
    private BlockStackItem _selectedBlock;
    public BlockStackItem SelectedBlock
    {
        get => _selectedBlock;
        set
        {
            _selectedBlock = value;
            OnPropertyChanged(nameof(SelectedBlock));
        }
    }

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

    public void ReloadBlocksFromScript()
    {
        _blocks.Clear();
        Blocks.Clear();
        if (string.IsNullOrWhiteSpace(Script)) return;

        try
        {
            _blocks.AddRange(new LoliScript(Script).ToBlocks());
            RebuildBlockItems();
        }
        catch (Exception ex)
        {
            SetStatus($"Parse error: {ex.Message}");
        }
    }

    public void PushBlocksToScript()
    {
        var ls = new LoliScript();
        ls.FromBlocks(_blocks);
        _syncingScript = true;
        Script = ls.Script;
        _syncingScript = false;
        RebuildBlockItems();
    }

    public void AddBlock(BlockBase block)
    {
        if (block == null) return;
        var idx = SelectedBlock != null ? Blocks.IndexOf(SelectedBlock) + 1 : _blocks.Count;
        if (idx < 0 || idx > _blocks.Count) idx = _blocks.Count;
        _blocks.Insert(idx, block);
        PushBlocksToScript();
        SetStatus($"Added {block.GetType().Name}");
    }

    public void RemoveSelectedBlocks()
    {
        var selected = Blocks.Where(b => b == SelectedBlock).ToList();
        if (selected.Count == 0 && SelectedBlock != null)
            selected.Add(SelectedBlock);
        foreach (var item in selected.ToList())
            _blocks.Remove(item.Block);
        PushBlocksToScript();
        SetStatus("Removed block(s)");
    }

    public void MoveSelectedUp()
    {
        if (SelectedBlock == null) return;
        var i = _blocks.IndexOf(SelectedBlock.Block);
        if (i <= 0) return;
        (_blocks[i - 1], _blocks[i]) = (_blocks[i], _blocks[i - 1]);
        PushBlocksToScript();
    }

    public void MoveSelectedDown()
    {
        if (SelectedBlock == null) return;
        var i = _blocks.IndexOf(SelectedBlock.Block);
        if (i < 0 || i >= _blocks.Count - 1) return;
        (_blocks[i + 1], _blocks[i]) = (_blocks[i], _blocks[i + 1]);
        PushBlocksToScript();
    }

    public void ReceiveFromRunner(string data, string proxy, ProxyType proxyType) =>
        Debugger.ReceiveFromRunner(data, proxy, proxyType);

    private void RebuildBlockItems()
    {
        Blocks.Clear();
        for (var i = 0; i < _blocks.Count; i++)
            Blocks.Add(new BlockStackItem(_blocks[i], i));
    }

    private void SetStatus(string message)
    {
        StatusMessage = message;
        OnPropertyChanged(nameof(StatusMessage));
    }
}
