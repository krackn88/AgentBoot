using System;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using Avalonia.Threading;
using Extreme.Net;
using RuriLib;
using RuriLib.LS;
using RuriLib.Models;
using RuriLib.ViewModels;

namespace OpenBullet.Linux.Services;

public sealed class StackerDebuggerHost : ViewModelBase
{
    private CancellationTokenSource _cts;

    public string TestData { get; set; } = "test:data";
    public string TestProxy { get; set; } = "";
    public bool UseProxy { get; set; }
    public ProxyType ProxyType { get; set; } = ProxyType.Http;

    public string LogText { get; private set; } = "";
    public bool IsRunning { get; private set; }
    public string StatusMessage { get; private set; } = "";

    public void ReceiveFromRunner(string data, string proxy, ProxyType proxyType)
    {
        TestData = data ?? "";
        TestProxy = proxy ?? "";
        ProxyType = proxyType;
        UseProxy = !string.IsNullOrWhiteSpace(proxy);
        OnPropertyChanged(nameof(TestData));
        OnPropertyChanged(nameof(TestProxy));
        OnPropertyChanged(nameof(UseProxy));
        SetStatus("Loaded hit into debugger test fields");
    }

    public async Task ToggleRunAsync(StackerHost stacker)
    {
        if (IsRunning)
        {
            _cts?.Cancel();
            return;
        }

        if (stacker?.Config?.Config == null)
        {
            SetStatus("Load a config in Stacker first");
            return;
        }

        _cts = new CancellationTokenSource();
        IsRunning = true;
        OnPropertyChanged(nameof(IsRunning));
        LogText = "";
        OnPropertyChanged(nameof(LogText));

        try
        {
            await Task.Run(() => RunScript(stacker, _cts.Token));
            SetStatus("Debugger finished");
        }
        catch (OperationCanceledException)
        {
            AppendLog("Debugger aborted");
            SetStatus("Debugger aborted");
        }
        catch (Exception ex)
        {
            AppendLog($"ERROR: {ex.Message}");
            SetStatus("Debugger failed");
        }
        finally
        {
            IsRunning = false;
            OnPropertyChanged(nameof(IsRunning));
        }
    }

    private void RunScript(StackerHost stacker, CancellationToken token)
    {
        var settings = File.Exists(LinuxPaths.RlSettingsJson)
            ? IOManager.LoadSettings<RLSettingsViewModel>(LinuxPaths.RlSettingsJson)
            : new RLSettingsViewModel();

        var ls = new LoliScript(stacker.Script);
        ls.Reset();

        CProxy proxy = null;
        if (UseProxy && !string.IsNullOrWhiteSpace(TestProxy))
        {
            proxy = TestProxy.TrimStart().StartsWith("(")
                ? new CProxy().Parse(TestProxy)
                : new CProxy(TestProxy, ProxyType);
        }

        var cData = new CData(TestData, new WordlistType { Name = "Default" });
        var bot = new BotData(settings, stacker.Config.Config.Settings, cData, proxy, UseProxy, new Random());

        while (ls.CanProceed && !token.IsCancellationRequested)
        {
            var line = ls.CurrentLine;
            ls.TakeStep(bot);
            Dispatcher.UIThread.Post(() => AppendLog($"OK {Truncate(line, 80)}"));
        }

        if (!token.IsCancellationRequested)
            Dispatcher.UIThread.Post(() => AppendLog("End of script"));
    }

    private static string Truncate(string s, int max) =>
        string.IsNullOrEmpty(s) || s.Length <= max ? s : s[..max] + "…";

    private void AppendLog(string line)
    {
        LogText += $"{DateTime.Now:HH:mm:ss} {line}{Environment.NewLine}";
        OnPropertyChanged(nameof(LogText));
    }

    private void SetStatus(string msg)
    {
        StatusMessage = msg;
        OnPropertyChanged(nameof(StatusMessage));
    }
}
