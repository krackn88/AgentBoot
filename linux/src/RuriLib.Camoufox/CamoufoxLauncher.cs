using System;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Playwright;

namespace RuriLib.Camoufox;

public static class CamoufoxLauncher
{
    private static Process _serverProcess;
    private static string _cachedWs;

    public static async Task<IBrowser> ConnectOrLaunchAsync(IPlaywright playwright, CamoufoxLaunchOptions options)
    {
        var ws = options.WebSocketEndpoint
                 ?? Environment.GetEnvironmentVariable("CAMOUFOX_WS")
                 ?? Environment.GetEnvironmentVariable("CAMOUFOX_SERVER_WS")
                 ?? _cachedWs;

        if (string.IsNullOrWhiteSpace(ws))
            ws = await TryStartLocalServerAsync();

        if (!string.IsNullOrWhiteSpace(ws))
        {
            _cachedWs = ws;
            return await playwright.Firefox.ConnectAsync(ws);
        }

        // Fallback: stock Firefox via Playwright (requires `playwright install firefox`)
        return await playwright.Firefox.LaunchAsync(new BrowserTypeLaunchOptions
        {
            Headless = options.Headless
        });
    }

    private static async Task<string> TryStartLocalServerAsync()
    {
        var port = GetFreePort();
        var wsPath = "openbullet";
        var ws = $"ws://127.0.0.1:{port}/{wsPath}";

        try
        {
            _serverProcess = Process.Start(new ProcessStartInfo
            {
                FileName = "python3",
                Arguments = $"-m camoufox server --port {port} --ws-path {wsPath}",
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true
            });

            for (var i = 0; i < 40; i++)
            {
                await Task.Delay(250);
                if (await ProbeWebSocket(ws))
                    return ws;
            }
        }
        catch
        {
            // camoufox python package not installed
        }

        return null;
    }

    private static async Task<bool> ProbeWebSocket(string ws)
    {
        try
        {
            var playwright = await Playwright.CreateAsync();
            var browser = await playwright.Firefox.ConnectAsync(ws);
            await browser.CloseAsync();
            return true;
        }
        catch
        {
            return false;
        }
    }

    private static int GetFreePort()
    {
        var l = new TcpListener(IPAddress.Loopback, 0);
        l.Start();
        var port = ((IPEndPoint)l.LocalEndpoint).Port;
        l.Stop();
        return port;
    }

    public static void StopServerIfOwned()
    {
        try
        {
            if (_serverProcess != null && !_serverProcess.HasExited)
                _serverProcess.Kill(entireProcessTree: true);
        }
        catch { }
        finally
        {
            _serverProcess = null;
            _cachedWs = null;
        }
    }
}
