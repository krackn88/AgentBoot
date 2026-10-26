using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Media.Imaging;
using Avalonia.Threading;
using SharpImage = SixLabors.ImageSharp.Image;
using SixLabors.ImageSharp.Formats.Png;
using SixLabors.ImageSharp.PixelFormats;
using SixLabors.ImageSharp.Processing;
using SharpRectangle = SixLabors.ImageSharp.Rectangle;

namespace OpenBullet.Linux.Services;

/// <summary>Headless-friendly PNG export via <see cref="RenderTargetBitmap"/> (not X11 window grab).</summary>
public static class ScreenshotCapture
{
    private const int DefaultWidth = 960;
    private const int DefaultHeight = 700;

    public static bool IsRequested
    {
        get
        {
            var flag = Environment.GetEnvironmentVariable("OPENBULLET_SCREENSHOT");
            if (string.IsNullOrWhiteSpace(flag)) return false;
            if (flag is "0" or "false" or "no") return false;
            return true;
        }
    }

    public static void EnableSoftwareRenderingIfNeeded()
    {
        if (!IsRequested) return;
        Environment.SetEnvironmentVariable("AVALONIA_RENDERER", "software");
    }

    public static IReadOnlyList<string> GetOutputPaths()
    {
        var list = new List<string>();
        var multi = Environment.GetEnvironmentVariable("OPENBULLET_SCREENSHOT_PATH");
        if (!string.IsNullOrWhiteSpace(multi))
        {
            list.AddRange(multi.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries));
            return list;
        }

        var legacy = Environment.GetEnvironmentVariable("OPENBULLET_SCREENSHOT");
        if (!string.IsNullOrWhiteSpace(legacy) && legacy is not ("1" or "true" or "yes"))
            list.Add(legacy.Trim());

