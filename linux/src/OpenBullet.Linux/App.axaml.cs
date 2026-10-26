using Avalonia;
using Avalonia.Markup.Xaml;

namespace OpenBullet.Linux;

public partial class App : Application
{
    public override void Initialize() => AvaloniaXamlLoader.Load(this);
}
