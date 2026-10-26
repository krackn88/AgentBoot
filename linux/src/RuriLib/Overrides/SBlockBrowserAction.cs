using OpenQA.Selenium;
using OpenQA.Selenium.Chrome;
using OpenQA.Selenium.Firefox;
using OpenQA.Selenium.Interactions;
using RuriLib.Camoufox;
using RuriLib.Functions.Files;
using RuriLib.Functions.UserAgent;
using RuriLib.LS;
using System;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Media;
using Microsoft.Playwright;

namespace RuriLib
{
    public class SBlockBrowserAction : BlockBase
    {
        private BrowserAction action = BrowserAction.Open;
        public BrowserAction Action { get { return action; } set { action = value; OnPropertyChanged(); } }

        private string input = "";
        public string Input { get { return input; } set { input = value; OnPropertyChanged(); } }

        public SBlockBrowserAction()
        {
            Label = "BROWSER ACTION";
        }

        public override BlockBase FromLS(string line)
        {
            var inputLine = line.Trim();
            if (inputLine.StartsWith("#"))
                Label = LineParser.ParseLabel(ref inputLine);

            Action = (BrowserAction)LineParser.ParseEnum(ref inputLine, "ACTION", typeof(BrowserAction));
            if (inputLine != string.Empty) Input = LineParser.ParseLiteral(ref inputLine, "INPUT");
            return this;
        }

        public override string ToLS(bool indent = true)
        {
            var writer = new BlockWriter(GetType(), indent, Disabled);
            writer
                .Label(Label)
                .Token("BROWSERACTION")
                .Token(Action)
                .Literal(Input, "Input");
            return writer.ToString();
        }

        public override void Process(BotData data)
        {
            base.Process(data);

            if (!BrowserSession.IsOpen(data) && action != BrowserAction.Open)
            {
                data.Log(new LogEntry("Open a browser first!", Colors.White));
                throw new Exception("Browser not open");
            }

            var replacedInput = ReplaceValues(input, data);

            if (CamoufoxBotBridge.TryGet(data, out var session))
            {
                ProcessCamoufox(data, session, replacedInput);
                return;
            }

            ProcessSelenium(data, replacedInput);
        }

        private void ProcessCamoufox(BotData data, CamoufoxSession session, string replacedInput)
        {
            var page = session.Page;

            switch (action)
            {
                case BrowserAction.Open:
                    OpenBrowser(data);
                    try { BrowserSession.UpdateData(data); } catch { }
                    break;

                case BrowserAction.Close:
                    page.CloseAsync().GetAwaiter().GetResult();
                    data.BrowserOpen = false;
                    break;

                case BrowserAction.Quit:
                    CamoufoxBotBridge.QuitBotData(data);
                    break;

                case BrowserAction.ClearCookies:
                    session.ClearCookies();
                    break;

                case BrowserAction.SendKeys:
                    SendKeysPlaywright(page, replacedInput);
                    if (replacedInput.Contains("<ENTER>") || replacedInput.Contains("<BACKSPACE>"))
                        BrowserSession.UpdateData(data);
                    break;

                case BrowserAction.Screenshot:
                    Files.SaveScreenshot(session.ScreenshotPng(), data);
                    break;

                case BrowserAction.OpenNewTab:
                    page.Context.NewPageAsync().GetAwaiter().GetResult();
                    break;

                case BrowserAction.SwitchToTab:
                    var pages = page.Context.Pages;
                    var idx = int.Parse(replacedInput);
                    if (idx >= 0 && idx < pages.Count)
                        pages[idx].BringToFrontAsync().GetAwaiter().GetResult();
                    BrowserSession.UpdateData(data);
                    break;

                case BrowserAction.CloseCurrentTab:
                    page.CloseAsync().GetAwaiter().GetResult();
                    break;

                case BrowserAction.Refresh:
                    page.ReloadAsync().GetAwaiter().GetResult();
                    break;

                case BrowserAction.Back:
                    page.GoBackAsync().GetAwaiter().GetResult();
                    break;

                case BrowserAction.Forward:
                    page.GoForwardAsync().GetAwaiter().GetResult();
                    break;

                case BrowserAction.ScrollToTop:
                    page.EvaluateAsync("window.scrollTo(0,0)").GetAwaiter().GetResult();
                    break;

                case BrowserAction.ScrollToBottom:
                    page.EvaluateAsync("window.scrollTo(0, document.body.scrollHeight)").GetAwaiter().GetResult();
                    break;

                case BrowserAction.Scroll:
                    page.EvaluateAsync($"window.scrollTo(0, {int.Parse(replacedInput)})").GetAwaiter().GetResult();
                    break;

                case BrowserAction.DOMtoSOURCE:
                    data.ResponseSource = page.EvaluateAsync<string>("document.body.innerHTML").GetAwaiter().GetResult();
                    break;

                case BrowserAction.GetCookies:
                    foreach (var cookie in session.GetCookies())
                    {
                        try { data.Cookies.Add(cookie.Key, cookie.Value); } catch { }
                    }
                    break;

                case BrowserAction.SetCookies:
                    var baseUrl = Regex.Match(replacedInput, "^(?:https?:\\/\\/)?(?:[^@\\/\n]+@)?([^:\\/?\n]+)").Groups[1].Value;
                    session.SetCookiesAsync(data.Cookies, baseUrl).GetAwaiter().GetResult();
                    break;

                case BrowserAction.Maximize:
                case BrowserAction.Minimize:
                case BrowserAction.FullScreen:
                case BrowserAction.SetWidth:
                case BrowserAction.SetHeight:
                case BrowserAction.SwitchToDefault:
                case BrowserAction.SwitchToAlert:
                case BrowserAction.SwitchToParentFrame:
                    data.Log(new LogEntry($"Browser action {action} is not fully emulated on Camoufox; skipped.", Colors.Tomato));
                    break;
            }

            data.Log(new LogEntry(string.Format("Executed browser action {0} on input {1}", action, replacedInput), Colors.White));
        }

