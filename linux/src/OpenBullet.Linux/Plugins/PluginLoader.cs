using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using PluginFramework;
using RuriLib;

namespace OpenBullet.Linux.Plugins;

public sealed class PluginLoadResult
{
    public IReadOnlyList<IBlockPlugin> BlockPlugins { get; init; } = Array.Empty<IBlockPlugin>();
    public IReadOnlyList<string> PluginNames { get; init; } = Array.Empty<string>();
    public IReadOnlyList<Type> UiPluginTypes { get; init; } = Array.Empty<Type>();
    public IReadOnlyList<string> Errors { get; init; } = Array.Empty<string>();
}

/// <summary>Loads block plugins from <c>Plugins/</c> (upstream-compatible layout).</summary>
public static class PluginLoader
{
    public static PluginLoadResult Load(string folder)
    {
        var blockPlugins = new List<IBlockPlugin>();
        var pluginNames = new List<string>();
        var uiTypes = new List<Type>();
        var errors = new List<string>();

        if (!Directory.Exists(folder))
            return new PluginLoadResult();

        Hook(folder);

        foreach (var dll in Directory.GetFiles(folder, "*.dll"))
        {
            try
            {
                var asm = Assembly.LoadFrom(dll);
                var depFolder = Path.Combine(folder, Path.GetFileNameWithoutExtension(dll));
                if (Directory.Exists(depFolder))
                    Hook(depFolder);

                LoadDependencies(asm.GetReferencedAssemblies());

                foreach (var type in asm.GetTypes())
                {
                    if (type.GetInterface(nameof(IPlugin)) == typeof(IPlugin))
                    {
                        pluginNames.Add(type.Name);
                        uiTypes.Add(type);
                    }

                    if (type.GetInterface(nameof(IBlockPlugin)) == typeof(IBlockPlugin)
                        && type.IsSubclassOf(typeof(BlockBase)))
                    {
                        if (Activator.CreateInstance(type) is IBlockPlugin plugin)
                            blockPlugins.Add(plugin);
                    }
                }
            }
            catch (Exception ex)
            {
                errors.Add($"{Path.GetFileName(dll)}: {ex.Message}");
            }
        }

        return new PluginLoadResult
        {
            BlockPlugins = blockPlugins,
            PluginNames = pluginNames,
            UiPluginTypes = uiTypes,
            Errors = errors
        };
    }

    private static void LoadDependencies(IEnumerable<AssemblyName> assemblies)
    {
        foreach (var asm in assemblies)
        {
            if (AppDomain.CurrentDomain.GetAssemblies().Any(a => a.GetName().FullName == asm.FullName))
                continue;

            try
            {
                AppDomain.CurrentDomain.Load(asm);
                LoadDependencies(Assembly.Load(asm).GetReferencedAssemblies());
            }
            catch
            {
                // Optional dependency — same as upstream Loader.
            }
        }
    }

    private static void Hook(params string[] folders)
    {
        AppDomain.CurrentDomain.AssemblyResolve += (_, args) =>
        {
            var loaded = AppDomain.CurrentDomain.GetAssemblies()
                .FirstOrDefault(a => a.FullName == args.Name);
            if (loaded != null)
                return loaded;

            var n = new AssemblyName(args.Name);
            if (n.Name.EndsWith(".xmlserializers", StringComparison.OrdinalIgnoreCase)
                || n.Name.EndsWith(".resources", StringComparison.OrdinalIgnoreCase))
                return null;

            foreach (var dir in folders)
            {
                var assy = new[] { "*.dll", "*.exe" }.SelectMany(g => Directory.EnumerateFiles(dir, g))
                    .FirstOrDefault(f =>
                    {
                        try
                        {
                            return n.Name.Equals(AssemblyName.GetAssemblyName(f).Name, StringComparison.OrdinalIgnoreCase);
                        }
                        catch (BadImageFormatException)
                        {
                            return false;
                        }
                    });

                if (assy != null)
                    return Assembly.LoadFrom(assy);
            }

            return null;
        };
    }
}
