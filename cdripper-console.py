#!/usr/bin/env python3
"""
YouTube Music Downloader
Busca músicas no YouTube e baixa como MP3.

Dependências:
    pip install yt-dlp
    pip install colorama

Opcional (para melhor qualidade de conversão):
    Instale o ffmpeg: https://ffmpeg.org/download.html
"""

import os
import sys
import re
import shutil
import platform
from pathlib import Path

try:
    import yt_dlp
except ImportError:
    print("Instalando yt-dlp...")
    os.system(f"{sys.executable} -m pip install yt-dlp -q")
    import yt_dlp

try:
    from colorama import Fore, Style, init
    init(autoreset=True)
    COLOR = True
except ImportError:
    os.system(f"{sys.executable} -m pip install colorama -q")
    try:
        from colorama import Fore, Style, init
        init(autoreset=True)
        COLOR = True
    except ImportError:
        COLOR = False


# ── helpers de cor ──────────────────────────────────────────────────────────

def c(text, color):
    if not COLOR:
        return text
    colors = {
        "green":  Fore.GREEN,
        "red":    Fore.RED,
        "yellow": Fore.YELLOW,
        "cyan":   Fore.CYAN,
        "blue":   Fore.BLUE,
        "white":  Fore.WHITE,
        "bold":   Style.BRIGHT,
    }
    return f"{colors.get(color, '')}{text}{Style.RESET_ALL}"


def banner():
    print(c("""
╔══════════════════════════════════════════╗
║      🎵  YouTube → MP3 Downloader  🎵    ║
╚══════════════════════════════════════════╝
""", "cyan"))


def sanitize_filename(name: str) -> str:
    """Remove caracteres inválidos para nomes de arquivo."""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()


def get_choice(prompt: str, min_val: int, max_val: int) -> int | None:
    """Obtém entrada do usuário com validação."""
    raw = input(prompt).strip()
    if raw.lower() in ("s", "sair", "q", "quit", "exit"):
        return None
    try:
        val = int(raw)
        if min_val <= val <= max_val:
            return val
    except ValueError:
        pass
    print(c(f"  ⚠ Digite um número entre {min_val} e {max_val}.", "red"))
    return -1   # sinal de entrada inválida


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


def display_results(results: list[dict]) -> None:
    """Exibe os resultados da busca."""
    print(c(f"\n{'─'*50}", "blue"))
    print(c(f"  {'#':<4} {'Título':<45} {'Duração':>8}", "bold"))
    print(c(f"{'─'*50}", "blue"))
    for i, entry in enumerate(results, 1):
        title = (entry.get("title") or "Sem título")[:44]
        duration = entry.get("duration") or 0
        mins, secs = divmod(int(duration), 60)
        dur_str = f"{mins}:{secs:02d}"
        print(f"  {c(str(i), 'yellow'):<4} {title:<45} {c(dur_str, 'cyan'):>8}")
    print(c(f"{'─'*50}\n", "blue"))


# ── download ─────────────────────────────────────────────────────────────────

class ProgressHook:
    def __call__(self, d):
        status = d.get("status")
        if status == "downloading":
            total   = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            if total:
                pct = downloaded / total * 100
                bar_len = 30
                filled  = int(bar_len * pct / 100)
                bar     = "█" * filled + "░" * (bar_len - filled)
                speed   = d.get("speed") or 0
                speed_k = speed / 1024
                print(
                    f"\r  {c(bar, 'green')} {c(f'{pct:5.1f}%', 'yellow')} "
                    f"  {c(f'{speed_k:.0f} KB/s', 'cyan')}",
                    end="", flush=True
                )
        elif status == "finished":
            print(f"\n  {c('✔ Download concluído! Convertendo…', 'green')}")


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


def display_cd_contents(cd_path: str) -> dict:
    """Exibe conteúdo do CD organizado por pasta."""
    mp3_dict = find_mp3_files(cd_path)
    
    if not mp3_dict:
        print(c("  ✖ Nenhum arquivo MP3 encontrado neste CD.", "red"))
        return {}
    
    print(c(f"\n{'─'*70}", "blue"))
    print(c(f"  Conteúdo do CD: {os.path.basename(cd_path)}", "cyan"))
    print(c(f"{'─'*70}", "blue"))
    
    total_files = 0
    for folder, files in sorted(mp3_dict.items()):
        folder_display = folder if folder != "." else "[Raiz]"
        print(c(f"\n  📁 {folder_display}", "yellow"))
        for i, file in enumerate(sorted(files), 1):
            print(f"     {i:2d}. {file}")
        total_files += len(files)
    
    print(c(f"\n{'─'*70}", "blue"))
    print(c(f"  Total: {total_files} arquivo(s) MP3", "green"))
    print(c(f"{'─'*70}\n", "blue"))
    
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


