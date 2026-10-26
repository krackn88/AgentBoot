# OpenBullet 1.2.2 — Linux port (.NET 8)

SDK-style projects compile upstream **RuriLib** and **OpenBulletCLI** sources from the git submodule at `../upstream/openbullet` (tag `1.2.2#707`) without modifying the submodule.

## Build

```bash
dotnet build linux/OpenBullet.Linux.sln -c Release
```

## Run CLI

```bash
cd linux/src/OpenBulletCLI
dotnet run -c Release -- \
  -c ../../fixtures/smoke.loli \
  -w ../../fixtures/smoke-wordlist.txt \
  --wltype Default \
  -b 1 -v
```

## Run GUI shell

```bash
dotnet run --project linux/src/OpenBullet.Linux/OpenBullet.Linux.csproj
```

## Layout

| Project | Purpose |
|---------|---------|
| `ObMedia` | `BlockColor` + WPF `System.Windows.Media` shim for upstream RuriLib |
| `RuriLib` | net8 compile of upstream `RuriLib/**/*.cs` |
| `OpenBulletCLI` | net8 compile of upstream CLI entrypoint |
| `OpenBullet.Linux` | Avalonia 11 UI (About screen ported) |
