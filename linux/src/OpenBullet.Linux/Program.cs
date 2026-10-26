using System;
using Avalonia;
using OpenBullet.Linux.Services;

namespace OpenBullet.Linux;

internal static class Program
{
    [STAThread]
    public static void Main(string[] args)
    {
        ScreenshotCapture.EnableSoftwareRenderingIfNeeded();
        BuildAvaloniaApp().StartWithClassicDesktopLifetime(args);
    }

    public static AppBuilder BuildAvaloniaApp() =>
        AppBuilder.Configure<App>()
            .UsePlatformDetect()
            .WithInterFont()
            .LogToTrace();
}
