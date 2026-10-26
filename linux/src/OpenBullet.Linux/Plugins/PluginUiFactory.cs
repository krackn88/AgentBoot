using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using Avalonia.Controls;
using PluginFramework;
using PluginButton = PluginFramework.Attributes.Button;
using PluginFramework.Attributes;
using RuriLib.Interfaces;

namespace OpenBullet.Linux.Plugins;

public static class PluginUiFactory
{
    private static readonly Dictionary<Type, Type> InputTypes = new()
    {
        { typeof(InfoText), typeof(string) },
        { typeof(Text), typeof(string) },
        { typeof(Numeric), typeof(int) },
        { typeof(Checkbox), typeof(bool) },
        { typeof(TextMulti), typeof(string[]) },
        { typeof(FilePicker), typeof(string) },
        { typeof(Dropdown), typeof(string) }
    };

    public static (IPlugin Instance, Control Panel) Build(Type pluginType, IApplication app)
    {
        var ctor = pluginType.GetConstructors()
            .FirstOrDefault(c => c.GetParameters().Any(p => p.ParameterType == typeof(IApplication)));
        var instance = ctor != null
            ? Activator.CreateInstance(pluginType, app) as IPlugin
            : Activator.CreateInstance(pluginType) as IPlugin;

        if (instance == null)
            throw new InvalidOperationException($"Could not create plugin {pluginType.Name}");

        var panel = new StackPanel { Spacing = 8 };
        panel.Children.Add(new TextBlock { Text = instance.Name, FontWeight = Avalonia.Media.FontWeight.Bold });

        foreach (var prop in pluginType.GetProperties().Where(IsInputProperty))
            panel.Children.Add(BuildField(instance, prop));

        foreach (var method in pluginType.GetMethods().Where(m => IsButtonMethod(m)))
            panel.Children.Add(BuildButton(instance, method));

        return (instance, panel);
    }

    private static bool IsInputProperty(PropertyInfo property)
    {
        var attrs = property.GetCustomAttributes<InputField>().ToList();
        if (attrs.Count != 1) return false;
        return InputTypes.TryGetValue(attrs[0].GetType(), out var t) && property.PropertyType == t;
    }

    private static bool IsButtonMethod(MethodInfo method)
    {
        if (method.GetCustomAttributes<PluginButton>().Count() != 1) return false;
        var p = method.GetParameters();
        return p.Length == 0 || (p.Length == 1 && p[0].ParameterType == typeof(IApplication));
    }

    private static Control BuildField(IPlugin plugin, PropertyInfo prop)
    {
        var stack = new StackPanel { Spacing = 4 };
        stack.Children.Add(new TextBlock { Text = prop.Name });

        if (prop.PropertyType == typeof(string))
        {
            var box = new TextBox { Text = prop.GetValue(plugin)?.ToString() ?? "" };
            box.LostFocus += (_, _) => prop.SetValue(plugin, box.Text);
            stack.Children.Add(box);
        }
        else if (prop.PropertyType == typeof(int))
        {
            var box = new TextBox { Text = (prop.GetValue(plugin) ?? 0).ToString() };
            box.LostFocus += (_, _) =>
            {
                if (int.TryParse(box.Text, out var n))
                    prop.SetValue(plugin, n);
            };
            stack.Children.Add(box);
        }
        else if (prop.PropertyType == typeof(bool))
        {
            var cb = new CheckBox { IsChecked = prop.GetValue(plugin) is true };
            cb.Checked += (_, _) => prop.SetValue(plugin, true);
            cb.Unchecked += (_, _) => prop.SetValue(plugin, false);
            stack.Children.Add(cb);
        }

        return stack;
    }

    private static Control BuildButton(IPlugin plugin, MethodInfo method)
    {
        var attr = method.GetCustomAttribute<PluginButton>();
        var btn = new Avalonia.Controls.Button { Content = attr?.text ?? method.Name };
        btn.Click += (_, _) =>
        {
            var args = method.GetParameters().Length == 1
                ? new object[] { new LinuxOpenBulletApp() }
                : Array.Empty<object>();
            method.Invoke(plugin, args);
        };
        return btn;
    }
}
