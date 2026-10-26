namespace ObMedia;

/// <summary>Named log colors used by RuriLib (WPF <c>Colors.*</c> equivalents).</summary>
public static class LogPalette
{
    public static BlockColor White => FromRgb(255, 255, 255);
    public static BlockColor Gold => FromRgb(255, 215, 0);
    public static BlockColor Tomato => FromRgb(255, 99, 71);
    public static BlockColor Orange => FromRgb(255, 165, 0);
    public static BlockColor OrangeRed => FromRgb(255, 69, 0);
    public static BlockColor Yellow => FromRgb(255, 255, 0);
    public static BlockColor Green => FromRgb(0, 128, 0);
    public static BlockColor GreenYellow => FromRgb(173, 255, 47);
    public static BlockColor Cyan => FromRgb(0, 255, 255);
    public static BlockColor DarkTurquoise => FromRgb(0, 206, 209);
    public static BlockColor MediumTurquoise => FromRgb(72, 209, 204);
    public static BlockColor DeepPink => FromRgb(255, 20, 147);
    public static BlockColor LightPink => FromRgb(255, 182, 193);
    public static BlockColor Goldenrod => FromRgb(218, 165, 32);
    public static BlockColor LightGoldenrodYellow => FromRgb(250, 250, 210);

    public static BlockColor FromRgb(byte r, byte g, byte b) => BlockColor.FromRgb(r, g, b);
}