def copy_cd_with_fallback(cd_path: str, output_base: str = "downloads") -> None:
    """Copia arquivos do CD para ./downloads/cdX, com fallback para YouTube."""
    mp3_dict = find_mp3_files(cd_path)
    
    if not mp3_dict:
        print(c("  ✖ Nenhum arquivo MP3 encontrado.", "red"))
        return
    
    cd_num = get_next_cd_number(output_base)
    cd_output = os.path.join(output_base, f"cd{cd_num}")
    
    print(c(f"\n  Copiando para: {cd_output}", "cyan"))
    print(c(f"  {'─'*60}", "blue"))
    
    total = sum(len(files) for files in mp3_dict.values())
    copied = 0
    failed = []
    
    for folderRelPath, files in sorted(mp3_dict.items()):
        # Criar pasta de destino
        if folderRelPath == ".":
            dest_folder = cd_output
        else:
            dest_folder = os.path.join(cd_output, folderRelPath)
        
        os.makedirs(dest_folder, exist_ok=True)
        
        for file in sorted(files):
            copied += 1
            src_file = os.path.join(cd_path, folderRelPath, file) if folderRelPath != "." else os.path.join(cd_path, file)
            dst_file = os.path.join(dest_folder, file)
            
            print(f"  [{copied:3d}/{total:3d}] {file}… ", end="", flush=True)
            
            try:
                shutil.copy2(src_file, dst_file)
                file_size = os.path.getsize(dst_file) / (1024 * 1024)
                print(c(f"✔ ({file_size:.1f} MB)", "green"))
            except Exception as e:
                print(c(f"✖ Erro: {str(e)[:40]}", "red"))
                failed.append((file, folderRelPath))
    
    print(c(f"\n  {'─'*60}", "blue"))
    print(c(f"  ✔ Cópia concluída: {copied - len(failed)}/{total} arquivos", "green"))
    
    # Fallback para YouTube
    if failed:
        print(c(f"\n  ⚠ {len(failed)} arquivo(s) falharam. Tentando YouTube…", "yellow"))
        print(c(f"  {'─'*60}", "blue"))
        
        for file, folder in failed:
            title = os.path.splitext(file)[0]
            
            if folder == ".":
                dest_folder = cd_output
            else:
                dest_folder = os.path.join(cd_output, folder)
            
            os.makedirs(dest_folder, exist_ok=True)
            dst_file = os.path.join(dest_folder, file)
            
            print(f"\n  🎵 Procurando no YouTube: {title}")
            try:
                results = search_youtube(title, max_results=1)
                if results:
                    url = results[0].get("url") or results[0].get("webpage_url") or \
                          f"https://www.youtube.com/watch?v={results[0]['id']}"
                    
                    print(c(f"     Baixando: {results[0].get('title', title)}", "cyan"))
                    mp3_path = download_mp3(url, file, dest_folder)
                    
                    if os.path.exists(mp3_path):
                        file_size = os.path.getsize(mp3_path) / (1024 * 1024)
                        print(c(f"     ✔ Salvo com sucesso ({file_size:.1f} MB)", "green"))
                    else:
                        print(c(f"     ⚠ Arquivo não encontrado após download", "yellow"))
                else:
                    print(c(f"     ✖ Nenhum resultado no YouTube", "red"))
            except Exception as e:
                print(c(f"     ✖ Erro: {str(e)}", "red"))
        
        print(c(f"\n  {'─'*60}", "blue"))




def main_menu():
    """Menu principal com opções."""
    print()
    print(c("  ╔════════════════════════════════════════╗", "blue"))
    print(c("  ║         Escolha uma opção:            ║", "blue"))
    print(c("  ╠════════════════════════════════════════╣", "blue"))
    print(c("  ║  1  🎵 Buscar música no YouTube       ║", "blue"))
    print(c("  ║  2  💿 Copiar de um CD                ║", "blue"))
    print(c("  ║  0  🚪 Sair                           ║", "blue"))
    print(c("  ╚════════════════════════════════════════╝", "blue"))
    print()
    choice = input(c("  Escolha uma opção [0-2]: ", "yellow")).strip()
    return choice


