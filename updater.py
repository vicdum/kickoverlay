"""Surum kontrolu ve otomatik guncelleme.

GitHub Releases'teki en son surumu APP_VERSION ile karsilastirir, uygun
paketi (tek dosya .exe ya da portable .zip) indirir ve calisan .exe'yi
kilitlemeden degistirmek icin ayri bir .bat betigi baslatir:

1. Bu surec kapanana kadar bekler (PID kontrolu).
2. Yeni dosyayi eskisinin uzerine kopyalar (.exe) ya da klasoru
   robocopy ile ustune yazar (onedir/.zip).
3. Uygulamayi yeniden baslatir, kendi gecici dosyalarini siler.

Gelistirme ortaminda (frozen olmayan, "python main.py") self-update
yapilamaz - sadece Releases sayfasi acilir.
"""

import os
import subprocess
import sys
import tempfile
import zipfile

import requests
from PyQt6.QtCore import QThread, pyqtSignal

from config import APP_VERSION
from logger import get_logger

log = get_logger("updater")

GITHUB_REPO = "vicdum/kickoverlay"
RELEASES_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RELEASES_PAGE_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"

API_HEADERS = {
    "User-Agent": "KickChatOverlay-Updater",
    "Accept": "application/vnd.github+json",
}

UPDATE_BAT_TEMPLATE = """@echo off
setlocal
set PID={pid}
:waitloop
tasklist /FI "PID eq %PID%" | find "%PID%" >nul
if not errorlevel 1 (
  timeout /t 1 /nobreak >nul
  goto waitloop
)
{action}
start "" "{target_exe}"
rmdir /S /Q "{work_dir}" >nul 2>&1
(goto) 2>nul & del "%~f0"
"""


def parse_version(text: str) -> tuple:
    text = (text or "").strip().lstrip("vV")
    parts = []
    for piece in text.split("."):
        digits = ""
        for ch in piece:
            if ch.isdigit():
                digits += ch
            else:
                break
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


def is_newer(remote_version: str, local_version: str) -> bool:
    r = parse_version(remote_version)
    l = parse_version(local_version)
    length = max(len(r), len(l))
    r = r + (0,) * (length - len(r))
    l = l + (0,) * (length - len(l))
    return r > l


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def is_onedir() -> bool:
    """Onedir derlemesi exe'nin yanindaki '_internal' klasorunden anlasilir."""
    if not is_frozen():
        return False
    return os.path.isdir(os.path.join(os.path.dirname(sys.executable), "_internal"))


def _pick_asset(assets: list):
    """(dosya_adi, indirme_url) dondurur; onedir icin .zip, onefile icin .exe tercih edilir."""
    zip_asset = None
    exe_asset = None
    for asset in assets:
        name = asset.get("name") or ""
        url = asset.get("browser_download_url")
        if not url:
            continue
        lname = name.lower()
        if lname.endswith(".zip") and zip_asset is None:
            zip_asset = (name, url)
        elif lname.endswith(".exe") and "portable" not in lname and exe_asset is None:
            exe_asset = (name, url)
    return (zip_asset or exe_asset) if is_onedir() else (exe_asset or zip_asset)


def check_for_update() -> dict:
    """Yeni surum varsa bilgi sozlugu, yoksa None dondurur. Hata firlatabilir."""
    resp = requests.get(RELEASES_API_URL, headers=API_HEADERS, timeout=(5, 10))
    resp.raise_for_status()
    release = resp.json()

    remote_version = (release.get("tag_name") or "").lstrip("vV")
    if not remote_version or not is_newer(remote_version, APP_VERSION):
        return None

    asset = _pick_asset(release.get("assets") or [])
    if asset is None:
        raise RuntimeError("Yeni surum bulundu ama indirilecek dosya (release asset) yok.")
    asset_name, asset_url = asset

    return {
        "version": remote_version,
        "url": release.get("html_url") or RELEASES_PAGE_URL,
        "notes": release.get("body") or "",
        "asset_name": asset_name,
        "asset_url": asset_url,
    }


