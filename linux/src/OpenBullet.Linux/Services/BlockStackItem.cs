using RuriLib;
using RuriLib.ViewModels;

namespace OpenBullet.Linux.Services;

public sealed class BlockStackItem : ViewModelBase
{
    public BlockStackItem(BlockBase block, int index)
    {
        Block = block;
        Index = index;
        RefreshLabel();
    }

    public BlockBase Block { get; }
    public int Index { get; set; }

    public string DisplayLabel { get; private set; }

    public void RefreshLabel()
    {
        var kind = Block.GetType().Name;
        if (kind.StartsWith("Block", System.StringComparison.Ordinal))
            kind = kind["Block".Length..];
        DisplayLabel = Block.Disabled ? $"[OFF] {kind}: {Block.Label}" : $"{kind}: {Block.Label}";
        OnPropertyChanged(nameof(DisplayLabel));
    }
}
