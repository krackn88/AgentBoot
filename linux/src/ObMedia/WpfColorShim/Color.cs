using System;
using ObMedia;

namespace System.Windows.Media;

/// <summary>
/// Compatibility shim so upstream RuriLib compiles without WPF. Maps to <see cref="BlockColor"/>.
/// </summary>
public struct Color : IEquatable<Color>
{
    public byte A { get; }
    public byte R { get; }
    public byte G { get; }
    public byte B { get; }

    private Color(byte a, byte r, byte g, byte b)
    {
        A = a;
        R = r;
        G = g;
        B = b;
    }

    public static Color FromRgb(byte r, byte g, byte b) => new(255, r, g, b);

    public static implicit operator Color(BlockColor c) => new(c.A, c.R, c.G, c.B);

    public static implicit operator BlockColor(Color c) => new(c.A, c.R, c.G, c.B);

    public bool Equals(Color other) => A == other.A && R == other.R && G == other.G && B == other.B;

    public override bool Equals(object obj) => obj is Color other && Equals(other);

    public override int GetHashCode() => HashCode.Combine(A, R, G, B);

    public static bool operator ==(Color left, Color right) => left.Equals(right);

    public static bool operator !=(Color left, Color right) => !left.Equals(right);
}
