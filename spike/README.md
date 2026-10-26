# OpenBullet Linux port spikes

Proof-of-concept UI shell for the OpenBullet 1.2.2 Linux port assessment.

## OpenBulletLinuxShell

Avalonia 11 + .NET 8 app that mimics the dark palette and custom title bar layout from upstream `OpenBullet/App.xaml` and `MainWindow.xaml`.

```bash
export PATH="$HOME/.dotnet:$PATH"   # if SDK not on PATH
cd OpenBulletLinuxShell
dotnet run
```

Full port plan: Project store `internal/openbullet-assessment.md`.
