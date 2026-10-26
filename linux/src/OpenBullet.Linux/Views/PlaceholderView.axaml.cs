using Avalonia.Controls;

namespace OpenBullet.Linux.Views;

public partial class PlaceholderView : UserControl
{
    public PlaceholderView(string title)
    {
        InitializeComponent();
        TitleText.Text = title;
    }
}
