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

### Headless Runner screenshot (CI / docs)

```bash
pip install pillow
export OPENBULLET_SCREENSHOT=1
export OPENBULLET_SCREENSHOT_PATH=/path/to/openbullet-linux-runner.png
bash linux/scripts/capture-runner-screenshot.sh
```

Uses Avalonia `RenderTargetBitmap` (not X11 window grab). Dark Metro UI has ~29 average luminance but &lt;5% near-black pixels when valid.

## Run GUI (`OpenBullet.Linux`)

```bash
dotnet run --project linux/src/OpenBullet.Linux/OpenBullet.Linux.csproj -c Release
```

The shell includes **Runner**, **Configs** (Manager + Stacker), **Camoufox Tools**, and **About**. Runner supports **START / STOP / HARD ABORT**, progress, CPM, and a log pane.

### Plugins

Place plugin DLLs under `Plugins/` next to the app binary (same layout as Windows OpenBullet). Optional dependency folders: `Plugins/<PluginName>/`.

Block plugins are loaded at startup; the Runner checks `RequiredPlugins` before start.

## Browser automation: Camoufox (not Selenium)

On Linux, **browser blocks** (`BROWSERACTION`, `NAVIGATE`, `ELEMENTACTION`, `EXECUTEJS`) use **Camoufox** through **Microsoft Playwright** (`RuriLib.Camoufox`). Upstream Selenium WebDriver is not started for `OpenBrowser` on this port.

`Selenium.WebDriver` NuGet packages remain referenced only for shared types and legacy code paths; **chromedriver / geckodriver are not used** on Linux.

### Install (Dustin / dev machine)

```bash
# Python Camoufox + browser bundle
pip install camoufox
python3 -m camoufox fetch

# Playwright Firefox driver (used to connect to Camoufox WS)
cd linux/src/RuriLib.Camoufox
dotnet build -c Release
pwsh bin/Release/net8.0/playwright.ps1 install firefox
# or: npx playwright install firefox  (if you use Node playwright CLI)
```

### Runtime configuration

| Variable | Purpose |
|----------|---------|
| `CAMOUFOX_WS` or `CAMOUFOX_SERVER_WS` | WebSocket URL of an existing Camoufox server (skip auto-start) |
| (auto) | If unset, the runner tries `python3 -m camoufox server --port <free> --ws-path openbullet` |
| (fallback) | If Camoufox is missing, Playwright launches stock **Firefox** (still headless-friendly, not anti-detect) |

RLSettings / config flags still apply where relevant: **Headless**, **ForceHeadless**, **CustomUserAgent**, **RandomUA**, **proxy** on the browser context.

### Cleanup

Use **Camoufox Tools** in the app (or Runner toolbar): stop owned server, kill Camoufox/python processes, clear Firefox temp profiles.

### MOUSEACTION (known gap)

Upstream `MOUSEACTION` LoliScript uses Selenium `Actions` (synthetic mouse). The Linux port does **not** implement this on Camoufox. **Workaround:** use `ELEMENTACTION` Click / Type / coordinates via Playwright-backed blocks, or rewrite configs to avoid `MOUSEACTION`.

## Layout

| Project | Purpose |
|---------|---------|
| `ObMedia` | `BlockColor` + WPF `System.Windows.Media` shim |
| `PluginFramework` | net8 compile of upstream plugin contracts |
| `RuriLib.Camoufox` | Playwright session + Camoufox launcher |
| `RuriLib` | net8 upstream sources + Linux overrides (`Overrides/`, ImageSharp, Camoufox blocks) |
| `OpenBulletCLI` | net8 CLI |
| `OpenBullet.Linux` | Avalonia 11 UI |

## CI

GitHub Actions workflow `.github/workflows/linux-openbullet.yml` builds the solution and runs the CLI smoke fixture on Ubuntu.