        private static void SendKeysPlaywright(IPage page, string replacedInput)
        {
            foreach (var s in replacedInput.Split(new[] { "||" }, StringSplitOptions.None))
            {
                switch (s)
                {
                    case "<TAB>":
                        page.Keyboard.PressAsync("Tab").GetAwaiter().GetResult();
                        break;
                    case "<ENTER>":
                        page.Keyboard.PressAsync("Enter").GetAwaiter().GetResult();
                        break;
                    case "<BACKSPACE>":
                        page.Keyboard.PressAsync("Backspace").GetAwaiter().GetResult();
                        break;
                    case "<ESC>":
                        page.Keyboard.PressAsync("Escape").GetAwaiter().GetResult();
                        break;
                    default:
                        page.Keyboard.TypeAsync(s).GetAwaiter().GetResult();
                        break;
                }
            }

            Thread.Sleep(1000);
        }

        private void ProcessSelenium(BotData data, string replacedInput)
        {
            Actions keyActions = null;

            switch (action)
            {
                case BrowserAction.Open:
                    OpenBrowser(data);
                    try { BrowserSession.UpdateData(data); } catch { }
                    break;

                case BrowserAction.Close:
                    data.Driver.Close();
                    data.BrowserOpen = false;
                    break;

                case BrowserAction.Quit:
                    data.Driver.Quit();
                    data.BrowserOpen = false;
                    break;

                case BrowserAction.ClearCookies:
                    data.Driver.Manage().Cookies.DeleteAllCookies();
                    break;

                case BrowserAction.SendKeys:
                    keyActions = new Actions(data.Driver);
                    foreach (var s in replacedInput.Split(new[] { "||" }, StringSplitOptions.None))
                    {
                        switch (s)
                        {
                            case "<TAB>":
                                keyActions.SendKeys(Keys.Tab);
                                break;
                            case "<ENTER>":
                                keyActions.SendKeys(Keys.Enter);
                                break;
                            case "<BACKSPACE>":
                                keyActions.SendKeys(Keys.Backspace);
                                break;
                            case "<ESC>":
                                keyActions.SendKeys(Keys.Escape);
                                break;
                            default:
                                keyActions.SendKeys(s);
                                break;
                        }
                    }
                    keyActions.Perform();
                    Thread.Sleep(1000);
                    if (replacedInput.Contains("<ENTER>") || replacedInput.Contains("<BACKSPACE>"))
                        BrowserSession.UpdateData(data);
                    break;

                case BrowserAction.Screenshot:
                    Files.SaveScreenshot(data.Driver.GetScreenshot(), data);
                    break;

                case BrowserAction.OpenNewTab:
                    ((IJavaScriptExecutor)data.Driver).ExecuteScript("window.open();");
                    data.Driver.SwitchTo().Window(data.Driver.WindowHandles.Last());
                    break;

                case BrowserAction.SwitchToTab:
                    data.Driver.SwitchTo().Window(data.Driver.WindowHandles[int.Parse(replacedInput)]);
                    BrowserSession.UpdateData(data);
                    break;

                case BrowserAction.CloseCurrentTab:
                    ((IJavaScriptExecutor)data.Driver).ExecuteScript("window.close();");
                    break;

                case BrowserAction.Refresh:
                    data.Driver.Navigate().Refresh();
                    break;

                case BrowserAction.Back:
                    data.Driver.Navigate().Back();
                    break;

                case BrowserAction.Forward:
                    data.Driver.Navigate().Forward();
                    break;

                case BrowserAction.Maximize:
                    data.Driver.Manage().Window.Maximize();
                    break;

                case BrowserAction.Minimize:
                    data.Driver.Manage().Window.Minimize();
                    break;

                case BrowserAction.FullScreen:
                    data.Driver.Manage().Window.FullScreen();
                    break;

                case BrowserAction.SetWidth:
                    data.Driver.Manage().Window.Size = new Size(int.Parse(replacedInput), data.Driver.Manage().Window.Size.Height);
                    break;

                case BrowserAction.SetHeight:
                    data.Driver.Manage().Window.Size = new Size(data.Driver.Manage().Window.Size.Width, int.Parse(replacedInput));
                    break;

                case BrowserAction.DOMtoSOURCE:
                    data.ResponseSource = data.Driver.FindElement(By.TagName("body")).GetAttribute("innerHTML");
                    break;

                case BrowserAction.GetCookies:
                    foreach (var cookie in data.Driver.Manage().Cookies.AllCookies)
                    {
                        try { data.Cookies.Add(cookie.Name, cookie.Value); } catch { }
                    }
                    break;

                case BrowserAction.SetCookies:
                    var baseURL = Regex.Match(ReplaceValues(input, data), "^(?:https?:\\/\\/)?(?:[^@\\/\n]+@)?([^:\\/?\n]+)").Groups[1].Value;
                    foreach (var cookie in data.Cookies)
                    {
                        try { data.Driver.Manage().Cookies.AddCookie(new OpenQA.Selenium.Cookie(cookie.Key, cookie.Value, baseURL, "/", DateTime.MaxValue)); } catch { }
                    }
                    break;

                case BrowserAction.SwitchToDefault:
                    data.Driver.SwitchTo().DefaultContent();
                    break;

                case BrowserAction.SwitchToAlert:
                    data.Driver.SwitchTo().Alert();
                    break;

                case BrowserAction.SwitchToParentFrame:
                    data.Driver.SwitchTo().ParentFrame();
                    break;

                case BrowserAction.ScrollToTop:
                case BrowserAction.ScrollToBottom:
                case BrowserAction.Scroll:
                    data.Log(new LogEntry($"Scroll actions use Camoufox path on Linux.", Colors.Tomato));
                    break;
            }

            data.Log(new LogEntry(string.Format("Executed browser action {0} on input {1}", action, ReplaceValues(input, data)), Colors.White));
        }

        public static void OpenBrowser(BotData data)
        {
            if (!data.BrowserOpen)
            {
                data.Log(new LogEntry("Opening browser (Camoufox)...", Colors.White));

                var opts = new CamoufoxLaunchOptions
                {
                    Headless = data.GlobalSettings.Selenium.Headless || data.ConfigSettings.ForceHeadless,
                    PageLoadTimeoutSeconds = data.GlobalSettings.Selenium.PageLoadTimeout
                };

                if (data.ConfigSettings.RandomUA)
                    opts.UserAgent = UserAgent.Random(data.random);
                else if (!string.IsNullOrEmpty(data.ConfigSettings.CustomUserAgent))
                    opts.UserAgent = data.ConfigSettings.CustomUserAgent;

                if (data.UseProxies && data.Proxy != null)
                    opts.ProxyServer = $"{data.Proxy.Type.ToString().ToLower()}://{data.Proxy.Proxy}";

                CamoufoxBotBridge.Open(data, opts);
                data.Log(new LogEntry("Opened!", Colors.White));
            }
            else
            {
                try { BrowserSession.UpdateData(data); } catch { }
            }
        }
    }
}
