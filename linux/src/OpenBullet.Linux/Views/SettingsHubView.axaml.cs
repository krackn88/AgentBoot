using Avalonia.Controls;
using OpenBullet.Linux.Services;

namespace OpenBullet.Linux.Views;

public partial class SettingsHubView : UserControl
{
    public SettingsHubView()
    {
        InitializeComponent();
    }

    public void Attach(RuriLibSettingsHost ruri, ObSettingsHost ob)
    {
        RuriTab.Attach(ruri);
        ObTab.Attach(ob);
    }
}
