using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Linq;
using System.Reflection;
using Newtonsoft.Json;
using RuriLib;
using RuriLib.ViewModels;

namespace OpenBullet.Linux.Services;

public sealed class BlockPropertyRow : ViewModelBase
{
    public string Name { get; init; }
    public string Value { get; set; }
    public string TypeName { get; init; }
    public bool IsEnum { get; init; }
    public bool IsBoolean => TypeName == "Boolean";
    public bool IsStringField => !IsEnum && !IsBoolean;
    public bool BoolValue
    {
        get => string.Equals(Value, "True", StringComparison.OrdinalIgnoreCase);
        set => Value = value ? "True" : "False";
    }
    public ObservableCollection<string> EnumOptions { get; init; }
}

public sealed class BlockPropertyEditorHost : ViewModelBase
{
    private BlockBase _block;
    private Action _onChanged;

    public string BlockTypeName { get; private set; } = "(no block)";
    public ObservableCollection<BlockPropertyRow> Rows { get; } = new();

    public void Bind(BlockBase block, Action onChanged)
    {
        _block = block;
        _onChanged = onChanged;
        Rows.Clear();
        if (block == null)
        {
            BlockTypeName = "(no block)";
            OnPropertyChanged(nameof(BlockTypeName));
            return;
        }

        var name = block.GetType().Name;
        if (name.StartsWith("Block", StringComparison.Ordinal))
            name = name["Block".Length..];
        BlockTypeName = name;
        OnPropertyChanged(nameof(BlockTypeName));

        foreach (var prop in GetEditableProperties(block.GetType()))
        {
            var val = prop.GetValue(block);
            var row = new BlockPropertyRow
            {
                Name = prop.Name,
                TypeName = prop.PropertyType.Name,
                IsEnum = prop.PropertyType.IsEnum,
                EnumOptions = prop.PropertyType.IsEnum
                    ? new ObservableCollection<string>(Enum.GetNames(prop.PropertyType))
                    : null,
                Value = FormatValue(val)
            };
            Rows.Add(row);
        }
    }

    public void ApplyRow(BlockPropertyRow row)
    {
        if (_block == null || row == null) return;
        var prop = _block.GetType().GetProperty(row.Name);
        if (prop == null || !prop.CanWrite) return;

        try
        {
            object parsed = row.IsEnum
                ? Enum.Parse(prop.PropertyType, row.Value)
                : Convert.ChangeType(row.Value, prop.PropertyType);
            prop.SetValue(_block, parsed);
            _onChanged?.Invoke();
        }
        catch
        {
            // keep UI stable on bad input
        }
    }

    private static IEnumerable<PropertyInfo> GetEditableProperties(Type type)
    {
        var skip = new HashSet<string> { "Item" };
        for (var t = type; t != null && t != typeof(object); t = t.BaseType)
        {
            foreach (var p in t.GetProperties(BindingFlags.Public | BindingFlags.Instance | BindingFlags.DeclaredOnly))
            {
                if (!p.CanRead || !p.CanWrite || skip.Contains(p.Name)) continue;
                if (p.GetCustomAttribute<JsonIgnoreAttribute>() != null) continue;
                if (p.PropertyType.IsClass && p.PropertyType != typeof(string) && !p.PropertyType.IsEnum) continue;
                if (p.PropertyType.IsGenericType) continue;
                yield return p;
            }
        }
    }

    private static string FormatValue(object val)
    {
        if (val == null) return "";
        if (val is bool b) return b ? "True" : "False";
        return val.ToString();
    }
}
