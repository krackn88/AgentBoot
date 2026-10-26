using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.IO;
using System.Linq;
using System.Text;
using OpenBullet.Linux.Repositories;
using RuriLib.Models;
using RuriLib.ViewModels;

namespace OpenBullet.Linux.Services;

public sealed class HitsDbHost : ViewModelBase
{
    public const string AllTypes = "All";
    public const string AllConfigs = "All";

    private readonly LiteDbRepository<Hit> _repo;
    private readonly List<Hit> _all = new();

    public ObservableCollection<Hit> FilteredHits { get; } = new();

    public string SearchString
    {
        get => _search;
        set
        {
            _search = value ?? "";
            OnPropertyChanged(nameof(SearchString));
            ApplyFilter();
        }
    }

    private string _search = "";

    public string TypeFilter
    {
        get => _typeFilter;
        set
        {
            _typeFilter = value ?? "SUCCESS";
            OnPropertyChanged(nameof(TypeFilter));
            ApplyFilter();
        }
    }

    private string _typeFilter = "SUCCESS";

    public string ConfigFilter
    {
        get => _configFilter;
        set
        {
            _configFilter = value ?? AllConfigs;
            OnPropertyChanged(nameof(ConfigFilter));
            ApplyFilter();
        }
    }

    private string _configFilter = AllConfigs;

    public int Total => _all.Count;
    public int Filtered => FilteredHits.Count;
    public string StatusMessage { get; private set; } = "";

    public ObservableCollection<string> TypeOptions { get; } = new() { AllTypes, "SUCCESS", "NONE", "FAIL", "RETRY", "BAN", "CUSTOM" };
    public ObservableCollection<string> ConfigOptions { get; } = new() { AllConfigs };

    public HitsDbHost()
    {
        _repo = new LiteDbRepository<Hit>(LinuxPaths.DatabaseFile, "hits");
        Refresh();
    }

    public void Refresh()
    {
        _all.Clear();
        _all.AddRange(_repo.Get().OrderByDescending(h => h.Date));
        RebuildConfigOptions();
        ApplyFilter();
        SetStatus($"Loaded {Total} hits");
    }

    public void DeleteSelected(IEnumerable<Hit> hits)
    {
        var list = hits.ToList();
        foreach (var h in list)
            _all.Remove(h);
        _repo.Remove(list);
        ApplyFilter();
        SetStatus($"Deleted {list.Count} hits");
    }

    public void DeleteAll()
    {
        _all.Clear();
        _repo.RemoveAll();
        ApplyFilter();
        SetStatus("Deleted all hits");
    }

    public void ExportSelected(IEnumerable<Hit> hits, string path, bool fullDetails)
    {
        var lines = hits.Select(h => fullDetails
            ? $"Data={h.Data} | Type={h.Type} | Config={h.ConfigName} | Wordlist={h.WordlistName} | Proxy={h.Proxy} | Date={h.Date:O} | Captured={h.CapturedString}"
            : $"{h.Data} | {h.CapturedString}");
        File.WriteAllLines(path, lines, Encoding.UTF8);
        SetStatus($"Exported {hits.Count()} hits");
    }

    private void RebuildConfigOptions()
    {
        ConfigOptions.Clear();
        ConfigOptions.Add(AllConfigs);
        foreach (var c in _all.Select(h => h.ConfigName).Where(n => !string.IsNullOrEmpty(n)).Distinct().OrderBy(n => n))
            ConfigOptions.Add(c);
    }

    private void ApplyFilter()
    {
        FilteredHits.Clear();
        var q = _search.Trim().ToLowerInvariant();
        foreach (var h in _all)
        {
            if (TypeFilter != AllTypes && h.Type != TypeFilter) continue;
            if (ConfigFilter != AllConfigs && h.ConfigName != ConfigFilter) continue;
            if (q.Length > 0)
            {
                var cap = h.CapturedData?.ToCaptureString() ?? h.CapturedString ?? "";
                if (!h.Data.ToLowerInvariant().Contains(q) && !cap.ToLowerInvariant().Contains(q))
                    continue;
            }

            FilteredHits.Add(h);
        }

        OnPropertyChanged(nameof(Total));
        OnPropertyChanged(nameof(Filtered));
    }

    private void SetStatus(string msg)
    {
        StatusMessage = msg;
        OnPropertyChanged(nameof(StatusMessage));
    }
}