def main_youtube():
    """Fluxo de busca no YouTube."""
    output_dir = input(
        f"  Pasta de destino {c('[downloads]', 'cyan')}: "
    ).strip() or "downloads"

    while True:
        print()
        query = input(c("  🔍 Buscar música (ou 'sair' para voltar): ", "bold")).strip()
        if not query or query.lower() in ("sair", "q", "quit", "exit"):
            break

        print(c(f'\n  Buscando: "{query}"…', "cyan"))
        try:
            results = search_youtube(query)
        except Exception as e:
            print(c(f"\n  ✖ Erro na busca: {e}", "red"))
            continue

        if not results:
            print(c("  ✖ Nenhum resultado encontrado.", "red"))
            continue

        display_results(results)

        # escolha do usuário
        while True:
            choice = get_choice(
                c(f"  Escolha [1–{len(results)}] ou 0 para nova busca: ", "yellow"),
                0, len(results)
            )
            if choice is None:       # sair
                print(c("\n  👋 Até mais!\n", "yellow"))
                return
            if choice == -1:         # entrada inválida
                continue
            break

        if choice == 0:
            continue

        selected = results[choice - 1]
        title    = selected.get("title", f"musica_{choice}")
        url      = selected.get("url") or selected.get("webpage_url") or \
                   f"https://www.youtube.com/watch?v={selected['id']}"

        print(c(f"\n  ⬇  Baixando: {title}", "green"))
        try:
            mp3_path = download_mp3(url, title, output_dir)
            if os.path.exists(mp3_path):
                size_mb = os.path.getsize(mp3_path) / (1024 * 1024)
                print(c(f"  🎵 Salvo em: {mp3_path}  ({size_mb:.1f} MB)", "green"))
            else:
                print(c(
                    f"  ⚠  Arquivo MP3 não encontrado — verifique se o ffmpeg está instalado.\n"
                    f"     O áudio pode ter sido salvo em outro formato em '{output_dir}'.",
                    "yellow"
                ))
        except Exception as e:
            print(c(f"\n  ✖ Erro no download: {e}", "red"))

        # baixar mais?
        again = input(c("\n  Baixar outra música? [S/n]: ", "cyan")).strip().lower()
        if again in ("n", "não", "nao", "no"):
            break


def main_cd():
    """Fluxo de cópia de CD."""
    print(c("\n  Procurando unidades de CD…", "cyan"))
    drives = find_cd_drives()
    
    if not drives:
        print(c("  ✖ Nenhuma unidade de CD encontrada.", "red"))
        return
    
    print(c(f"\n  {'─'*50}", "blue"))
    print(c("  Unidades disponíveis:", "yellow"))
    print(c(f"  {'─'*50}", "blue"))
    for i, drive in enumerate(drives, 1):
        print(f"  {i}. {drive}")
    print(c(f"  {'─'*50}\n", "blue"))
    
    while True:
        choice = get_choice(
            c(f"  Escolha uma unidade [1–{len(drives)}] ou 0 para voltar: ", "yellow"),
            0, len(drives)
        )
        if choice is None:
            return
        if choice == -1:
            continue
        if choice == 0:
            return
        break
    
    selected_drive = drives[choice - 1]
    
    # Exibir conteúdo
    mp3_dict = display_cd_contents(selected_drive)
    if not mp3_dict:
        return
    
    # Confirmar cópia
    confirm = input(c("  Deseja copiar estes arquivos? [S/n]: ", "cyan")).strip().lower()
    if confirm in ("n", "não", "nao", "no"):
        return
    
    copy_cd_with_fallback(selected_drive)
    print(c("\n  ✔ Processo concluído!", "green"))


def main():
    banner()
    
    while True:
        choice = main_menu()
        
        if choice == "1":
            main_youtube()
        elif choice == "2":
            main_cd()
        elif choice == "0":
            print(c("\n  👋 Até mais!\n", "yellow"))
            break
        else:
            print(c("  ⚠ Opção inválida. Tente novamente.", "red"))


# ── fluxo principal ───────────────────────────────────────────────────────────


if __name__ == "__main__":
    main()
