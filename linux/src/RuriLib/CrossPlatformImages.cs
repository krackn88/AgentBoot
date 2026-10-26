using System.IO;
using SixLabors.ImageSharp;
using SixLabors.ImageSharp.Formats.Jpeg;
using SixLabors.ImageSharp.Formats.Png;
using SixLabors.ImageSharp.PixelFormats;
using SixLabors.ImageSharp.Processing;

namespace RuriLib;

/// <summary>ImageSharp helpers for Selenium/captcha paths on non-Windows runtimes.</summary>
internal static class CrossPlatformImages
{
    public static byte[] CropScreenshot(byte[] screenshotBytes, int x, int y, int width, int height)
    {
        using var image = Image.Load<Rgba32>(screenshotBytes);
        image.Mutate(ctx => ctx.Crop(new Rectangle(x, y, width, height)));
        using var ms = new MemoryStream();
        image.Save(ms, new PngEncoder());
        return ms.ToArray();
    }

    public static byte[] EncodeJpeg(byte[] pngOrImageBytes)
    {
        using var image = Image.Load<Rgba32>(pngOrImageBytes);
        using var ms = new MemoryStream();
        image.Save(ms, new JpegEncoder());
        return ms.ToArray();
    }

    public static void CopyFile(string source, string destination)
    {
        var dir = Path.GetDirectoryName(destination);
        if (!string.IsNullOrEmpty(dir))
            Directory.CreateDirectory(dir);
        File.Copy(source, destination, true);
    }
}
