using Microsoft.Playwright;

namespace RuriLib.Camoufox;

public sealed class CamoufoxLaunchOptions
{
    public bool Headless { get; set; } = true;
    public string UserAgent { get; set; }
    public string ProxyServer { get; set; }
    public int PageLoadTimeoutSeconds { get; set; } = 60;
    public string WebSocketEndpoint { get; set; }

    public BrowserNewContextOptions BuildContextOptions()
    {
        var ctx = new BrowserNewContextOptions
        {
            UserAgent = string.IsNullOrWhiteSpace(UserAgent) ? null : UserAgent,
            IgnoreHTTPSErrors = true
        };

        if (!string.IsNullOrWhiteSpace(ProxyServer))
            ctx.Proxy = new Proxy { Server = ProxyServer };

        return ctx;
    }
}
