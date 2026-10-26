using RuriLib.Interfaces;

namespace OpenBullet.Linux.Plugins;

/// <summary>Minimal <see cref="IApplication"/> for UI plugins that need app context.</summary>
public sealed class LinuxOpenBulletApp : IApplication
{
    public IRunnerManager RunnerManager { get; set; }
    public IProxyManager ProxyManager { get; set; }
    public IProxyChecker ProxyChecker { get; set; }
    public IWordlistManager WordlistManager { get; set; }
    public IConfigManager ConfigManager { get; set; }
    public IHitsDB HitsDB { get; set; }
    public IAlerter Alerter { get; set; }
    public ILogger Logger { get; set; }
    public ISettings Settings { get; set; }
}
