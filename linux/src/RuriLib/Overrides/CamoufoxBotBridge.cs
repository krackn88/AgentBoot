using System;
using RuriLib.Camoufox;
using RuriLib.Runner;

namespace RuriLib.Camoufox;

/// <summary>Hooks Camoufox sessions into <see cref="BotData.CustomObjects"/> (Linux port).</summary>
public static class CamoufoxBotBridge
{
    public static bool TryGet(BotData data, out CamoufoxSession session)
    {
        session = null;
        if (data?.CustomObjects == null) return false;
        return data.CustomObjects.TryGetValue(CamoufoxSession.CustomObjectKey, out var obj)
               && obj is CamoufoxSession s
               && (session = s) != null;
    }

    public static bool IsOpen(BotData data) => data.BrowserOpen && TryGet(data, out _);

    public static void Open(BotData data, CamoufoxLaunchOptions options)
    {
        if (data.BrowserOpen && TryGet(data, out _))
            return;

        data.CustomObjects ??= new System.Collections.Generic.Dictionary<string, object>();
        var session = CamoufoxSession.LaunchAsync(options).GetAwaiter().GetResult();
        data.CustomObjects[CamoufoxSession.CustomObjectKey] = session;
        data.BrowserOpen = true;
        data.Driver = null;
    }

    public static void UpdateBrowserData(BotData data)
    {
        if (TryGet(data, out var session))
        {
            data.Address = session.Url;
            data.ResponseSource = session.Content;
            return;
        }

        if (data.Driver != null)
        {
            data.Address = data.Driver.Url;
            data.ResponseSource = data.Driver.PageSource;
        }
    }

    public static void QuitBotData(BotData data)
    {
        if (TryGet(data, out var session))
        {
            session.DisposeSync();
            data.CustomObjects.Remove(CamoufoxSession.CustomObjectKey);
        }

        try { data.Driver?.Quit(); } catch { }
        data.Driver = null;
        data.BrowserOpen = false;
    }

    public static void QuitRunnerBot(RunnerBotViewModel bot)
    {
        if (bot.BrowserObjects != null
            && bot.BrowserObjects.TryGetValue(CamoufoxSession.CustomObjectKey, out var obj)
            && obj is CamoufoxSession session)
        {
            session.DisposeSync();
            bot.BrowserObjects.Remove(CamoufoxSession.CustomObjectKey);
        }

        try { bot.Driver?.Quit(); } catch { }
        bot.Driver = null;
        bot.IsDriverOpen = false;
    }
}
