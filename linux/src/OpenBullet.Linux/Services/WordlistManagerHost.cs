using System;
using System.Collections.ObjectModel;
using System.IO;
using System.Linq;
using RuriLib.Models;
using RuriLib.ViewModels;

namespace OpenBullet.Linux.Services;

public sealed class WordlistManagerHost : ViewModelBase
{
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
            Rescan();
        }
    }

    public string StatusMessage { get; private set; } = "";

    public WordlistManagerHost()
    {
        Rescan();
    }

    public void Rescan()
    {
        Wordlists.Clear();
        if (!Directory.Exists(LinuxPaths.WordlistsFolder))
            Directory.CreateDirectory(LinuxPaths.WordlistsFolder);

        var q = _search.Trim().ToLowerInvariant();
        foreach (var file in Directory.EnumerateFiles(LinuxPaths.WordlistsFolder, "*.txt"))
        {
            var name = Path.GetFileNameWithoutExtension(file);
            if (q.Length > 0 && !name.ToLowerInvariant().Contains(q))
                continue;
            Wordlists.Add(new Wordlist(name, file, "Default", ""));
        }

        SetStatus($"Found {Wordlists.Count} wordlist(s)");
    }

    public void Select(Wordlist wl)
    {
        Selected = wl;
        SetStatus(wl == null ? "No selection" : $"Selected {wl.Name}");
    }

    public void AddFromPath(string path)
    {
        if (!File.Exists(path)) return;
        var dest = Path.Combine(LinuxPaths.WordlistsFolder, Path.GetFileName(path));
        if (!File.Exists(dest))
            File.Copy(path, dest);
        Rescan();
    }

    public void DeleteSelected(Wordlist wl)
    {
        if (wl == null) return;
        try
        {
            if (File.Exists(wl.Path))
                File.Delete(wl.Path);
        }
        catch { }

        Wordlists.Remove(wl);
        SetStatus($"Deleted {wl.Name}");
    }

    private void SetStatus(string msg)
    {
        StatusMessage = msg;
        OnPropertyChanged(nameof(StatusMessage));
    }
}
