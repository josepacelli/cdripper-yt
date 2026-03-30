#!/usr/bin/env python3
"""
cdripper-web.py — Interface web para copiar músicas de CDs e YouTube

Usa PyWebView para criar uma aplicação desktop com HTML/CSS/JavaScript moderno.
Mantém a mesma lógica de cdripper_utils.py mas com interface web amigável.
"""

import os
import sys
import threading
import base64
import time as time_module
from pathlib import Path

import webview

# Importar funções compartilhadas
from cdripper_utils import (
    search_youtube,
    download_mp3,
    find_cd_drives,
    find_mp3_files,
    get_mp3_metadata,
    apply_artwork_to_mp3,
    validate_mp3_duration,
    get_name_variations,
    sanitize_filename,
    get_next_cd_number,
)


class API:
    """API que expõe funções Python para o frontend JavaScript."""

    def __init__(self, window):
        self.window = window
        self.copying = False

    def search_youtube(self, query: str) -> list:
        """Busca música no YouTube."""
        try:
            results = search_youtube(query, max_results=5)
            # Converter para estrutura compatível com frontend
            return [
                {
                    "id": r.get("id"),
                    "title": r.get("title", "Sem título"),
                    "duration": r.get("duration", 0),
                    "url": r.get("url"),
                    "webpage_url": r.get("webpage_url"),
                    "thumbnail": r.get("thumbnail"),
                }
                for r in results
            ]
        except Exception as e:
            print(f"Erro ao buscar YouTube: {e}")
            return []

    def download_mp3(self, url: str, title: str, folder: str = "downloads") -> dict:
        """Baixa MP3 do YouTube."""
        try:
            mp3_path = download_mp3(url, title, folder)
            if os.path.exists(mp3_path):
                return {
                    "success": True,
                    "filename": os.path.basename(mp3_path),
                    "path": mp3_path,
                }
            else:
                return {"success": False}
        except Exception as e:
            print(f"Erro ao baixar: {e}")
            return {"success": False}

    def find_cd_drives(self) -> list:
        """Encontra unidades de CD/DVD."""
        try:
            return find_cd_drives()
        except Exception as e:
            print(f"Erro ao encontrar unidades: {e}")
            return []

    def find_mp3_files(self, directory: str) -> dict:
        """Encontra MP3s em um diretório."""
        try:
            return find_mp3_files(directory)
        except Exception as e:
            print(f"Erro ao encontrar MP3s: {e}")
            return {}

    def copy_cd_with_fallback(
        self, cd_path: str, output_base: str = "downloads", selected_files: list = None
    ) -> dict:
        """Copia arquivos do CD com fallback para YouTube."""
        if not cd_path:
            return {"success": False, "total": 0}

        try:
            # Encontrar MP3s no CD
            mp3_dict = find_mp3_files(cd_path)

            if not mp3_dict:
                return {"success": False, "total": 0}

            # Filtrar apenas arquivos selecionados se fornecido
            if selected_files:
                filtered_dict = {}
                for folder, files in mp3_dict.items():
                    filtered_dict[folder] = [
                        f
                        for f in files
                        if any(
                            sf["folder"] == folder and sf["file"] == f for sf in selected_files
                        )
                    ]
                    if not filtered_dict[folder]:
                        del filtered_dict[folder]
                mp3_dict = filtered_dict

            if not mp3_dict:
                return {"success": False, "total": 0}

            total = sum(len(files) for files in mp3_dict.values())
            cd_num = get_next_cd_number(output_base)
            cd_output = os.path.join(output_base, f"cd{cd_num}")
            success = 0
            failed = []

            processed = 0
            start_time = time_module.time()

            # Fase 1: Tentar copiar do CD
            for folder, files in sorted(mp3_dict.items()):
                folder_dest = (
                    cd_output
                    if folder == "."
                    else os.path.join(cd_output, folder)
                )
                os.makedirs(folder_dest, exist_ok=True)

                for file in sorted(files):
                    if not self.copying:
                        break

                    processed += 1
                    src = os.path.join(cd_path, folder, file) if folder != "." else os.path.join(cd_path, file)
                    dst = os.path.join(folder_dest, file)

                    # Atualizar progresso
                    self.window.evaluate_js(
                        f"updateProgress({processed}, {total}, '{file}')"
                    )

                    # Tentar copiar
                    try:
                        import shutil

                        shutil.copy2(src, dst)
                        success += 1
                        cd_metadata = get_mp3_metadata(dst)
                        artwork_b64 = self._get_artwork_b64(cd_metadata)
                        if artwork_b64:
                            self.window.evaluate_js(
                                f"updateArtwork('{artwork_b64}')"
                            )
                    except Exception:
                        # Fallback: YouTube imediatamente
                        title = os.path.splitext(file)[0]
                        cd_metadata = get_mp3_metadata(src)
                        cd_duration = cd_metadata.get("duration_secs")

                        try:
                            results = search_youtube(
                                title, max_results=5, expected_duration_secs=cd_duration
                            )
                            if results:
                                url = (
                                    results[0].get("url")
                                    or results[0].get("webpage_url")
                                    or f"https://www.youtube.com/watch?v={results[0]['id']}"
                                )
                                mp3_path = download_mp3(url, file, folder_dest)

                                if os.path.exists(mp3_path):
                                    if cd_duration and not validate_mp3_duration(
                                        mp3_path, cd_duration, tolerance_percent=30
                                    ):
                                        try:
                                            os.remove(mp3_path)
                                        except Exception:
                                            pass
                                    else:
                                        apply_artwork_to_mp3(mp3_path, cd_metadata)
                                        success += 1
                                        artwork_b64 = self._get_artwork_b64(cd_metadata)
                                        if artwork_b64:
                                            self.window.evaluate_js(
                                                f"updateArtwork('{artwork_b64}')"
                                            )
                        except Exception:
                            pass

                        if success < processed:
                            failed.append((file, folder_dest, title, cd_metadata))

            # Fase 2: Retry com variações
            if failed:
                for file, folder_dest, original_title, cd_metadata in failed[:]:
                    variations = get_name_variations(original_title)
                    cd_duration = cd_metadata.get("duration_secs")

                    for var_title in variations[1:]:
                        try:
                            results = search_youtube(
                                var_title, max_results=5, expected_duration_secs=cd_duration
                            )
                            if results:
                                url = (
                                    results[0].get("url")
                                    or results[0].get("webpage_url")
                                    or f"https://www.youtube.com/watch?v={results[0]['id']}"
                                )
                                mp3_path = download_mp3(url, file, folder_dest)

                                if os.path.exists(mp3_path):
                                    if cd_duration and not validate_mp3_duration(
                                        mp3_path, cd_duration, tolerance_percent=30
                                    ):
                                        try:
                                            os.remove(mp3_path)
                                        except Exception:
                                            pass
                                    else:
                                        apply_artwork_to_mp3(mp3_path, cd_metadata)
                                        success += 1
                                        failed.remove((file, folder_dest, original_title, cd_metadata))
                                        break
                        except Exception:
                            pass

            # Fase 3: Fallback mode (sem validação rigorosa)
            if failed:
                for file, folder_dest, original_title, cd_metadata in failed[:]:
                    variations = get_name_variations(original_title)
                    cd_duration = cd_metadata.get("duration_secs")

                    for var_title in variations[1:]:
                        try:
                            results = search_youtube(
                                var_title, max_results=5, expected_duration_secs=cd_duration
                            )
                            if results:
                                url = (
                                    results[0].get("url")
                                    or results[0].get("webpage_url")
                                    or f"https://www.youtube.com/watch?v={results[0]['id']}"
                                )
                                mp3_path = download_mp3(url, file, folder_dest)

                                if os.path.exists(mp3_path):
                                    if cd_duration and not validate_mp3_duration(
                                        mp3_path, cd_duration, tolerance_percent=30, strict=False
                                    ):
                                        try:
                                            os.remove(mp3_path)
                                        except Exception:
                                            pass
                                    else:
                                        apply_artwork_to_mp3(mp3_path, cd_metadata)
                                        success += 1
                                        failed.remove((file, folder_dest, original_title, cd_metadata))
                                        break
                        except Exception:
                            pass

            return {"success": True, "total": total, "copied": success, "dest": cd_output}

        except Exception as e:
            print(f"Erro ao copiar CD: {e}")
            return {"success": False, "total": 0}

    def browse_folder(self) -> str:
        """Abre diálogo de seleção de pasta."""
        try:
            result = self.window.create_file_dialog(
                webview.FOLDER_DIALOG,
                title="Selecione a pasta de destino",
            )
            return result[0] if result else ""
        except Exception:
            return ""

    def _get_artwork_b64(self, metadata: dict) -> str:
        """Converte artwork bytes para base64."""
        try:
            artwork_bytes = metadata.get("artwork_bytes")
            if artwork_bytes:
                return base64.b64encode(artwork_bytes).decode("utf-8")
        except Exception:
            pass
        return ""


def main():
    """Inicia a aplicação web."""
    # Criar API
    api = None

    def on_window_created(window):
        nonlocal api
        api = API(window)

    # Criar janela
    html_file = os.path.join(os.path.dirname(__file__), "web", "index.html")

    if not os.path.exists(html_file):
        print("Erro: web/index.html não encontrado")
        sys.exit(1)

    window = webview.create_window(
        title="🎵 Isaac Music - Copiar Músicas",
        url=f"file://{html_file}",
        js_api=None,  # Será definido após criar API
        width=1000,
        height=1200,
        resizable=True,
        background_color="#F5F5F5",
        on_top=False,
    )

    # Attach API
    api = API(window)
    window.expose(api)

    # Iniciar aplicação
    webview.start(debug=False)


if __name__ == "__main__":
    main()
