using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Extreme.Net;
using OpenBullet.Linux.Repositories;
using RuriLib.Models;
using RuriLib.ViewModels;

namespace OpenBullet.Linux.Services;

public sealed class ProxyManagerHost : ViewModelBase
{
    private readonly LiteDbRepository<CProxy> _repo;
    private CancellationTokenSource _checkCts;

    public ObservableCollection<CProxy> Proxies { get; } = new();

    public int Total { get; private set; }
    public int Working { get; private set; }
    public int NotWorking { get; private set; }
    public int Tested { get; private set; }

    public int BotsAmount { get; set; } = 10;
    public int TimeoutSeconds { get; set; } = 5;
    public bool OnlyUntested { get; set; } = true;
    public string TestSite { get; set; } = "https://api.ipify.org";
    public string SuccessKey { get; set; } = "ip";

    public bool IsChecking { get; private set; }
    public float CheckProgress { get; private set; }
    public string StatusMessage { get; private set; } = "";

    public ProxyManagerHost()
    {
        _repo = new LiteDbRepository<CProxy>(LinuxPaths.DatabaseFile, "proxies");
        Refresh();
    }

    public void Refresh()
    {
        Proxies.Clear();
        foreach (var p in _repo.Get().OrderBy(p => p.Proxy))
            Proxies.Add(p);
        UpdateStats();
        SetStatus($"Loaded {Proxies.Count} proxies");
    }

    public void ImportLines(IEnumerable<string> lines, ProxyType type = ProxyType.Http)
    {
        var added = new List<CProxy>();
        foreach (var line in lines.Where(l => !string.IsNullOrWhiteSpace(l)).Distinct())
        {
            try
            {
                var proxy = new CProxy().Parse(line.Trim(), type, "", "");
                if (!proxy.IsNumeric || proxy.IsValidNumeric)
                    added.Add(proxy);
            }
            catch { }
        }

        if (added.Count == 0)
        {
            SetStatus("No valid proxies imported");
            return;
        }

        foreach (var p in added)
            Proxies.Add(p);
        _repo.Add(added);
        UpdateStats();
        SetStatus($"Imported {added.Count} proxies");
    }

    public void ImportFile(string path)
    {
        if (!File.Exists(path)) return;
        ImportLines(File.ReadAllLines(path));
    }

    public void ExportSelected(IEnumerable<CProxy> items, string path)
    {
        File.WriteAllLines(path, items.Select(p => p.Proxy));
        SetStatus($"Exported {items.Count()} proxies");
    }

    public void DeleteSelected(IEnumerable<CProxy> items)
    {
        var list = items.ToList();
        foreach (var p in list)
            Proxies.Remove(p);
        _repo.Remove(list);
        UpdateStats();
        SetStatus($"Deleted {list.Count} proxies");
    }

    public void DeleteAll()
    {
        Proxies.Clear();
        _repo.RemoveAll();
        UpdateStats();
        SetStatus("Deleted all proxies");
    }

    public void DeleteNotWorking() => DeleteSelected(Proxies.Where(p => p.Working == ProxyWorking.NO));

    public async Task ToggleCheckAsync()
    {
        if (IsChecking)
        {
            _checkCts?.Cancel();
            return;
        }

        IsChecking = true;
        OnPropertyChanged(nameof(IsChecking));
        _checkCts = new CancellationTokenSource();
        var token = _checkCts.Token;

        var targets = (OnlyUntested
            ? Proxies.Where(p => p.Working == ProxyWorking.UNTESTED)
            : Proxies).ToList();

        var done = 0;
        using var gate = new SemaphoreSlim(BotsAmount, BotsAmount);
        var tasks = targets.Select(async proxy =>
        {
            await gate.WaitAsync(token);
            try
            {
                var ok = await CheckProxyAsync(proxy, token);
                proxy.Working = ok ? ProxyWorking.YES : ProxyWorking.NO;
                proxy.LastChecked = DateTime.Now;
                _repo.Update(proxy);
            }
            catch
            {
                proxy.Working = ProxyWorking.NO;
            }
            finally
            {
                done++;
                CheckProgress = targets.Count == 0 ? 0 : 100f * done / targets.Count;
                OnPropertyChanged(nameof(CheckProgress));
                UpdateStats();
                gate.Release();
            }
        });

        try
        {
            await Task.WhenAll(tasks);
            SetStatus($"Checked {targets.Count} proxies");
        }
        catch (OperationCanceledException)
        {
            SetStatus("Proxy check aborted");
        }
        finally
        {
            IsChecking = false;
            OnPropertyChanged(nameof(IsChecking));
            CheckProgress = 0;
            OnPropertyChanged(nameof(CheckProgress));
        }
    }

    private async Task<bool> CheckProxyAsync(CProxy proxy, CancellationToken token)
    {
        token.ThrowIfCancellationRequested();
        var timeout = TimeoutSeconds * 1000;
        using var request = new HttpRequest();
        request.Proxy = proxy.GetClient();
        request.Proxy.ConnectTimeout = timeout;
        request.Proxy.ReadWriteTimeout = timeout;
        request.ConnectTimeout = timeout;
        request.ReadWriteTimeout = timeout;
        var response = await request.GetAsync(TestSite);
        return response.ToString().Contains(SuccessKey, StringComparison.OrdinalIgnoreCase);
    }

    private void UpdateStats()
    {
        Total = Proxies.Count;
        Tested = Proxies.Count(p => p.Working != ProxyWorking.UNTESTED);
        Working = Proxies.Count(p => p.Working == ProxyWorking.YES);
        NotWorking = Proxies.Count(p => p.Working == ProxyWorking.NO);
        OnPropertyChanged(nameof(Total));
        OnPropertyChanged(nameof(Working));
        OnPropertyChanged(nameof(NotWorking));
        OnPropertyChanged(nameof(Tested));
    }

    private void SetStatus(string msg)
    {
        StatusMessage = msg;
        OnPropertyChanged(nameof(StatusMessage));
    }
}
