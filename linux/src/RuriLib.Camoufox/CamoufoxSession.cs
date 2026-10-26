using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.Playwright;

namespace RuriLib.Camoufox;

/// <summary>Playwright session for one bot (Camoufox Firefox).</summary>
public sealed class CamoufoxSession : IAsyncDisposable
{
    public const string CustomObjectKey = "RuriLib.Camoufox.Session";

    public IPage Page { get; }
    public IBrowser Browser { get; }
    public IBrowserContext Context { get; }

    private IFrame _activeFrame;

    private CamoufoxSession(IPage page, IBrowser browser, IBrowserContext context)
    {
        Page = page;
        Browser = browser;
        Context = context;
    }

    public void SetActiveFrame(IFrame frame) => _activeFrame = frame;

    public void ClearActiveFrame() => _activeFrame = null;

    private ILocator Root(string selector) =>
        _activeFrame != null ? _activeFrame.Locator(selector) : Page.Locator(selector);

    public string Url => Page.Url;
    public string Content => Page.ContentAsync().GetAwaiter().GetResult();

    public byte[] ScreenshotPng() => Page.ScreenshotAsync(new PageScreenshotOptions { Type = ScreenshotType.Png }).GetAwaiter().GetResult();

    public object ExecuteJs(string script) => Page.EvaluateAsync<object>(script).GetAwaiter().GetResult();

    public async Task GotoAsync(string url, int timeoutSeconds)
    {
        await Page.GotoAsync(url, new PageGotoOptions
        {
            Timeout = timeoutSeconds * 1000,
            WaitUntil = WaitUntilState.DOMContentLoaded
        });
    }

    public IReadOnlyList<ILocator> FindAll(string selector, CamoufoxLocatorKind kind)
    {
        var sel = ToPlaywrightSelector(selector, kind);
        return Root(sel).AllAsync().GetAwaiter().GetResult();
    }

    public ILocator First(string selector, CamoufoxLocatorKind kind)
    {
        var sel = ToPlaywrightSelector(selector, kind);
        return Root(sel).First;
    }

    public static string ToPlaywrightSelector(string value, CamoufoxLocatorKind kind) => kind switch
    {
        CamoufoxLocatorKind.Id => $"#{EscapeCss(value)}",
        CamoufoxLocatorKind.Class => $".{EscapeCss(value)}",
        CamoufoxLocatorKind.Name => $"[name='{EscapeAttr(value)}']",
        CamoufoxLocatorKind.Tag => value,
        CamoufoxLocatorKind.Css => value,
        CamoufoxLocatorKind.XPath => $"xpath={value}",
        _ => value
    };

    public Dictionary<string, string> GetCookies()
    {
        var cookies = Context.CookiesAsync().GetAwaiter().GetResult();
        return cookies.ToDictionary(c => c.Name, c => c.Value);
    }

    public void ClearCookies() => Context.ClearCookiesAsync().GetAwaiter().GetResult();

    public async Task SetCookiesAsync(IEnumerable<KeyValuePair<string, string>> cookies, string domain)
    {
        var list = cookies.Select(c => new Cookie
        {
            Name = c.Key,
            Value = c.Value,
            Domain = domain,
            Path = "/"
        }).ToArray();
        await Context.AddCookiesAsync(list);
    }

    public static async Task<CamoufoxSession> LaunchAsync(CamoufoxLaunchOptions options)
    {
        var playwright = await Playwright.CreateAsync();
        var browser = await CamoufoxLauncher.ConnectOrLaunchAsync(playwright, options);
        var context = browser.Contexts.FirstOrDefault() ?? await browser.NewContextAsync(options.BuildContextOptions());
        var page = context.Pages.FirstOrDefault() ?? await context.NewPageAsync();
        return new CamoufoxSession(page, browser, context);
    }

    public async ValueTask DisposeAsync()
    {
        try { await Context.CloseAsync(); } catch { }
        try { await Browser.CloseAsync(); } catch { }
    }

    public void DisposeSync() => DisposeAsync().AsTask().GetAwaiter().GetResult();

    private static string EscapeCss(string s) => s.Replace(" ", "\\ ");
    private static string EscapeAttr(string s) => s.Replace("'", "\\'");
}

public enum CamoufoxLocatorKind
{
    Id, Class, Name, Tag, Css, XPath
}
