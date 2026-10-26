using System.Diagnostics;
using Avalonia.Controls;
using Avalonia.Interactivity;

namespace OpenBullet.Linux.Views;

public partial class AboutView : UserControl
{
    public AboutView()
    {
        InitializeComponent();
    }

    private void OnRepositoryClick(object sender, RoutedEventArgs e) =>
        Process.Start(new ProcessStartInfo("https://github.com/openbullet/openbullet") { UseShellExecute = true });

    private void OnUsageGuideClick(object sender, RoutedEventArgs e) =>
        Process.Start(new ProcessStartInfo("https://openbullet.github.io/") { UseShellExecute = true });
}
