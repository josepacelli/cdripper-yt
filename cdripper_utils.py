#!/usr/bin/env python3
"""
Módulo compartilhado para cdripper-console.py e cdripper-gui.py
Contém funções para busca/download de YouTube e manipulação de CDs.
"""

import os
import re
import sys
import shutil
import platform
from pathlib import Path

try:
    import yt_dlp
except ImportError:
    print("Instalando yt-dlp...")
    os.system(f"{sys.executable} -m pip install yt-dlp -q")
    import yt_dlp


# ── busca ────────────────────────────────────────────────────────────────────

def search_youtube(query: str, max_results: int = 5) -> list[dict]:
    """Retorna lista de vídeos encontrados."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
    }
    url = f"ytsearch{max_results}:{query}"
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info.get("entries", [])


# ── download ─────────────────────────────────────────────────────────────────

class AnimatedSpinner:
    """Spinner animado para mostrar progresso durante operações."""
    def __init__(self):
        self.frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.current = 0

    def next(self):
        frame = self.frames[self.current]
        self.current = (self.current + 1) % len(self.frames)
        return frame


class ProgressHook:
    def __init__(self):
        self.spinner = AnimatedSpinner()

    def __call__(self, d):
        status = d.get("status")
        if status == "downloading":
            total   = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            if total:
                pct = downloaded / total * 100
                bar_len = 25
                filled  = int(bar_len * pct / 100)
                bar     = "█" * filled + "░" * (bar_len - filled)
                speed   = d.get("speed") or 0
                speed_k = speed / 1024
                spinner_frame = self.spinner.next()
                print(
                    f"\r  {spinner_frame} {bar} {pct:5.1f}%   {speed_k:.0f} KB/s",
                    end="", flush=True
                )
        elif status == "finished":
            print(f"\n  ✔ Convertendo…")


def sanitize_filename(name: str) -> str:
    """Remove caracteres inválidos para nomes de arquivo."""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()


def download_mp3(video_url: str, title: str, output_dir: str = "downloads") -> str:
    """Baixa o vídeo e converte para MP3."""
    os.makedirs(output_dir, exist_ok=True)
    safe_title = sanitize_filename(title)
    output_path = os.path.join(output_dir, f"{safe_title}.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_path,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [ProgressHook()],
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])

    mp3_file = os.path.join(output_dir, f"{safe_title}.mp3")
    return mp3_file


# ── cópia de CDs ─────────────────────────────────────────────────────────────

def find_cd_drives() -> list[str]:
    """Encontra unidades de CD/DVD disponíveis."""
    drives = []
    if platform.system() == "Darwin":  # macOS
        volumes_path = "/Volumes"
        if os.path.exists(volumes_path):
            for item in os.listdir(volumes_path):
                full_path = os.path.join(volumes_path, item)
                if os.path.isdir(full_path) and item not in ("Macintosh HD", "Data"):
                    drives.append(full_path)
    elif platform.system() == "Windows":
        import string
        for drive in string.ascii_uppercase:
            if os.path.exists(f"{drive}:"):
                drives.append(f"{drive}:")
    elif platform.system() == "Linux":
        common_paths = ["/mnt/cdrom", "/media"]
        for path in common_paths:
            if os.path.exists(path):
                for item in os.listdir(path):
                    full_path = os.path.join(path, item)
                    if os.path.isdir(full_path):
                        drives.append(full_path)
    return drives


def find_mp3_files(directory: str) -> dict:
    """Encontra todos os arquivos MP3 no diretório, agrupados por pasta."""
    mp3_dict = {}
    for root, dirs, files in os.walk(directory):
        mp3_files = [f for f in files if f.lower().endswith(".mp3")]
        if mp3_files:
            rel_path = os.path.relpath(root, directory)
            mp3_dict[rel_path] = mp3_files
    return mp3_dict


def get_next_cd_number(base_dir: str = "downloads") -> int:
    """Retorna o próximo número de CD disponível."""
    max_num = 0
    if os.path.exists(base_dir):
        for item in os.listdir(base_dir):
            if item.startswith("cd") and item.lstrip("cd").isdigit():
                num = int(item.lstrip("cd"))
                max_num = max(max_num, num)
    return max_num + 1


def get_name_variations(title: str) -> list[str]:
    """Gera variações do nome para tentar buscar no YouTube."""
    variations = [title]

    # Remove números no final (ex: "musica 1" -> "musica")
    without_numbers = re.sub(r'\s*\d+\s*$', '', title).strip()
    if without_numbers and without_numbers != title:
        variations.append(without_numbers)

    # Remove parênteses e conteúdo (ex: "musica (remix)" -> "musica")
    without_parens = re.sub(r'\s*\([^)]*\)\s*', ' ', title).strip()
    if without_parens and without_parens != title:
        variations.append(without_parens)

    # Remove colchetes e conteúdo (ex: "musica [remix]" -> "musica")
    without_brackets = re.sub(r'\s*\[[^\]]*\]\s*', ' ', title).strip()
    if without_brackets and without_brackets != title:
        variations.append(without_brackets)

    # Apenas as primeiras 2-3 palavras (ex: "musica artista remix" -> "musica artista")
    words = title.split()
    if len(words) > 2:
        variations.append(" ".join(words[:2]))
        variations.append(" ".join(words[:3]))

    # Remove duplicatas mantendo ordem
    seen = set()
    unique_variations = []
    for v in variations:
        if v and v not in seen:
            seen.add(v)
            unique_variations.append(v)

    return unique_variations