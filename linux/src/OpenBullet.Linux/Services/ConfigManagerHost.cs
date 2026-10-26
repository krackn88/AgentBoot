using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.IO;
using System.Linq;
using RuriLib;
using RuriLib.ViewModels;

namespace OpenBullet.Linux.Services;

public sealed class ConfigManagerHost : ViewModelBase
{
    private readonly LinuxConfigRepository _repo;

    public ObservableCollection<ConfigViewModel> AllConfigs { get; } = new();
    public ObservableCollection<ConfigViewModel> FilteredConfigs { get; } = new();

    public ConfigViewModel CurrentConfig { get; private set; }
    public string CurrentConfigName => CurrentConfig?.Name ?? "None";
    public int Total => FilteredConfigs.Count;

    public ObservableCollection<string> Categories { get; } = new() { "All" };

    private string _categoryFilter = "All";
    public string CategoryFilter
    {
        get => _categoryFilter;
        set
        {
            _categoryFilter = value ?? "All";
            OnPropertyChanged(nameof(CategoryFilter));
            ApplyFilter();
        }
    }

    private string _searchString = "";
    public string SearchString
    {
        get => _searchString;
        set
        {
            _searchString = value ?? "";
            OnPropertyChanged(nameof(SearchString));
            ApplyFilter();
        }
    }

    public string StatusMessage { get; private set; } = "";

    public ConfigManagerHost()
    {
        _repo = new LinuxConfigRepository(LinuxPaths.ConfigsFolder);
        Rescan();
    }

    public void Rescan()
    {
        AllConfigs.Clear();
        foreach (var c in _repo.Get().OrderByDescending(c => c.Config.Settings.LastModified))
            AllConfigs.Add(c);
        RebuildCategories();
        ApplyFilter();
        SetStatus($"Rescanned — {AllConfigs.Count} config(s)");
    }

    public void Select(ConfigViewModel config)
    {
        CurrentConfig = config;
        OnPropertyChanged(nameof(CurrentConfig));
        OnPropertyChanged(nameof(CurrentConfigName));
        SetStatus($"Selected {config?.Name}");
    }

    public void LoadSelected(ConfigViewModel config)
    {
        if (config == null) return;
        Select(config);
    }

    public void SaveCurrent()
    {
        if (CurrentConfig == null)
        {
            SetStatus("No config selected");
            return;
        }

        CurrentConfig.Config.Settings.LastModified = DateTime.Now;
        _repo.Update(CurrentConfig);
        SetStatus($"Saved {CurrentConfig.Name}");
    }

    public void SaveConfig(ConfigViewModel vm)
    {
        if (vm == null) return;
        vm.Config.Settings.LastModified = DateTime.Now;
        _repo.Update(vm);
        SetStatus($"Saved {vm.Name}");
    }

    public void DeleteSelected(IEnumerable<ConfigViewModel> items)
    {
        foreach (var item in items.ToList())
        {
            _repo.Remove(item);
            AllConfigs.Remove(item);
            if (CurrentConfig == item)
                Select(null);
        }

        ApplyFilter();
        SetStatus("Deleted selected config(s)");
    }

    public ConfigViewModel CreateNew(string name)
    {
        name = string.IsNullOrWhiteSpace(name) ? $"Config_{DateTime.Now:yyyyMMdd_HHmmss}" : name.Trim();
        var settings = new ConfigSettings { Name = name, SuggestedBots = 1 };
        var cfg = new Config(settings, "");
        var vm = new ConfigViewModel(name, LinuxConfigRepository.DefaultCategory, cfg);
        _repo.Add(vm);
        AllConfigs.Insert(0, vm);
        ApplyFilter();
        Select(vm);
        SetStatus($"Created {name}");
        return vm;
    }

    public void EnsureSmokeFixtureImported()
    {
        var smokePath = Path.Combine(LinuxPaths.FindRepoLinuxDir() ?? "", "fixtures", "smoke.loli");
        if (!File.Exists(smokePath)) return;

        var dest = Path.Combine(LinuxPaths.ConfigsFolder, "smoke.loli");
        if (!File.Exists(dest))
        {
            Directory.CreateDirectory(LinuxPaths.ConfigsFolder);
            File.Copy(smokePath, dest);
            Rescan();
        }
    }

    private void RebuildCategories()
    {
        Categories.Clear();
        Categories.Add("All");
        foreach (var cat in AllConfigs.Select(c => c.Category).Where(c => !string.IsNullOrEmpty(c)).Distinct().OrderBy(c => c))
            Categories.Add(cat);
        OnPropertyChanged(nameof(Categories));
    }

    private void ApplyFilter()
    {
        FilteredConfigs.Clear();
        var q = _searchString.Trim().ToLowerInvariant();
        foreach (var c in AllConfigs)
        {
            if (CategoryFilter != "All" && c.Category != CategoryFilter) continue;
            if (q.Length > 0)
            {
                var author = c.Config?.Settings?.Author ?? "";
                if (!c.Name.ToLowerInvariant().Contains(q) &&
                    !c.Category.ToLowerInvariant().Contains(q) &&
                    !author.ToLowerInvariant().Contains(q))
                    continue;
            }

            FilteredConfigs.Add(c);
        }

        OnPropertyChanged(nameof(Total));
    }

    private void SetStatus(string message)
    {
        StatusMessage = message;
        OnPropertyChanged(nameof(StatusMessage));
    }
}
