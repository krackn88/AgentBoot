using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using RuriLib;
using RuriLib.ViewModels;

namespace OpenBullet.Linux.Services;

/// <summary>Disk config store (upstream <c>ConfigRepository</c> without WPF/OB statics).</summary>
public sealed class LinuxConfigRepository
{
    public const string DefaultCategory = "Default";
    public string BaseFolder { get; }

    public LinuxConfigRepository(string baseFolder)
    {
        BaseFolder = baseFolder;
        Directory.CreateDirectory(baseFolder);
    }

    public IEnumerable<ConfigViewModel> Get()
    {
        var configs = new List<ConfigViewModel>();

        foreach (var file in Directory.EnumerateFiles(BaseFolder).Where(f => f.EndsWith(".loli", StringComparison.OrdinalIgnoreCase)))
        {
            try
            {
                configs.Add(new ConfigViewModel(
                    Path.GetFileNameWithoutExtension(file),
                    DefaultCategory,
                    IOManager.LoadConfig(file)));
            }
            catch
            {
                // Skip corrupt configs like upstream.
            }
        }

        foreach (var categoryFolder in Directory.EnumerateDirectories(BaseFolder))
        {
            foreach (var file in Directory.EnumerateFiles(categoryFolder).Where(f => f.EndsWith(".loli", StringComparison.OrdinalIgnoreCase)))
            {
                try
                {
                    configs.Add(new ConfigViewModel(
                        Path.GetFileNameWithoutExtension(file),
                        Path.GetFileName(categoryFolder),
                        IOManager.LoadConfig(file)));
                }
                catch { }
            }
        }

        return configs;
    }

    public void Add(ConfigViewModel entity)
    {
        var path = GetPath(entity);
        if (entity.Category != DefaultCategory)
            Directory.CreateDirectory(Path.Combine(BaseFolder, entity.Category));

        if (File.Exists(path))
            throw new IOException("A config with the same name and category already exists");

        IOManager.SaveConfig(entity.Config, path);
    }

    public void Update(ConfigViewModel entity)
    {
        var path = GetPath(entity);
        if (!File.Exists(path))
            throw new IOException("File not found");
        IOManager.SaveConfig(entity.Config, path);
    }

    public void Remove(ConfigViewModel entity)
    {
        var path = GetPath(entity);
        if (!File.Exists(path))
            throw new IOException("File not found");
        File.Delete(path);
    }

    private string GetPath(ConfigViewModel config) => GetPath(config.Category, config.FileName);

    private string GetPath(string category, string fileName)
    {
        var file = $"{fileName}.loli";
        return category != DefaultCategory
            ? Path.Combine(BaseFolder, category, file)
            : Path.Combine(BaseFolder, file);
    }
}