def download_asset(asset_url: str, asset_name: str, progress_cb=None) -> str:
    """Asset'i gecici bir klasore indirir, tam dosya yolunu dondurur."""
    work_dir = tempfile.mkdtemp(prefix="KickOverlayUpdate_")
    dest_path = os.path.join(work_dir, asset_name)

    with requests.get(asset_url, stream=True, timeout=(5, 30)) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("Content-Length") or 0)
        written = 0
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=262144):
                if not chunk:
                    continue
                f.write(chunk)
                written += len(chunk)
                if progress_cb and total:
                    try:
                        progress_cb(int(written * 100 / total))
                    except Exception:
                        pass
    return dest_path


def _resolve_zip_root(extract_dir: str) -> str:
    """Zip tek bir kok klasor iceriyorsa (KickChatOverlay-portable.zip gibi)
    kopyalama kaynagi o klasor olmali, yoksa extract_dir'in kendisi."""
    entries = [e for e in os.listdir(extract_dir) if e != "__MACOSX"]
    if len(entries) == 1 and os.path.isdir(os.path.join(extract_dir, entries[0])):
        return os.path.join(extract_dir, entries[0])
    return extract_dir


def launch_updater_and_exit(downloaded_path: str, asset_name: str) -> bool:
    """Suresi ayrilmis bir .bat baslatir: bu surec kapanmayi bekler, dosyalari
    degistirir, uygulamayi yeniden baslatir. Basariyla baslatildiysa True
    doner - caginin ardindan uygulama kapatilmali (worker/overlay temiz
    kapatma dahil, os._exit degil normal quit())."""
    try:
        target_exe = os.path.abspath(sys.executable)
        target_dir = os.path.dirname(target_exe)
        work_dir = os.path.dirname(downloaded_path)

        if asset_name.lower().endswith(".zip"):
            extract_dir = os.path.join(work_dir, "extracted")
            with zipfile.ZipFile(downloaded_path, "r") as zf:
                zf.extractall(extract_dir)
            source_dir = _resolve_zip_root(extract_dir)
            action = f'robocopy "{source_dir}" "{target_dir}" /E /R:5 /W:2 >nul'
        else:
            action = f'copy /Y "{downloaded_path}" "{target_exe}" >nul'

        bat_path = os.path.join(tempfile.gettempdir(), f"kickoverlay_update_{os.getpid()}.bat")
        script = UPDATE_BAT_TEMPLATE.format(
            pid=os.getpid(), action=action, target_exe=target_exe, work_dir=work_dir,
        )
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(script)

        subprocess.Popen(
            ["cmd.exe", "/c", bat_path],
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
            close_fds=True,
        )
        log.info("guncelleyici baslatildi (bat=%s hedef=%s)", bat_path, target_exe)
        return True
    except Exception as exc:
        log.error("guncelleyici baslatilamadi: %s", exc, exc_info=True)
        return False


class UpdateCheckThread(QThread):
    """GitHub'daki en son surumu sorgular, GUI'yi bloklamaz."""

    result = pyqtSignal(object)   # dict ya da None
    failed = pyqtSignal(str)

    def run(self):
        try:
            info = check_for_update()
        except Exception as exc:
            log.warning("guncelleme kontrolu basarisiz: %s", exc)
            self.failed.emit(str(exc))
            return
        self.result.emit(info)


class UpdateDownloadThread(QThread):
    """Secilen release asset'ini arka planda indirir."""

    progress = pyqtSignal(int)
    succeeded = pyqtSignal(str)   # indirilen dosyanin tam yolu
    failed = pyqtSignal(str)

    def __init__(self, asset_url: str, asset_name: str, parent=None):
        super().__init__(parent)
        self.asset_url = asset_url
        self.asset_name = asset_name

    def run(self):
        try:
            path = download_asset(self.asset_url, self.asset_name, progress_cb=self.progress.emit)
        except Exception as exc:
            log.error("guncelleme indirilemedi: %s", exc, exc_info=True)
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(path)
