# PyInstaller spec for customer edition (obfuscated sources in build/obf-customer).
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

block_cipher = None
root = Path(os.environ.get("TROPIC_BUILD_ROOT", Path(SPECPATH).resolve().parent))
obf = Path(os.environ.get("TROPIC_OBF_DIR", root / "build" / "obf-customer"))

ctk_datas, ctk_binaries, ctk_hidden = collect_all("customtkinter")

a = Analysis(
    [str(obf / "run_customer.py")],
    pathex=[str(obf)],
    binaries=ctk_binaries,
    datas=ctk_datas,
    hiddenimports=[
        *ctk_hidden,
        "tkinter",
        "tkinter.filedialog",
        "tkinter.messagebox",
        "Crypto.Cipher.AES",
        "Crypto.Util.Padding",
        "Crypto.PublicKey.ECC",
        "Crypto.Signature.eddsa",
        "Crypto.Hash.SHA512",
        "requests",
        "urllib3",
        "certifi",
        "charset_normalizer",
        "idna",
        "tropic_checker",
        "tropic_checker.gui",
        "tropic_checker.api",
        "tropic_checker.engine",
        "tropic_checker.storage",
        "tropic_checker.crypto",
        "tropic_checker.theme",
        "tropic_checker.telegram_notify",
        "tropic_checker.licensing",
        "tropic_checker.licensing.hwid",
        "tropic_checker.licensing.license_core",
        "tropic_checker.licensing.activation",
        "tropic_checker.licensing.store",
        "tropic_checker.licensing._secret",
        "tropic_checker.licensing.online",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["flask", "gunicorn", "pytest", "tropic_checker.web_app", "tropic_checker.smoke"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="TropicChecker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
