using System.Linq;
using RuriLib;
using RuriLib.LS;
using Xunit;

namespace OpenBullet.Parity.Tests;

public sealed class BlockRoundTripTests
{
    [Fact]
    public void SmokeFixture_round_trips_through_blocks()
    {
        var path = System.IO.Path.Combine(
            FindLinuxRoot(),
            "fixtures",
            "smoke.loli");
        Assert.True(System.IO.File.Exists(path), path);
        var script = System.IO.File.ReadAllText(path);
        var blocks = new LoliScript(script).ToBlocks();
        Assert.NotEmpty(blocks);
        var ls = new LoliScript();
        ls.FromBlocks(blocks.ToList());
        var again = new LoliScript(ls.Script).ToBlocks();
        Assert.Equal(blocks.Count, again.Count);
        Assert.Contains(blocks, b => b is BlockRequest);
    }

    [Theory]
    [InlineData("REQUEST GET \"https://example.com\"\n")]
    [InlineData("PARSE \"<SOURCE>\" LR \"\" \"\" -> VAR \"x\"\n")]
    [InlineData("FUNCTION Constant \"hello\" -> VAR \"g\"\n")]
    public void Block_types_parse_and_emit(string line)
    {
        var blocks = new LoliScript(line).ToBlocks();
        Assert.Single(blocks);
        var ls = new LoliScript();
        ls.FromBlocks(blocks.ToList());
        Assert.False(string.IsNullOrWhiteSpace(ls.Script));
        Assert.NotEmpty(new LoliScript(ls.Script).ToBlocks());
    }

    private static string FindLinuxRoot()
    {
        foreach (var start in new[]
                 {
                     System.IO.Directory.GetCurrentDirectory(),
                     System.AppContext.BaseDirectory
                 })
        {
            var dir = start;
            for (var i = 0; i < 10 && !string.IsNullOrEmpty(dir); i++)
            {
                if (System.IO.File.Exists(System.IO.Path.Combine(dir, "fixtures", "smoke.loli")))
                    return dir;
                dir = System.IO.Path.GetDirectoryName(dir);
            }
        }

        throw new System.IO.FileNotFoundException("Could not locate linux/fixtures/smoke.loli");
    }
}
