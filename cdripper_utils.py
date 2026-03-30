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

def search_youtube(query: str, max_results: int = 5, expected_duration_secs: float = None) -> list[dict]:
    """Retorna lista de vídeos encontrados, ordenados por proximidade de duração se fornecida."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
    }
    url = f"ytsearch{max_results}:{query}"
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        entries = info.get("entries", [])

    # Se duração esperada foi fornecida, ordenar por proximidade
    if expected_duration_secs and entries:
        def duration_score(entry):
            d = entry.get("duration") or 0
            return abs(d - expected_duration_secs)
        entries = sorted(entries, key=duration_score)

    return entries


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


def get_mp3_metadata(mp3_path: str) -> dict:
    """Extrai metadados (imagem, duração) de um MP3. Retorna dict com os dados encontrados."""
    try:
        from mutagen.mp3 import MP3
        from mutagen.id3 import ID3

        audio = MP3(mp3_path)
        metadata = {"duration_secs": audio.info.length}

        # Tentar extrair tags ID3
        try:
            tags = ID3(mp3_path)
            # Procurar por imagem/capa (APIC = Attached Picture)
            for key in tags.keys():
                if key.startswith("APIC"):
                    apic = tags[key]
                    metadata["artwork_bytes"] = apic.data
                    metadata["artwork_mime"] = apic.mime
                    metadata["artwork_desc"] = apic.desc
                    metadata["artwork_type"] = apic.type
                    break
        except Exception:
            pass  # Arquivo sem tags ID3 é ok

        return metadata
    except Exception:
        return {}


def apply_artwork_to_mp3(mp3_path: str, metadata: dict) -> None:
    """Aplica imagem/capa de um metadata dict a um arquivo MP3."""
    if not metadata.get("artwork_bytes"):
        return

    try:
        from mutagen.id3 import ID3, APIC, error as ID3Error

        # Tentar ler tags existentes, ou criar novas
        try:
            tags = ID3(mp3_path)
        except ID3Error:
            tags = ID3()

        # Remover artwork existente e adicionar a nova
        tags.delall("APIC")
        tags.add(APIC(
            encoding=3,  # UTF-8
            mime=metadata.get("artwork_mime", "image/jpeg"),
            type=metadata.get("artwork_type", 3),  # 3 = cover front
            desc=metadata.get("artwork_desc", "Cover"),
            data=metadata["artwork_bytes"],
        ))
        tags.save(mp3_path)
    except Exception:
        pass  # Falha silenciosa para não alarmar usuários


def validate_mp3_duration(mp3_path: str, expected_duration_secs: float, tolerance_percent: float = 30, strict: bool = True) -> bool:
    """
    Valida se a duração do arquivo MP3 está dentro de tolerância.

    Args:
        mp3_path: caminho do arquivo MP3
        expected_duration_secs: duração esperada em segundos (do CD)
        tolerance_percent: tolerância em % (padrão 30%)
        strict: se True, valida rigorosamente; se False, aceita qualquer duração > 30s

    Returns:
        True se duração está OK, False se está muito diferente

    Exemplos (strict=True):
        CD: 1:30m (90s) → aceita 63s a 117s
        6s → REJEITA (muito curto)
        1:28m (88s) → ACEITA (dentro de ±30%)
        3:00m (180s) → REJEITA (muito longo)

    Exemplos (strict=False, fallback mode):
        Qualquer duração > 30s é aceita
        Evita clipes muito curtos (6s)
    """
    try:
        from mutagen.mp3 import MP3

        audio = MP3(mp3_path)
        actual_duration = audio.info.length

        if strict:
            # Validação rigorosa: ±X% da duração esperada
            min_acceptable = expected_duration_secs * (1 - tolerance_percent / 100)
            max_acceptable = expected_duration_secs * (1 + tolerance_percent / 100)
            return min_acceptable <= actual_duration <= max_acceptable
        else:
            # Fallback mode: aceita qualquer coisa > 30s (evita clipes muito curtos)
            return actual_duration > 30
    except Exception:
        # Se não conseguir ler metadados, rejeitar por segurança
        return False


def sanitize_filename(name: str) -> str:
    """Remove caracteres inválidos para nomes de arquivo e espaços extras."""
    # Remove caracteres inválidos
    cleaned = re.sub(r'[\\/*?:"<>|]', "", name)
    # Remove espaços múltiplos e espaços nas pontas
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


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

        # Adicionar pasta iCloud do usuário
        home_dir = os.path.expanduser("~")
        icloud_path = os.path.join(home_dir, "Library/Mobile Documents")
        if os.path.exists(icloud_path):
            drives.append(icloud_path)
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