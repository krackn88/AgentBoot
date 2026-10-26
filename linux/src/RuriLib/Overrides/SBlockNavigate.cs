using RuriLib.Camoufox;
using RuriLib.LS;
using System;
using System.Threading.Tasks;
using System.Windows.Media;

namespace RuriLib
{
    public class SBlockNavigate : BlockBase
    {
        private string url = "https://example.com";
        public string Url { get { return url; } set { url = value; OnPropertyChanged(); } }

        private int timeout = 60;
        public int Timeout { get { return timeout; } set { timeout = value; OnPropertyChanged(); } }

        private bool banOnTimeout = true;
        public bool BanOnTimeout { get { return banOnTimeout; } set { banOnTimeout = value; OnPropertyChanged(); } }

        public SBlockNavigate()
        {
            Label = "NAVIGATE";
        }

        public override BlockBase FromLS(string line)
        {
            var input = line.Trim();
            if (input.StartsWith("#"))
                Label = LineParser.ParseLabel(ref input);

            Url = LineParser.ParseLiteral(ref input, "URL");
            if (LineParser.Lookahead(ref input) == TokenType.Integer)
                Timeout = LineParser.ParseInt(ref input, "TIMEOUT");
            if (LineParser.Lookahead(ref input) == TokenType.Boolean)
                LineParser.SetBool(ref input, this);

            return this;
        }

        public override string ToLS(bool indent = true)
        {
            var writer = new BlockWriter(GetType(), indent, Disabled);
            writer
                .Label(Label)
                .Token("NAVIGATE")
                .Literal(Url)
                .Integer(Timeout, "Timeout")
                .Boolean(BanOnTimeout, "BanOnTimeout");
            return writer.ToString();
        }

        public override void Process(BotData data)
        {
            base.Process(data);

            if (!BrowserSession.IsOpen(data))
            {
                data.Log(new LogEntry("Open a browser first!", Colors.White));
                throw new Exception("Browser not open");
            }

            var target = ReplaceValues(url, data);
            data.Log(new LogEntry("Navigating to " + target, Colors.White));

            if (CamoufoxBotBridge.TryGet(data, out var session))
            {
                try
                {
                    session.GotoAsync(target, timeout).GetAwaiter().GetResult();
                    data.Log(new LogEntry("Navigated!", Colors.White));
                }
                catch (Exception ex) when (ex.GetType().Name.Contains("Timeout", StringComparison.Ordinal))
                {
                    data.Log(new LogEntry("Timeout on Page Load", Colors.Tomato));
                    if (BanOnTimeout)
                        data.Status = BotStatus.BAN;
                }
            }
            else
            {
                data.Driver.Manage().Timeouts().PageLoad = TimeSpan.FromSeconds(timeout);
                try
                {
                    data.Driver.Navigate().GoToUrl(target);
                    data.Log(new LogEntry("Navigated!", Colors.White));
                }
                catch (OpenQA.Selenium.WebDriverTimeoutException)
                {
                    data.Log(new LogEntry("Timeout on Page Load", Colors.Tomato));
                    if (BanOnTimeout)
                        data.Status = BotStatus.BAN;
                }

                data.Driver.Manage().Timeouts().PageLoad = TimeSpan.FromSeconds(data.GlobalSettings.Selenium.PageLoadTimeout);
            }

            BrowserSession.UpdateData(data);
        }
    }
}
