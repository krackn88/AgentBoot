using System;

namespace ObMedia;

/// <summary>
/// Canonical ARGB color for RuriLib logging and config (replaces WPF <c>System.Windows.Media.Color</c> on Linux).
/// </summary>
public readonly struct BlockColor : IEquatable<BlockColor>
{
    public byte A { get; }
    public byte R { get; }
    public byte G { get; }
    public byte B { get; }

    public BlockColor(byte a, byte r, byte g, byte b)
    {
        A = a;
        R = r;
        G = g;
        B = b;
    }

    public static BlockColor FromRgb(byte r, byte g, byte b) => new(255, r, g, b);

    public bool Equals(BlockColor other) => A == other.A && R == other.R && G == other.G && B == other.B;

    public override bool Equals(object obj) => obj is BlockColor other && Equals(other);

    public override int GetHashCode() => HashCode.Combine(A, R, G, B);

    public static bool operator ==(BlockColor left, BlockColor right) => left.Equals(right);

    public static bool operator !=(BlockColor left, BlockColor right) => !left.Equals(right);
}
