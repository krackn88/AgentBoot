DTV Checker - Standalone GUI
============================

Windows:
  Double-click start.bat
  (First run installs Python deps automatically)

Linux:
  chmod +x start.sh
  ./start.sh

Requirements:
  - Python 3.10+ installed
  - Internet connection (first run downloads PyQt6 + httpx)

Features:
  - Combo paste or load large .txt files
  - Proxy support (host:port:user:pass)
  - Configurable threads + CPM
  - Smoke test combo box
  - Active hits only (inactive = fail)
  - Copy / delete / export hits
  - Live log

Notes:
  - US residential proxies recommended if your IP is geo-blocked by DIRECTV
  - Only accounts with Active: Yes appear in the Hits list
