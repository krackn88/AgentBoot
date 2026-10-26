using System;
using System.Collections.Generic;
using System.Linq;
using OpenBullet.Linux.Repositories;
using RuriLib;
using RuriLib.Interfaces;
using RuriLib.Models;
using RuriLib.ViewModels;

namespace OpenBullet.Linux.Services;

public sealed class LinuxLogger : ILogger
{
    private readonly List<LogEntry> _entries = new();

    public bool Enabled => true;
    public int BufferSize => 10_000;
    public IEnumerable<LogEntry> Entries => _entries;

    public void Log(string message, LogLevel level = LogLevel.Info, bool prompt = false, int timeout = 0)
    {
        _entries.Add(new LogEntry("Linux", message, level));
    }
}

public sealed class LinuxAlerter : IAlerter
{
    public bool YesOrNo(string message, string title) => true;
}

public sealed class LinuxHitsDbAdapter : IHitsDB
{
    private readonly HitsDbHost _host;
    private readonly LiteDbRepository<Hit> _repo;

    public LinuxHitsDbAdapter(HitsDbHost host)
    {
        _host = host;
        _repo = new LiteDbRepository<Hit>(LinuxPaths.DatabaseFile, "hits");
    }

    public IEnumerable<Hit> Hits => _repo.Get();

    public void Add(Hit hit) => _host.AddFromRunner(hit);

    public void Remove(Hit hit) => _repo.Remove(hit);

    public void Remove(IEnumerable<Hit> hits)
    {
        foreach (var h in hits.ToList())
            _repo.Remove(h);
    }

    public void Update(Hit hit) => _repo.Update(hit);

    public void RemoveAll() => _repo.RemoveAll();

    public void DeleteDuplicates() { }
}

public sealed class LinuxWordlistManagerAdapter : IWordlistManager
{
    private readonly WordlistManagerHost _host;

    public LinuxWordlistManagerAdapter(WordlistManagerHost host) => _host = host;

    public IEnumerable<Wordlist> Wordlists => _host.Wordlists;

    public void Add(Wordlist wordlist) => _host.AddFromPath(wordlist.Path);

    public void Update(Wordlist wordlist) { }

    public void Remove(Wordlist wordlist) => _host.DeleteSelected(wordlist);

    public void DeleteNotFound() => _host.DeleteNotFound();

    public void RemoveAll() => _host.PurgeAll();
}

public sealed class LinuxConfigManagerAdapter : IConfigManager
{
    private readonly ConfigManagerHost _host;

    public LinuxConfigManagerAdapter(ConfigManagerHost host) => _host = host;

    public IEnumerable<ConfigViewModel> Configs => _host.AllConfigs;

    public void Add(ConfigViewModel config) { }

    public void Rescan() => _host.Rescan();

    public void Remove(ConfigViewModel config) => _host.DeleteSelected(new[] { config });

    public void Remove(IEnumerable<ConfigViewModel> configs) => _host.DeleteSelected(configs);

    public void Update(ConfigViewModel config) => _host.SaveConfig(config);
}

public sealed class LinuxApplicationBridge : IApplication
{
    public LinuxApplicationBridge(AppShell shell)
    {
        WordlistManager = new LinuxWordlistManagerAdapter(shell.Wordlists);
        ConfigManager = new LinuxConfigManagerAdapter(shell.Configs);
        HitsDB = new LinuxHitsDbAdapter(shell.Hits);
        Logger = new LinuxLogger();
        Alerter = new LinuxAlerter();
    }

    public IRunnerManager RunnerManager { get; set; }
    public IProxyManager ProxyManager { get; set; }
    public IProxyChecker ProxyChecker { get; set; }
    public IWordlistManager WordlistManager { get; }
    public IConfigManager ConfigManager { get; }
    public IHitsDB HitsDB { get; }
    public IAlerter Alerter { get; }
    public ILogger Logger { get; }
    public ISettings Settings { get; set; }
}
