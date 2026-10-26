using RuriLib.Camoufox;

namespace RuriLib;

internal static class BrowserSession
{
    public static bool IsOpen(BotData data) =>
        data.BrowserOpen && (CamoufoxBotBridge.IsOpen(data) || data.Driver != null);

    public static void UpdateData(BotData data) => CamoufoxBotBridge.UpdateBrowserData(data);
}
