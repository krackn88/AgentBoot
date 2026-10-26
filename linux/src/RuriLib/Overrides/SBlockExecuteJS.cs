using RuriLib.Camoufox;
using RuriLib.LS;
using System;
using System.Collections.Generic;
using System.Windows.Media;

namespace RuriLib
{
    public class SBlockExecuteJS : BlockBase
    {
        private string javascriptCode = "alert('henlo');";
        public string JavascriptCode { get { return javascriptCode; } set { javascriptCode = value; OnPropertyChanged(); } }

        private string outputVariable = "";
        public string OutputVariable { get { return outputVariable; } set { outputVariable = value; OnPropertyChanged(); } }

        private bool isCapture = false;
        public bool IsCapture { get { return isCapture; } set { isCapture = value; OnPropertyChanged(); } }

        public SBlockExecuteJS()
        {
            Label = "EXECUTE JS";
        }

        public override BlockBase FromLS(string line)
        {
            var input = line.Trim();
            if (input.StartsWith("#"))
                Label = LineParser.ParseLabel(ref input);

            JavascriptCode = LineParser.ParseLiteral(ref input, "SCRIPT");

            if (LineParser.ParseToken(ref input, TokenType.Arrow, false) == string.Empty)
                return this;

            try
            {
                var varType = LineParser.ParseToken(ref input, TokenType.Parameter, true);
                if (varType.ToUpper() == "VAR" || varType.ToUpper() == "CAP")
                    IsCapture = varType.ToUpper() == "CAP";
            }
            catch { throw new ArgumentException("Invalid or missing variable type"); }

            try { OutputVariable = LineParser.ParseToken(ref input, TokenType.Literal, true); }
            catch { throw new ArgumentException("Variable name not specified"); }

            return this;
        }

        public override string ToLS(bool indent = true)
        {
            var writer = new BlockWriter(GetType(), indent, Disabled);
            writer
                .Label(Label)
                .Token("EXECUTEJS")
                .Literal(JavascriptCode.Replace("\r\n", " ").Replace("\n", " "));

            if (!writer.CheckDefault(OutputVariable, "OutputVariable"))
            {
                writer
                    .Arrow()
                    .Token(IsCapture ? "CAP" : "VAR")
                    .Literal(OutputVariable);
            }

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

            data.Log(new LogEntry("Executing JS code!", Colors.White));
            object returned;
            if (CamoufoxBotBridge.TryGet(data, out var session))
                returned = session.ExecuteJs(ReplaceValues(javascriptCode, data));
            else
                returned = data.Driver.ExecuteScript(ReplaceValues(javascriptCode, data));

            if (returned != null)
            {
                try
                {
                    InsertVariable(data, isCapture, false, new List<string>() { returned.ToString() }, outputVariable, "", "", false, true);
                }
                catch
                {
                    throw new Exception("Failed to convert the returned value to a string");
                }
            }

            data.Log(new LogEntry("... executed!", Colors.White));
            BrowserSession.UpdateData(data);
        }
    }
}
