# OpenBullet 1.2.2 — Linux port (.NET 8)

SDK-style projects compile upstream **RuriLib**, **PluginFramework**, and **OpenBulletCLI** from the git submodule at `upstream/openbullet` (tag `1.2.2#707`) without modifying the submodule.

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

## Run GUI (`OpenBullet.Linux`)

```bash
dotnet run --project linux/src/OpenBullet.Linux/OpenBullet.Linux.csproj -c Release
```

The **Runner** tab loads smoke fixtures when present, supports **START / STOP / HARD ABORT**, and shows progress, CPM, and a log pane. The **About** tab matches upstream copy.

### Plugins

Place plugin DLLs under `Plugins/` next to the app binary (same layout as Windows OpenBullet). Optional dependency folders: `Plugins/<PluginName>/`.

Block plugins are loaded at startup; the Runner checks `RequiredPlugins` before start.

## Selenium on Linux

Upstream WPF **Selenium Tools** used `cmd.exe` / `taskkill`. On Linux use the Runner toolbar buttons (**Kill chromedriver** / **Kill geckodriver**) or:

```bash
pkill -f chromedriver
pkill -f geckodriver
```

### Driver setup

1. Install a browser (Chromium or Firefox).
2. Install a matching driver and ensure it is on `PATH`:
   - **Chrome/Chromium:** [Chrome for Testing](https://googlechromelabs.github.io/chrome-for-testing/) or distro `chromium-chromedriver`
   - **Firefox:** `geckodriver` from [Mozilla releases](https://github.com/mozilla/geckodriver/releases)
3. In `Settings/RLSettings.json` (auto-created beside the app), set Selenium paths if needed — same keys as upstream RuriLib settings.

Configs that spawn Selenium still require a working driver + browser on the host. OB 1.2.2 does not bundle Linux drivers in NuGet (Win64 packages are Windows-only).

## Layout

| Project | Purpose |
|---------|---------|
| `ObMedia` | `BlockColor` + WPF `System.Windows.Media` shim |
| `PluginFramework` | net8 compile of upstream plugin contracts |
| `RuriLib` | net8 upstream sources + Linux overrides (`Overrides/`, ImageSharp) |
| `OpenBulletCLI` | net8 CLI |
| `OpenBullet.Linux` | Avalonia 11 UI (Runner + About) |

## CI

GitHub Actions workflow `.github/workflows/linux-openbullet.yml` builds the solution and runs the CLI smoke fixture on Ubuntu.
