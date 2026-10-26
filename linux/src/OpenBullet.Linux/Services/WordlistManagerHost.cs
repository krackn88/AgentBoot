using System;
using System.Collections.ObjectModel;
using System.IO;
using System.Linq;
using OpenBullet.Linux.Repositories;
using RuriLib;
using RuriLib.Models;
using EnvironmentSettings = RuriLib.Models.EnvironmentSettings;
using RuriLib.ViewModels;

namespace OpenBullet.Linux.Services;

public sealed class WordlistManagerHost : ViewModelBase
{
    private readonly LiteDbRepository<Wordlist> _repo;

    public ObservableCollection<Wordlist> Wordlists { get; } = new();

    public Wordlist Selected { get; private set; }

    private string _search = "";
    public string SearchString
    {
        get => _search;
        set
        {
            _search = value ?? "";
            OnPropertyChanged(nameof(SearchString));
            RefreshView();
        }
    }

    public string StatusMessage { get; private set; } = "";

    public WordlistManagerHost()
    {
        _repo = new LiteDbRepository<Wordlist>(LinuxPaths.DatabaseFile, "wordlists");
        ImportMissingFromFolder();
        RefreshView();
    }

    public void RefreshView()
    {
        Wordlists.Clear();
        var q = _search.Trim().ToLowerInvariant();
        foreach (var wl in _repo.Get().OrderBy(w => w.Name))
        {
            if (q.Length > 0 &&
                !wl.Name.ToLowerInvariant().Contains(q) &&
                !(wl.Purpose ?? "").ToLowerInvariant().Contains(q))
                continue;
            Wordlists.Add(wl);
        }

        SetStatus($"Showing {Wordlists.Count} wordlist(s) from LiteDB");
    }

    public void Select(Wordlist wl)
    {
        Selected = wl;
        SetStatus(wl == null ? "No selection" : $"Selected {wl.Name} ({wl.Total} lines)");
    }

    public void AddFromPath(string path)
    {
        if (!File.Exists(path)) return;
        var dest = Path.Combine(LinuxPaths.WordlistsFolder, Path.GetFileName(path));
        if (!File.Exists(dest))
            File.Copy(path, dest);

        var wl = FileToWordlist(dest);
        if (Wordlists.Any(w => w.Path == wl.Path) || _repo.Get().Any(w => w.Path == wl.Path))
        {
            SetStatus("Wordlist already in database");
            return;
        }

        _repo.Add(wl);
        RefreshView();
        SetStatus($"Added {wl.Name}");
    }

    public void DeleteSelected(Wordlist wl)
    {
        if (wl == null) return;
        try
        {
            if (File.Exists(wl.Path) && !wl.Temporary)
                File.Delete(wl.Path);
        }
        catch { }

        _repo.Remove(wl);
        Wordlists.Remove(wl);
        SetStatus($"Deleted {wl.Name}");
    }

    public void DeleteNotFound()
    {
        var missing = _repo.Get().Where(w => !File.Exists(w.Path)).ToList();
        foreach (var w in missing)
            _repo.Remove(w);
        RefreshView();
        SetStatus($"Removed {missing.Count} missing file reference(s)");
    }

    public void PurgeAll()
    {
        _repo.RemoveAll();
        RefreshView();
        SetStatus("Purged wordlist DB");
    }

    private void ImportMissingFromFolder()
    {
        Directory.CreateDirectory(LinuxPaths.WordlistsFolder);
        var existing = _repo.Get().Select(w => w.Path).ToHashSet(StringComparer.OrdinalIgnoreCase);
        foreach (var file in Directory.EnumerateFiles(LinuxPaths.WordlistsFolder, "*.txt"))
        {
            if (existing.Contains(file)) continue;
            try
            {
                _repo.Add(FileToWordlist(file));
            }
            catch { }
        }
    }

    private static Wordlist FileToWordlist(string path)
    {
        var env = File.Exists(LinuxPaths.EnvironmentIni)
            ? IOManager.ParseEnvironmentSettings(LinuxPaths.EnvironmentIni)
            : new EnvironmentSettings();
        var firstType = env.WordlistTypes.FirstOrDefault()?.Name ?? "Default";
        var wl = new Wordlist(Path.GetFileNameWithoutExtension(path), path, firstType, "");
        if (File.Exists(path))
        {
            var first = File.ReadLines(path).FirstOrDefault() ?? "";
            wl.Type = env.RecognizeWordlistType(first);
        }

        return wl;
    }

    private void SetStatus(string msg)
    {
        StatusMessage = msg;
        OnPropertyChanged(nameof(StatusMessage));
    }
}