        return list;
    }

    public static string GetCropOutputPath()
    {
        var crop = Environment.GetEnvironmentVariable("OPENBULLET_SCREENSHOT_CROP_PATH");
        if (!string.IsNullOrWhiteSpace(crop)) return crop.Trim();

        var primary = GetOutputPaths().FirstOrDefault();
        if (primary == null) return null;
        var dir = Path.GetDirectoryName(primary) ?? ".";
        var name = Path.GetFileNameWithoutExtension(primary);
        var ext = Path.GetExtension(primary);
        return Path.Combine(dir, $"{name}-crop{ext}");
    }

    public static void Schedule(Window window, Control contentRoot)
    {
        if (!IsRequested) return;

        window.Opened += (_, _) =>
        {
            Dispatcher.UIThread.Post(async () => await CaptureWithRetriesAsync(window, contentRoot));
        };
    }

    private static async Task CaptureWithRetriesAsync(Window window, Control contentRoot)
    {
        var paths = GetOutputPaths();
        if (paths.Count == 0)
        {
            Console.Error.WriteLine("OPENBULLET_SCREENSHOT set but no OPENBULLET_SCREENSHOT_PATH (or legacy path) provided.");
            Environment.Exit(2);
            return;
        }

        var cropPath = GetCropOutputPath();
        const int maxAttempts = 6;
        byte[] pngBytes = null;
        ScreenshotStats stats = null;

        for (var attempt = 1; attempt <= maxAttempts; attempt++)
        {
            await Task.Delay(200 + attempt * 350);
            await ForceLayoutAsync(window);

            var width = Math.Max(DefaultWidth, (int)Math.Ceiling(window.Bounds.Width));
            var height = Math.Max(DefaultHeight, (int)Math.Ceiling(window.Bounds.Height));

            pngBytes = await RenderToPngAsync(window, width, height);
            stats = AnalyzePng(pngBytes);

            Console.WriteLine(
                $"[screenshot] attempt {attempt}/{maxAttempts}: {width}x{height} avg={stats.AverageBrightness:F1} black%={stats.BlackPixelPercent:F1} bright_px={stats.BrightPixelCount}");

            if (stats.Passes)
                break;

            pngBytes = null;
        }

        if (pngBytes == null || stats == null || !stats.Passes)
        {
            Console.Error.WriteLine("[screenshot] FAILED: image still too dark after retries.");
            Environment.Exit(3);
            return;
        }

        foreach (var path in paths)
            await WritePngAsync(path, pngBytes);

        var chatPath = Environment.GetEnvironmentVariable("OPENBULLET_SCREENSHOT_CHAT_PATH");
        if (!string.IsNullOrWhiteSpace(chatPath))
            await WritePngAsync(chatPath, BrightenForPreview(pngBytes));

        if (!string.IsNullOrWhiteSpace(cropPath) && contentRoot is Visual visual)
            await WriteCropAsync(cropPath, pngBytes, window, visual);

        var statsPath = Environment.GetEnvironmentVariable("OPENBULLET_SCREENSHOT_STATS");
        if (!string.IsNullOrWhiteSpace(statsPath))
        {
            await File.WriteAllTextAsync(statsPath,
                $"{stats.Width}x{stats.Height} avg_brightness={stats.AverageBrightness:F2} black_pct={stats.BlackPixelPercent:F2} bright_px={stats.BrightPixelCount}\n");
        }

        Environment.Exit(0);
    }

    private static async Task ForceLayoutAsync(Window window)
    {
        window.Width = DefaultWidth;
        window.Height = DefaultHeight;
        window.Measure(new Avalonia.Size(DefaultWidth, DefaultHeight));
        window.Arrange(new Rect(0, 0, DefaultWidth, DefaultHeight));
        await Dispatcher.UIThread.InvokeAsync(() => { }, DispatcherPriority.Render);
        await Task.Delay(50);
    }

    private static async Task<byte[]> RenderToPngAsync(Visual visual, int width, int height)
    {
        return await Dispatcher.UIThread.InvokeAsync(() =>
        {
            var bmp = new RenderTargetBitmap(new PixelSize(width, height), new Vector(96, 96));
            bmp.Render(visual);
            using var ms = new MemoryStream();
            bmp.Save(ms);
            return ms.ToArray();
        });
    }

    private static async Task WritePngAsync(string path, byte[] pngBytes)
    {
        var full = Path.GetFullPath(path);
        Directory.CreateDirectory(Path.GetDirectoryName(full) ?? ".");
        await File.WriteAllBytesAsync(full, pngBytes);
    }

    private static async Task WriteCropAsync(string cropPath, byte[] fullPng, Window window, Visual target)
    {
        var topLeft = target.TranslatePoint(new Avalonia.Point(0, 0), window);
        if (topLeft == null) return;

        var bounds = target.Bounds;
        if (bounds.Width < 1 || bounds.Height < 1)
            return;

        var x = (int)Math.Max(0, Math.Floor(topLeft.Value.X));
        var y = (int)Math.Max(0, Math.Floor(topLeft.Value.Y));
        var w = (int)Math.Min(Math.Ceiling(bounds.Width), window.Bounds.Width - x);
        var h = (int)Math.Min(Math.Ceiling(bounds.Height), window.Bounds.Height - y);
        if (w < 8 || h < 8) return;

        using var image = SharpImage.Load<Rgba32>(fullPng);
        image.Mutate(ctx => ctx.Crop(new SharpRectangle(x, y, w, h)));
        await using var fs = File.Create(Path.GetFullPath(cropPath));
        await image.SaveAsync(fs, new PngEncoder());
    }

    public static ScreenshotStats AnalyzePng(byte[] pngBytes)
    {
        using var image = SharpImage.Load<Rgba32>(pngBytes);
        long sum = 0;
        long total = image.Width * image.Height;
        long nearBlack = 0;
        long brightPixels = 0;

        image.ProcessPixelRows(accessor =>
        {
            for (var y = 0; y < accessor.Height; y++)
            {
                var row = accessor.GetRowSpan(y);
                for (var x = 0; x < row.Length; x++)
                {
                    var p = row[x];
                    var lum = (p.R * 299 + p.G * 587 + p.B * 114) / 1000;
                    sum += lum;
                    if (lum < 12) nearBlack++;
                    if (lum > 80) brightPixels++;
                }
            }
        });

        var avg = total == 0 ? 0 : (double)sum / total;
        var blackPct = total == 0 ? 100 : 100.0 * nearBlack / total;
        return new ScreenshotStats(image.Width, image.Height, avg, blackPct, brightPixels);
    }

    public static byte[] BrightenForPreview(byte[] pngBytes, float lift = 0.35f)
    {
        using var image = SharpImage.Load<Rgba32>(pngBytes);
        image.Mutate(ctx => ctx.Brightness(lift));
        using var ms = new MemoryStream();
        image.Save(ms, new PngEncoder());
        return ms.ToArray();
    }

    public sealed record ScreenshotStats(int Width, int Height, double AverageBrightness, double BlackPixelPercent, long BrightPixelCount)
    {
        /// <summary>Dark Metro UI can have low average luminance; reject only true black frames.</summary>
        public bool Passes =>
            BlackPixelPercent < 95
            && (AverageBrightness > 40 || BrightPixelCount > 500);
    }
}
