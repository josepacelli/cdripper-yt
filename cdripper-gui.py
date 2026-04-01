#!/usr/bin/env python3
"""
Isaac GUI - versão infantil do downloader.

Interface gráfica com botões grandes para:
- Buscar e baixar música do YouTube
- Copiar músicas MP3 do CD para ./downloads/cdX
- Em caso de erro na cópia, buscar a música no YouTube e baixar
"""

from __future__ import annotations

import os
import platform
import shutil
import sys
import threading
import time
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import messagebox, ttk, filedialog
except Exception as exc:
    print("Erro: tkinter/_tkinter nao esta disponivel neste Python.")
    print(f"Detalhe: {exc}")
    system = platform.system()
    if system == "Linux":
        print("Instale no sistema e tente novamente:")
        print("  Debian/Ubuntu: sudo apt install python3-tk")
        print("  Fedora: sudo dnf install python3-tkinter")
    elif system == "Darwin":
        print("No macOS, use Python oficial de python.org ou um ambiente com Tk habilitado.")
    elif system == "Windows":
        print("No Windows, reinstale o Python oficial marcando o componente tcl/tk e IDLE.")
    else:
        print("Use uma instalacao de Python com suporte a tkinter.")
    raise SystemExit(1)

from cdripper_utils import (
    apply_artwork_to_mp3,
    download_mp3,
    download_mp4,
    enrich_mp3_from_internet,
    fetch_playlist_tracks,
    find_cd_drives,
    find_mp3_files,
    get_mp3_metadata,
    get_next_cd_number,
    search_youtube,
    get_name_variations,
    validate_mp3_duration,
    setup_logging,
    get_logger,
)


class AnimatedSpinner:
    """Spinner animado para mostrar progresso durante operações."""
    def __init__(self):
        self.frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.current = 0

    def next(self):
        frame = self.frames[self.current]
        self.current = (self.current + 1) % len(self.frames)
        return frame


class Win7ProgressBar(tk.Canvas):
    """Barra de progresso estilo Windows 7, com efeito visual."""
    def __init__(self, parent, height=30, **kwargs):
        super().__init__(parent, height=height, bg="#F6FBFF", highlightthickness=0, **kwargs)
        self._value = 0
        self._max_value = 100
        self.height = height
        self.animate_offset = 0
        self.animation_id = None
        self.is_animating = False
        # Vincular evento de redimensionamento
        self.bind("<Configure>", self._on_configure)
        self.draw_progress()

    def __setitem__(self, key: str, value: float) -> None:
        """Suporta interface de dicionário para compatibilidade com ttk.Progressbar."""
        if key == "value":
            self._value = max(0, min(value, self._max_value))
            self.draw_progress()
        elif key == "maximum":
            self._max_value = max(1, value)

    def __getitem__(self, key: str) -> float:
        """Suporta leitura via interface de dicionário."""
        if key == "value":
            return self._value
        elif key == "maximum":
            return self._max_value
        return 0

    def set_value(self, value: float) -> None:
        """Atualiza o valor da barra."""
        self["value"] = value

    def set_max(self, max_value: float) -> None:
        """Define o valor máximo."""
        self["maximum"] = max_value

    def draw_progress(self) -> None:
        """Desenha a barra de progresso."""
        self.delete("all")

        # Obter largura dinâmica do Canvas
        canvas_width = self.winfo_width()
        if canvas_width <= 1:
            canvas_width = 600  # Valor padrão se ainda não foi renderizado

        # Bordas da barra
        border_color = "#A0A0A0"
        self.create_rectangle(1, 1, canvas_width - 1, self.height - 1, outline=border_color, width=1)

        # Fundo cinzento
        self.create_rectangle(2, 2, canvas_width - 2, self.height - 2, fill="#E8E8E8", outline="")

        if self._value > 0:
            # Calcular largura preenchida
            filled_width = (self._value / self._max_value) * (canvas_width - 4)

            # Desenhar barra verde com gradiente (cores do Windows 7)
            # Barra superior (verde mais claro)
            self.create_rectangle(2, 2, filled_width + 2, self.height // 2, fill="#77CC77", outline="")
            # Barra inferior (verde mais escuro)
            self.create_rectangle(2, self.height // 2, filled_width + 2, self.height - 2, fill="#5DAA5D", outline="")

            # Desenhar padrão de linhas animadas (efeito onda)
            self.draw_stripe_pattern(filled_width)

    def draw_stripe_pattern(self, filled_width: float) -> None:
        """Desenha o padrão de linhas animadas."""
        stripe_width = 20
        stripe_spacing = 5
        x = self.animate_offset % (stripe_width + stripe_spacing)

        while x < filled_width:
            # Linhas com transparência simulada (usando cor mais clara)
            self.create_line(x + 2, 2, x + 2, self.height - 2, fill="#AADDAA", width=2)
            x += stripe_width + stripe_spacing

    def _on_configure(self, event) -> None:
        """Redesenha quando o canvas é redimensionado."""
        self.draw_progress()

    def start_animation(self) -> None:
        """Inicia a animação da barra."""
        if not self.is_animating:
            self.is_animating = True
            self._animate()

    def stop_animation(self) -> None:
        """Para a animação da barra."""
        self.is_animating = False
        if self.animation_id:
            self.after_cancel(self.animation_id)
            self.animation_id = None

    def _animate(self) -> None:
        """Anima o padrão de linhas."""
        if self.is_animating:
            self.animate_offset += 2
            self.draw_progress()
            self.animation_id = self.after(50, self._animate)


class IsaacGUIApp:
    def __init__(self, root: tk.Tk) -> None:
        # Configurar logging para arquivo
        try:
            setup_logging("cdripper.log")
            self.logger = get_logger()
        except Exception:
            # Se logging falhar, criar dummy logger
            import logging
            self.logger = logging.getLogger("cdripper_dummy")

        self.root = root
        self.root.title("Isaac Music - Modo Infantil")
        self.root.geometry("1280x770")
        self.root.minsize(980, 680)
        self.root.configure(bg="#F6FBFF")

        self.current_results: list[dict] = []
        self.current_drives: list[str] = []
        self.current_cd_path: str | None = None
        self.cancel_copy: bool = False  # Flag para cancelar cópia
        self.copy_start_time: float = 0  # Tempo de início da cópia
        self.spinner = AnimatedSpinner()  # Spinner animado
        self.copying_in_progress: bool = False  # Flag para indicar cópia em andamento
        self.spinner_animation_id: str | None = None  # ID do agendamento de animação

        # Vídeo YouTube (MP4)
        self.video_results: list[dict] = []  # Resultados da busca de vídeos
        self.video_cancel: bool = False  # Flag para cancelar download de vídeo
        self.video_in_progress: bool = False  # Flag para indicar download em andamento
        self.video_start_time: float = 0.0  # Tempo de início do download

        # Navegação hierárquica de pastas (Treeview)
        self.nav_root_items: list[str] = []  # Drives + pastas locais adicionadas
        self.nav_selected_source: str | None = None  # Caminho selecionado no treeview
        self.nav_item_to_path: dict[str, str] = {}  # Mapeamento de tree item ID → caminho absoluto
        self.nav_loaded_items: set[str] = set()  # Tree items já carregados (evita reload)

        # Playlist YouTube
        self.playlist_tracks: list[dict] = []  # Faixas carregadas da playlist
        self.playlist_cancel: bool = False  # Flag para cancelar download da playlist
        self.playlist_start_time: float = 0.0  # Tempo de início do download
        self.playlist_in_progress: bool = False  # Flag para indicar download em andamento

        self._build_styles()
        self._build_header()
        self._build_tabs()

    def _log(self, message: str) -> None:
        """Log para arquivo e console."""
        print(message)
        try:
            if hasattr(self, 'logger'):
                self.logger.info(message)
        except Exception:
            pass  # Se logger falhar, continua só com print

    def _build_styles(self) -> None:
        self.title_font = ("Arial Rounded MT Bold", 28)
        self.section_font = ("Arial Rounded MT Bold", 19)
        self.text_font = ("Arial", 14)
        self.big_btn_font = ("Arial Rounded MT Bold", 16)

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("TNotebook", background="#F6FBFF", borderwidth=0)
        style.configure("TNotebook.Tab", font=("Arial Rounded MT Bold", 13), padding=(18, 10))
        style.map("TNotebook.Tab", background=[("selected", "#BDE0FE"), ("!selected", "#EAF6FF")])

        # Estilo para o Treeview
        rowheight = 72 if platform.system() == "Linux" else 28
        style.configure("Treeview", font=("Arial", 19), rowheight=rowheight)
        style.configure("Treeview.Heading", font=("Arial", 12, "bold"))

    def _build_header(self) -> None:
        header = tk.Frame(self.root, bg="#CDEBFF", height=110)
        header.pack(fill="x")

        title = tk.Label(
            header,
            text="🎵 Isaac Music 🎵",
            font=self.title_font,
            bg="#CDEBFF",
            fg="#083B66",
        )
        title.pack(pady=(12, 0))

        subtitle = tk.Label(
            header,
            text="Escolha uma opção para ouvir suas músicas!",
            font=("Arial", 14, "bold"),
            bg="#CDEBFF",
            fg="#175A8A",
        )
        subtitle.pack(pady=(4, 8))

    def _build_tabs(self) -> None:
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=16, pady=14)

        self.youtube_tab = tk.Frame(notebook, bg="#F6FBFF")
        self.cd_tab = tk.Frame(notebook, bg="#F6FBFF")
        self.playlist_tab = tk.Frame(notebook, bg="#F6FBFF")
        self.video_tab = tk.Frame(notebook, bg="#F6FBFF")

        notebook.add(self.youtube_tab, text="📺 YouTube")
        notebook.add(self.cd_tab, text="💿 Copiar CD")
        notebook.add(self.playlist_tab, text="💿 Playlist")
        notebook.add(self.video_tab, text="🎬 Baixar Vídeo")

        self._build_youtube_tab()
        self._build_cd_tab()
        self._build_playlist_tab()
        self._build_video_tab()

    def _build_youtube_tab(self) -> None:
        container = tk.Frame(self.youtube_tab, bg="#F6FBFF")
        container.pack(fill="both", expand=True, padx=12, pady=10)

        tk.Label(
            container,
            text="1) Escreva o nome da música",
            font=self.section_font,
            bg="#F6FBFF",
            fg="#114B5F",
        ).pack(anchor="w", pady=(0, 6))

        query_row = tk.Frame(container, bg="#F6FBFF")
        query_row.pack(fill="x", pady=(0, 12))

        self.youtube_query = tk.Entry(query_row, font=self.text_font)
        self.youtube_query.pack(side="left", fill="x", expand=True, ipady=8)

        search_btn = tk.Button(
            query_row,
            text="🔎 Procurar",
            font=self.big_btn_font,
            bg="#00B4D8",
            fg="white",
            activebackground="#0096C7",
            padx=20,
            pady=8,
            command=self.search_music,
        )
        search_btn.pack(side="left", padx=(10, 0))

        tk.Label(
            container,
            text="2) Escolha uma música na lista",
            font=self.section_font,
            bg="#F6FBFF",
            fg="#114B5F",
        ).pack(anchor="w", pady=(6, 6))

        list_frame = tk.Frame(container, bg="#F6FBFF")
        list_frame.pack(fill="both", expand=True)

        self.results_list = tk.Listbox(
            list_frame,
            font=("Arial", 14),
            height=10,
            activestyle="none",
            selectbackground="#90E0EF",
            selectforeground="#023E8A",
        )
        self.results_list.pack(side="left", fill="both", expand=True)

        scroll = tk.Scrollbar(list_frame, command=self.results_list.yview)
        scroll.pack(side="right", fill="y")
        self.results_list.configure(yscrollcommand=scroll.set)

        # Input para pasta de destino (YouTube)
        path_frame_yt = tk.Frame(container, bg="#F6FBFF")
        path_frame_yt.pack(fill="x", pady=(8, 0))

        tk.Label(
            path_frame_yt,
            text="Pasta de destino:",
            font=("Arial", 12, "bold"),
            bg="#F6FBFF",
            fg="#114B5F",
        ).pack(side="left", padx=(0, 8))

        self.youtube_output_entry = tk.Entry(
            path_frame_yt,
            font=("Arial", 12),
            bg="white",
            fg="#333333",
            width=20,
        )
        self.youtube_output_entry.pack(side="left")
        self.youtube_output_entry.insert(0, "downloads")

        action_row = tk.Frame(container, bg="#F6FBFF")
        action_row.pack(fill="x", pady=(12, 8))

        self.youtube_status = tk.Label(
            action_row,
            text="3) Clique no botão para baixar",
            font=("Arial", 13, "bold"),
            bg="#F6FBFF",
            fg="#2B9348",
        )
        self.youtube_status.pack(side="left")

        download_btn = tk.Button(
            action_row,
            text="⬇️ Baixar música",
            font=self.big_btn_font,
            bg="#2A9D8F",
            fg="white",
            activebackground="#21867A",
            padx=24,
            pady=10,
            command=self.download_selected_music,
        )
        download_btn.pack(side="right")

    def _build_cd_tab(self) -> None:
        container = tk.Frame(self.cd_tab, bg="#F6FBFF")
        container.pack(fill="both", expand=True, padx=12, pady=10)

        # ────────────────────────────────────────────────────────────────────
        # Botões de ação (Procurar CDs + Adicionar pasta local)
        # ────────────────────────────────────────────────────────────────────
        top_row = tk.Frame(container, bg="#F6FBFF")
        top_row.pack(fill="x", pady=(0, 12))

        scan_btn = tk.Button(
            top_row,
            text="💿 Procurar CDs",
            font=self.big_btn_font,
            bg="#FFB703",
            fg="#4A2D00",
            activebackground="#F4A261",
            padx=20,
            pady=8,
            command=self.scan_cd_drives,
        )
        scan_btn.pack(side="left")

        add_folder_btn = tk.Button(
            top_row,
            text="📁 Adicionar pasta local",
            font=self.big_btn_font,
            bg="#8ECAE6",
            fg="#09324C",
            activebackground="#74B7D6",
            padx=20,
            pady=8,
            command=self._add_local_folder,
        )
        add_folder_btn.pack(side="left", padx=(12, 0))

        # ────────────────────────────────────────────────────────────────────
        # Navegador hierárquico (Treeview)
        # ────────────────────────────────────────────────────────────────────
        nav_label = tk.Label(
            container,
            text="1) Escolha uma pasta",
            font=self.section_font,
            bg="#F6FBFF",
            fg="#6B4E16",
        )
        nav_label.pack(anchor="w", pady=(4, 6))

        nav_frame = tk.Frame(container, bg="#F6FBFF")
        nav_frame.pack(fill="both", expand=True, pady=(0, 12))

        # Treeview com scrollbar
        scrollbar = ttk.Scrollbar(nav_frame)
        scrollbar.pack(side="right", fill="y")

        self.nav_tree = ttk.Treeview(
            nav_frame,
            height=6,
            yscrollcommand=scrollbar.set,
        )
        self.nav_tree.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.nav_tree.yview)

        # Configurar coluna principal com largura apropriada
        self.nav_tree.column("#0", width=350, minwidth=250)

        # Bind para carregar subpastas ao expandir
        self.nav_tree.bind("<<TreeviewOpen>>", self._on_tree_expand)
        self.nav_tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # ────────────────────────────────────────────────────────────────────
        # Label de source selecionado
        # ────────────────────────────────────────────────────────────────────
        self.cd_source_label = tk.Label(
            container,
            text="Nenhuma pasta selecionada",
            font=("Arial", 12, "bold"),
            bg="#F6FBFF",
            fg="#666666",
        )
        self.cd_source_label.pack(anchor="w", pady=(0, 8))

        # ────────────────────────────────────────────────────────────────────
        # Destino da cópia
        # ────────────────────────────────────────────────────────────────────
        dest_row = tk.Frame(container, bg="#F6FBFF")
        dest_row.pack(fill="x", pady=(0, 8))

        tk.Label(
            dest_row,
            text="Pasta destino:",
            font=("Arial", 12, "bold"),
            bg="#F6FBFF",
            fg="#264653",
        ).pack(side="left", padx=(0, 8))

        self.cd_output_entry = tk.Entry(
            dest_row,
            font=("Arial", 12),
            bg="white",
            fg="#333333",
            width=20,
        )
        self.cd_output_entry.pack(side="left")
        self.cd_output_entry.insert(0, "downloads")
        self.cd_output_entry.bind("<KeyRelease>", lambda e: self._update_cd_target_label())

        self.cd_target_label = tk.Label(
            dest_row,
            text="",
            font=("Arial", 13, "bold"),
            bg="#F6FBFF",
            fg="#264653",
        )
        self.cd_target_label.pack(side="left", padx=(10, 0))

        self._update_cd_target_label()

        tk.Label(
            container,
            text="2) Confira a lista antes de copiar",
            font=self.section_font,
            bg="#F6FBFF",
            fg="#6B4E16",
        ).pack(anchor="w", pady=(4, 6))

        self.cd_preview_text = tk.Text(
            container,
            font=("Courier", 12),
            height=8,
            wrap="word",
            bg="#FFFFFF",
            fg="#333333",
        )
        self.cd_preview_text.pack(fill="both", expand=True)
        self.cd_preview_text.insert("1.0", "Nenhum CD selecionado ainda.\n")
        self.cd_preview_text.configure(state="disabled")

        # Frame de progresso (oculto por padrão)
        self.cd_progress_frame = tk.Frame(container, bg="#F6FBFF")
        self.cd_progress_frame.pack(fill="x", pady=(10, 0))

        # Frame com diretório de origem + nome do arquivo
        info_frame = tk.Frame(self.cd_progress_frame, bg="#F6FBFF")
        info_frame.pack(fill="x", pady=(0, 8))

        # Diretório de origem
        self.cd_source_dir_label = tk.Label(
            info_frame,
            text="",
            font=("Arial", 10),
            bg="#F6FBFF",
            fg="#666666",
            anchor="w",
            justify="left",
        )
        self.cd_source_dir_label.pack(fill="x", anchor="w")

        # Nome do arquivo
        self.cd_current_file_label = tk.Label(
            info_frame,
            text="",
            font=("Arial", 13, "bold"),
            bg="#F6FBFF",
            fg="#333333",
            anchor="w",
            justify="left",
        )
        self.cd_current_file_label.pack(fill="x", anchor="w")

        # Placeholder para artwork (mantido para compatibilidade, mas oculto)
        self.cd_artwork_label = tk.Label(self.cd_progress_frame)
        self.cd_artwork_photo = None  # Referência para evitar garbage collection

        self.cd_progress_bar = Win7ProgressBar(
            self.cd_progress_frame,
            height=30,
        )
        self.cd_progress_bar.pack(fill="x", expand=True, pady=(0, 8))

        progress_info = tk.Frame(self.cd_progress_frame, bg="#F6FBFF")
        progress_info.pack(fill="x", pady=(0, 4))

        self.cd_progress_percent = tk.Label(
            progress_info,
            text="0%",
            font=("Arial", 14, "bold"),
            bg="#F6FBFF",
            fg="#264653",
        )
        self.cd_progress_percent.pack(side="left")

        self.cd_progress_count = tk.Label(
            progress_info,
            text="0/0 arquivos",
            font=("Arial", 12),
            bg="#F6FBFF",
            fg="#666666",
        )
        self.cd_progress_count.pack(side="left", padx=(20, 0))

        self.cd_progress_speed = tk.Label(
            progress_info,
            text="0 KB/s",
            font=("Arial", 12),
            bg="#F6FBFF",
            fg="#666666",
        )
        self.cd_progress_speed.pack(side="left", padx=(20, 0))

        self.cd_progress_eta = tk.Label(
            progress_info,
            text="ETA: --",
            font=("Arial", 12, "bold"),
            bg="#F6FBFF",
            fg="#264653",
        )
        self.cd_progress_eta.pack(side="left", padx=(20, 0))

        # Botão de cancelar
        self.cd_cancel_btn = tk.Button(
            progress_info,
            text="⛔ Cancelar",
            font=("Arial", 10, "bold"),
            bg="#B00020",
            fg="white",
            activebackground="#8B0000",
            padx=12,
            pady=4,
            command=self._cancel_copy,
        )
        self.cd_cancel_btn.pack(side="right", padx=(10, 0))

        # Botão de "Mais detalhes"
        details_frame = tk.Frame(self.cd_progress_frame, bg="#F6FBFF")
        details_frame.pack(fill="x", pady=(8, 0))

        self.cd_details_btn = tk.Button(
            details_frame,
            text="▼ Mais detalhes",
            font=("Arial", 10),
            bg="#E0E0E0",
            fg="#333333",
            activebackground="#D0D0D0",
            padx=8,
            pady=4,
            command=self._toggle_details,
        )
        self.cd_details_btn.pack(side="left")

        # Painel de detalhes (expandido)
        self.cd_details_expanded = False
        self.cd_details_panel = tk.Frame(self.cd_progress_frame, bg="#F0F0F0", relief="sunken", borderwidth=1)

        self.cd_details_text = tk.Text(
            self.cd_details_panel,
            font=("Courier", 10),
            height=8,
            wrap="word",
            bg="#FFFFFF",
            fg="#333333",
        )
        self.cd_details_text.pack(fill="both", expand=True, padx=4, pady=4)
        self.cd_details_text.configure(state="disabled")

        # Inicialmente oculto
        self.cd_progress_frame.pack_forget()

        copy_row = tk.Frame(container, bg="#F6FBFF")
        copy_row.pack(fill="x", pady=(10, 6))

        copy_btn = tk.Button(
            copy_row,
            text="📥 Copiar para downloads/cdX",
            font=self.big_btn_font,
            bg="#E76F51",
            fg="white",
            activebackground="#D75A3A",
            padx=20,
            pady=10,
            command=self.start_copy_cd,
        )
        copy_btn.pack(side="right")

        self.cd_status = tk.Label(
            copy_row,
            text="🎵 Vamos copiar as músicas para o computador!",
            font=("Arial", 12, "bold"),
            bg="#F6FBFF",
            fg="#2B9348",
        )
        self.cd_status.pack(side="left")

    def _build_playlist_tab(self) -> None:
        container = tk.Frame(self.playlist_tab, bg="#F6FBFF")
        container.pack(fill="both", expand=True, padx=16, pady=14)

        # Passo 1: Entrada de URL ou nome
        step1_label = tk.Label(
            container,
            text="1) Cole a URL ou nome do artista/álbum",
            font=self.section_font,
            bg="#F6FBFF",
            fg="#175A8A",
        )
        step1_label.pack(anchor="w", pady=(0, 8))

        self.playlist_query = tk.Entry(
            container,
            font=self.text_font,
            bg="white",
            fg="#333333",
            relief="solid",
            borderwidth=2,
        )
        self.playlist_query.pack(fill="x", pady=(0, 8))

        load_button = tk.Button(
            container,
            text="🔍 Carregar faixas",
            font=("Arial", 14, "bold"),
            bg="#FEAE1B",
            fg="white",
            padx=20,
            pady=12,
            border=0,
            cursor="hand2",
            command=self._load_playlist_tracks,
        )
        load_button.pack(anchor="w", pady=(0, 16))

        # Passo 2: Preview de faixas
        step2_label = tk.Label(
            container,
            text="2) Confira as faixas",
            font=self.section_font,
            bg="#F6FBFF",
            fg="#175A8A",
        )
        step2_label.pack(anchor="w", pady=(8, 8))

        self.playlist_preview_text = tk.Text(
            container,
            font=("Courier", 12),
            bg="white",
            fg="#333333",
            height=10,
            state="disabled",
        )
        self.playlist_preview_text.pack(fill="both", expand=True, pady=(0, 12))

        # Pasta de destino
        dest_frame = tk.Frame(container, bg="#F6FBFF")
        dest_frame.pack(fill="x", pady=(0, 8))

        dest_label = tk.Label(
            dest_frame,
            text="Pasta destino:",
            font=("Arial", 12, "bold"),
            bg="#F6FBFF",
            fg="#175A8A",
        )
        dest_label.pack(side="left", padx=(0, 8))

        self.playlist_output_entry = tk.Entry(
            dest_frame,
            font=self.text_font,
            bg="white",
            fg="#333333",
        )
        self.playlist_output_entry.insert(0, "downloads")
        self.playlist_output_entry.pack(side="left", fill="x", expand=True)

        # Status line
        self.playlist_status = tk.Label(
            container,
            text="",
            font=("Arial", 11),
            bg="#F6FBFF",
            fg="#666666",
        )
        self.playlist_status.pack(anchor="w", pady=(4, 8))

        # Botão de download (inicialmente visível)
        download_button = tk.Button(
            container,
            text="🎵 Baixar tudo",
            font=("Arial", 14, "bold"),
            bg="#2B9348",
            fg="white",
            padx=20,
            pady=12,
            border=0,
            cursor="hand2",
            command=self._start_playlist_download,
        )
        download_button.pack(anchor="w", pady=(0, 12))

        # Progress frame (inicialmente oculto)
        self.playlist_progress_frame = tk.Frame(container, bg="#F6FBFF")
        self.playlist_progress_frame.pack_forget()

        self.playlist_progress_bar = Win7ProgressBar(self.playlist_progress_frame, height=24)
        self.playlist_progress_bar.pack(fill="x", pady=(10, 8))

        progress_info = tk.Frame(self.playlist_progress_frame, bg="#F6FBFF")
        progress_info.pack(fill="x", pady=(0, 8))

        self.playlist_progress_percent = tk.Label(
            progress_info,
            text="0%",
            font=("Arial", 11, "bold"),
            bg="#F6FBFF",
            fg="#175A8A",
        )
        self.playlist_progress_percent.pack(side="left", padx=(0, 16))

        self.playlist_progress_count = tk.Label(
            progress_info,
            text="0/0 faixas",
            font=("Arial", 11, "bold"),
            bg="#F6FBFF",
            fg="#175A8A",
        )
        self.playlist_progress_count.pack(side="left", padx=(0, 16))

        self.playlist_progress_speed = tk.Label(
            progress_info,
            text="",
            font=("Arial", 11),
            bg="#F6FBFF",
            fg="#666666",
        )
        self.playlist_progress_speed.pack(side="left", padx=(0, 16))

        cancel_button = tk.Button(
            self.playlist_progress_frame,
            text="⊘ Cancelar",
            font=("Arial", 12, "bold"),
            bg="#E74C3C",
            fg="white",
            padx=16,
            pady=10,
            border=0,
            cursor="hand2",
            command=self._cancel_playlist,
        )
        cancel_button.pack(anchor="w", pady=(8, 0))

    def _build_video_tab(self) -> None:
        """Constrói a aba de download de vídeo em MP4."""
        container = tk.Frame(self.video_tab, bg="#F6FBFF")
        container.pack(fill="both", expand=True, padx=16, pady=14)

        # Seção 1: Busca por nome ou URL
        search_label = tk.Label(
            container,
            text="1) Nome ou URL do vídeo:",
            font=self.section_font,
            bg="#F6FBFF",
            fg="#114B5F",
        )
        search_label.pack(anchor="w", pady=(0, 8))

        search_frame = tk.Frame(container, bg="#F6FBFF")
        search_frame.pack(fill="x", pady=(0, 16))

        self.video_query = tk.Entry(search_frame, font=self.text_font, width=40)
        self.video_query.pack(side="left", fill="x", expand=True, padx=(0, 8))

        search_btn = tk.Button(
            search_frame,
            text="🔍 Procurar",
            font=self.big_btn_font,
            bg="#00B4D8",
            fg="white",
            padx=16,
            pady=8,
            command=self._search_video,
        )
        search_btn.pack(side="left")

        # Seção 2: Lista de resultados
        results_label = tk.Label(
            container,
            text="2) Escolha o vídeo:",
            font=self.section_font,
            bg="#F6FBFF",
            fg="#114B5F",
        )
        results_label.pack(anchor="w", pady=(0, 8))

        results_frame = tk.Frame(container, bg="white", relief="solid", borderwidth=1)
        results_frame.pack(fill="both", expand=True, pady=(0, 16))

        self.video_results_list = tk.Listbox(
            results_frame,
            font=self.text_font,
            height=6,
            selectmode="single",
            bg="white",
            fg="#114B5F",
            selectbackground="#90E0EF",
            selectforeground="#023E8A",
        )
        self.video_results_list.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(results_frame, command=self.video_results_list.yview)
        scrollbar.pack(side="right", fill="y")
        self.video_results_list.config(yscrollcommand=scrollbar.set)

        # Seção 3: Pasta de destino
        dest_label = tk.Label(
            container,
            text="Pasta de destino:",
            font=self.section_font,
            bg="#F6FBFF",
            fg="#114B5F",
        )
        dest_label.pack(anchor="w", pady=(0, 8))

        self.video_output_entry = tk.Entry(container, font=self.text_font)
        self.video_output_entry.insert(0, "downloads")
        self.video_output_entry.pack(fill="x", pady=(0, 16))

        # Status
        self.video_status = tk.Label(
            container,
            text="Pronto para baixar",
            font=("Arial", 12),
            bg="#F6FBFF",
            fg="#114B5F",
        )
        self.video_status.pack(anchor="w", pady=(0, 8))

        # Botão de download
        download_btn = tk.Button(
            container,
            text="🎬 Baixar em MP4",
            font=self.big_btn_font,
            bg="#7B2FBE",
            fg="white",
            padx=20,
            pady=10,
            command=self._download_video,
        )
        download_btn.pack(fill="x", pady=(0, 16))

        # Frame de progresso (oculto por padrão)
        self.video_progress_frame = tk.Frame(container, bg="#F6FBFF")

        progress_bar_frame = tk.Frame(self.video_progress_frame, bg="#F6FBFF")
        progress_bar_frame.pack(fill="x", pady=(0, 8))

        self.video_progress_bar = Win7ProgressBar(progress_bar_frame, height=30)
        self.video_progress_bar.pack(fill="x", expand=True)

        progress_info = tk.Frame(self.video_progress_frame, bg="#F6FBFF")
        progress_info.pack(fill="x", pady=(0, 8))

        self.video_progress_percent = tk.Label(
            progress_info,
            text="0%",
            font=("Arial", 11, "bold"),
            bg="#F6FBFF",
            fg="#175A8A",
        )
        self.video_progress_percent.pack(side="left", padx=(0, 16))

        self.video_progress_size = tk.Label(
            progress_info,
            text="0.0 MB / 0.0 MB",
            font=("Arial", 11),
            bg="#F6FBFF",
            fg="#175A8A",
        )
        self.video_progress_size.pack(side="left", padx=(0, 16))

        self.video_progress_speed = tk.Label(
            progress_info,
            text="0.0 MB/s",
            font=("Arial", 11),
            bg="#F6FBFF",
            fg="#175A8A",
        )
        self.video_progress_speed.pack(side="left", padx=(0, 16))

        self.video_progress_eta = tk.Label(
            progress_info,
            text="ETA: --",
            font=("Arial", 11),
            bg="#F6FBFF",
            fg="#175A8A",
        )
        self.video_progress_eta.pack(side="left", expand=True)

        # Nome do arquivo e botão cancelar
        file_info = tk.Frame(self.video_progress_frame, bg="#F6FBFF")
        file_info.pack(fill="x", pady=(8, 0))

        self.video_current_file = tk.Label(
            file_info,
            text="⠋ Baixando...",
            font=("Arial", 11),
            bg="#F6FBFF",
            fg="#175A8A",
        )
        self.video_current_file.pack(side="left", expand=True)

        self.video_cancel_btn = tk.Button(
            file_info,
            text="⏹ Parar",
            font=("Arial", 11, "bold"),
            bg="#B00020",
            fg="white",
            padx=12,
            pady=4,
            command=self._cancel_video,
        )
        self.video_cancel_btn.pack(side="right")

    def _search_video(self) -> None:
        """Busca vídeos no YouTube por nome ou URL."""
        query = self.video_query.get().strip()
        if not query:
            return

        # Se for URL, não precisa buscar
        if query.startswith("http://") or query.startswith("https://"):
            self.video_results = [{"title": query, "url": query, "duration": None, "id": ""}]
            self.video_results_list.delete(0, tk.END)
            self.video_results_list.insert(tk.END, f"01. {query}")
            self.video_status.configure(text="✔ URL válida, pronto para baixar", fg="#2B9348")
            return

        # Busca por nome
        self.video_status.configure(text="🔍 Buscando...", fg="#005F73")
        self.video_results_list.delete(0, tk.END)

        def worker():
            try:
                results = search_youtube(query, max_results=8)
                self.root.after(0, lambda: self._on_video_search_done(results))
            except Exception as e:
                self.root.after(0, lambda: self._on_video_search_error(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_video_search_done(self, results: list[dict]) -> None:
        """Callback quando busca no YouTube termina."""
        if not results:
            self.video_status.configure(text="⊘ Nenhum vídeo encontrado", fg="#B00020")
            return

        self.video_results = results
        self.video_results_list.delete(0, tk.END)

        for idx, video in enumerate(results, 1):
            title = video.get("title", "Sem título")
            duration = video.get("duration", 0) or 0
            minutes = int(duration) // 60
            seconds = int(duration) % 60
            display_text = f"{idx:02d}. {title}   ({minutes}:{seconds:02d})"
            self.video_results_list.insert(tk.END, display_text)

        self.video_status.configure(
            text=f"✔ {len(results)} vídeo(s) encontrado(s)",
            fg="#2B9348"
        )

    def _on_video_search_error(self, exc: Exception) -> None:
        """Callback para erro na busca de vídeo."""
        self.video_status.configure(
            text="⊘ Erro na busca",
            fg="#B00020"
        )
        self._log(f"Erro ao buscar vídeo: {exc}")

    def _download_video(self) -> None:
        """Inicia download do vídeo selecionado em MP4."""
        sel = self.video_results_list.curselection()
        if not sel:
            messagebox.showwarning("Seleção necessária", "Escolha um vídeo para baixar.")
            return

        idx = sel[0]
        if idx >= len(self.video_results):
            return

        result = self.video_results[idx]
        url = result.get("url") or result.get("webpage_url")
        if not url and result.get("id"):
            url = f"https://www.youtube.com/watch?v={result['id']}"

        if not url:
            messagebox.showerror("Erro", "Não foi possível extrair a URL do vídeo.")
            return

        title = result.get("title", "vídeo")
        output_dir = self.video_output_entry.get().strip() or "downloads"

        # Mostrar barra de progresso
        self.video_progress_frame.pack(fill="x", pady=(16, 0))
        self.video_progress_bar["maximum"] = 100
        self.video_progress_bar["value"] = 0
        self.video_progress_bar.start_animation()
        self.video_progress_percent.configure(text="0%")
        self.video_progress_size.configure(text="0.0 MB / 0.0 MB")
        self.video_progress_speed.configure(text="0.0 MB/s")
        self.video_progress_eta.configure(text="ETA: --")
        self.video_current_file.configure(text=f"⠋ Baixando: {title}")
        self.video_cancel_btn.configure(state="normal", text="⏹ Parar")

        self.video_cancel = False
        self.video_in_progress = True
        self.video_start_time = time.time()

        # Criar hook de progresso
        class VideoProgressHook:
            def __init__(hook_self, parent_self):
                hook_self.parent = parent_self
                hook_self.spinner = AnimatedSpinner()

            def __call__(hook_self, d):
                if d.get("status") != "downloading":
                    return

                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes", 0)
                speed = d.get("speed") or 0

                if total:
                    pct = int(downloaded / total * 100)
                    hook_self.parent.root.after(
                        0,
                        lambda pct=pct, down=downloaded, tot=total, spd=speed:
                        hook_self.parent._update_video_progress(pct, down, tot, spd)
                    )

        progress_hook = VideoProgressHook(self)

        def worker():
            try:
                download_mp4(url, title, output_dir, progress_hook)
                self.root.after(0, lambda: self._on_video_download_done(title, output_dir))
            except Exception as e:
                self.root.after(0, lambda: self._on_video_download_error(e))

        threading.Thread(target=worker, daemon=True).start()

    def _update_video_progress(self, pct: int, downloaded: int, total: int, speed: float) -> None:
        """Atualiza barra de progresso do download de vídeo."""
        if self.video_cancel:
            return

        self.video_progress_bar["value"] = pct
        self.video_progress_percent.configure(text=f"{pct}%")

        downloaded_mb = downloaded / (1024 * 1024)
        total_mb = total / (1024 * 1024)
        self.video_progress_size.configure(text=f"{downloaded_mb:.1f} MB / {total_mb:.1f} MB")

        speed_mb = speed / (1024 * 1024)
        self.video_progress_speed.configure(text=f"{speed_mb:.1f} MB/s")

        if speed > 0 and downloaded < total:
            eta_secs = int((total - downloaded) / speed)
            self.video_progress_eta.configure(text=f"ETA: {eta_secs}s")

    def _cancel_video(self) -> None:
        """Cancela o download de vídeo."""
        self.video_cancel = True
        self.video_cancel_btn.configure(state="disabled", text="⏹ Cancelando...")

    def _on_video_download_done(self, title: str, output_dir: str) -> None:
        """Callback quando download de vídeo termina."""
        self.video_in_progress = False
        self.video_progress_bar.stop_animation()
        self.video_cancel_btn.configure(state="normal", text="⏹ Parar")
        self.video_status.configure(text="✔ Download concluído!", fg="#2B9348")
        self._log(f"Vídeo '{title}' baixado em {output_dir}")
        messagebox.showinfo(
            "Tudo pronto",
            f"Vídeo salvo em:\n{output_dir}/{title}.mp4"
        )

    def _on_video_download_error(self, exc: Exception) -> None:
        """Callback para erro no download de vídeo."""
        self.video_in_progress = False
        self.video_progress_bar.stop_animation()
        self.video_cancel_btn.configure(state="normal", text="⏹ Parar")
        self.video_status.configure(text="⊘ Erro no download", fg="#B00020")
        self._log(f"Erro ao baixar vídeo: {exc}")

    def _update_cd_target_label(self) -> None:
        """Atualiza o label de destino quando a pasta é alterada."""
        output_base = self.cd_output_entry.get().strip() or "downloads"
        next_cd = get_next_cd_number(output_base)
        self.cd_target_label.configure(text=f"Destino: ./{output_base}/cd{next_cd}")

    def _show_progress_bar(self, total: int) -> None:
        """Mostra a barra de progresso e oculta o preview text."""
        self.cd_preview_text.pack_forget()
        self.cd_progress_frame.pack(fill="x", pady=(10, 0))
        self.cd_progress_bar["maximum"] = total
        self.cd_progress_bar["value"] = 0
        self.cd_progress_bar.start_animation()  # Iniciar animação da barra
        self.cd_current_file_label.configure(text="Iniciando…")
        self.cd_source_dir_label.configure(text="")
        self.cd_progress_percent.configure(text="0%")
        self.cd_progress_count.configure(text=f"0/{total} arquivos")

    def _hide_progress_bar(self) -> None:
        """Oculta a barra de progresso e mostra o preview text."""
        self.cd_progress_bar.stop_animation()  # Parar animação da barra
        self.cd_progress_frame.pack_forget()
        self.cd_preview_text.pack(fill="both", expand=True)

    def _update_progress(self, done: int, total: int, filename: str = "", source_dir: str = "") -> None:
        """Atualiza a barra de progresso com velocidade, ETA e diretório de origem."""
        pct = int((done / total * 100)) if total > 0 else 0
        self.cd_progress_bar["value"] = done

        # Mostrar diretório de origem e nome do arquivo
        if source_dir:
            self.cd_source_dir_label.configure(text=f"Source: {source_dir}")
        if filename:
            self.cd_current_file_label.configure(text=f"Arquivo: {filename}")

        # Calcular velocidade e ETA
        elapsed = time.time() - self.copy_start_time
        if elapsed > 0 and done > 0:
            speed_kb_s = (done / elapsed) / 1024 if elapsed > 0 else 0
            remaining = total - done
            if speed_kb_s > 0:
                eta_seconds = remaining / speed_kb_s if speed_kb_s > 0 else 0
                eta_min = int(eta_seconds // 60)
                eta_sec = int(eta_seconds % 60)
                if eta_min > 0:
                    eta_text = f"ETA: {eta_min}m {eta_sec}s"
                else:
                    eta_text = f"ETA: {eta_sec}s"
            else:
                eta_text = "ETA: --"

            speed_text = f"{speed_kb_s:.0f} KB/s"
        else:
            speed_text = "0 KB/s"
            eta_text = "ETA: --"

        self.cd_progress_percent.configure(text=f"{pct}%")
        self.cd_progress_count.configure(text=f"{done}/{total} arquivos")
        self.cd_progress_speed.configure(text=speed_text)
        self.cd_progress_eta.configure(text=eta_text)

        if filename:
            spinner = self.spinner.next()
            display_name = filename[:45] + "…" if len(filename) > 45 else filename
            self.cd_current_file_label.configure(text=f"{spinner} Processando: {display_name}")

        self.root.update_idletasks()

    def _animate_spinner(self) -> None:
        """Anima continuamente o spinner enquanto cópia está em andamento."""
        if not self.copying_in_progress:
            return

        # Atualizar apenas o spinner sem alterar outros dados
        spinner_frame = self.spinner.next()
        if self.cd_current_file_label.cget("text"):
            current_text = self.cd_current_file_label.cget("text")
            # Remover spinner antigo e adicionar novo
            if " Processando:" in current_text:
                filename_part = current_text.split(" Processando:", 1)[1].strip()
                display_name = filename_part[:45] + "…" if len(filename_part) > 45 else filename_part
                self.cd_current_file_label.configure(text=f"{spinner_frame} Processando: {display_name}")

        # Agendar próxima animação em 100ms
        self.spinner_animation_id = self.root.after(100, self._animate_spinner)

    def _cancel_copy(self) -> None:
        """Sinaliza para cancelar a cópia em andamento."""
        self.cancel_copy = True
        self.cd_cancel_btn.configure(state="disabled", text="⏹ Cancelando…")

    def _toggle_details(self) -> None:
        """Expande ou contrai o painel de detalhes."""
        if self.cd_details_expanded:
            # Contrair
            self.cd_details_panel.pack_forget()
            self.cd_details_btn.configure(text="▼ Mais detalhes")
            self.cd_details_expanded = False
        else:
            # Expandir
            self.cd_details_panel.pack(fill="both", expand=True, pady=(0, 8))
            self.cd_details_btn.configure(text="▲ Menos detalhes")
            self.cd_details_expanded = True

    def _update_details_log(self, message: str) -> None:
        """Adiciona uma mensagem ao log de detalhes."""
        self.cd_details_text.configure(state="normal")
        self.cd_details_text.insert(tk.END, message + "\n")
        self.cd_details_text.see(tk.END)
        self.cd_details_text.configure(state="disabled")

    def _update_cd_artwork(self, artwork_bytes: bytes | None, mime: str = "image/jpeg") -> None:
        """Atualiza a imagem de capa exibida durante a cópia. Chamado via root.after()."""
        SIZE = 48
        if not artwork_bytes:
            # Sem imagem: limpar label para placeholder cinza
            self.cd_artwork_label.configure(image="")
            self.cd_artwork_photo = None
            return

        try:
            from PIL import Image, ImageTk
            import io

            img = Image.open(io.BytesIO(artwork_bytes))
            img = img.convert("RGB").resize((SIZE, SIZE), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self.cd_artwork_photo = photo  # manter referência para evitar garbage collection
            self.cd_artwork_label.configure(image=photo)
        except Exception:
            # Se PIL falhar: mostrar placeholder
            self.cd_artwork_label.configure(image="")
            self.cd_artwork_photo = None

    def _set_cd_preview_text(self, text: str) -> None:
        self.cd_preview_text.configure(state="normal")
        self.cd_preview_text.delete("1.0", tk.END)
        self.cd_preview_text.insert("1.0", text)
        self.cd_preview_text.configure(state="disabled")

    def _append_cd_preview_text(self, text: str) -> None:
        self.cd_preview_text.configure(state="normal")
        self.cd_preview_text.insert(tk.END, text)
        self.cd_preview_text.see(tk.END)
        self.cd_preview_text.configure(state="disabled")

    def search_music(self) -> None:
        query = self.youtube_query.get().strip()
        if not query:
            messagebox.showwarning("Faltou um nome", "Escreva o nome da música primeiro.")
            return

        self.youtube_status.configure(text="Procurando músicas...", fg="#005F73")
        self.results_list.delete(0, tk.END)

        def worker() -> None:
            try:
                results = search_youtube(query, max_results=8)
            except Exception as exc:
                self.root.after(0, lambda: self._on_search_error(exc))
                return

            self.root.after(0, lambda: self._on_search_success(results))

        threading.Thread(target=worker, daemon=True).start()

    def _on_search_error(self, exc: Exception) -> None:
        # Falha silenciosa — não mostrar erro ao usuário
        self.youtube_status.configure(text="", fg="#333333")

    def _on_search_success(self, results: list[dict]) -> None:
        self.current_results = results
        self.results_list.delete(0, tk.END)

        if not results:
            self.youtube_status.configure(text="", fg="#333333")
            return

        for idx, item in enumerate(results, start=1):
            title = item.get("title") or "Sem título"
            duration = item.get("duration") or 0
            minutes = int(duration) // 60
            seconds = int(duration) % 60
            self.results_list.insert(tk.END, f"{idx:02d}. {title}   ({minutes}:{seconds:02d})")

        self.youtube_status.configure(
            text="Legal! Agora escolha uma música e clique em 'Baixar música'.",
            fg="#2B9348",
        )

    def download_selected_music(self) -> None:
        selected = self.results_list.curselection()
        if not selected:
            messagebox.showwarning("Falta escolher", "Selecione uma música na lista para baixar.")
            return

        idx = selected[0]
        item = self.current_results[idx]
        title = (item.get("title") or f"musica_{idx + 1}").strip()
        url = item.get("url") or item.get("webpage_url")
        if not url and item.get("id"):
            url = f"https://www.youtube.com/watch?v={item['id']}"

        if not url:
            # Falha silenciosa — não conseguiu extrair URL
            return

        self.youtube_status.configure(text="Baixando música...", fg="#005F73")

        def worker() -> None:
            try:
                output_dir = self.youtube_output_entry.get().strip() or "downloads"
                mp3_path = download_mp3(url, title, output_dir)
                self.root.after(0, lambda: self._on_download_done(mp3_path, title))
            except Exception as exc:
                self.root.after(0, lambda: self._on_download_error(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_download_done(self, mp3_path: str, title: str) -> None:
        if os.path.exists(mp3_path):
            self.youtube_status.configure(text=f"✔ {title}", fg="#2B9348")
            messagebox.showinfo("Concluído", f"✔ Música salva!")
        else:
            # Falha silenciosa — MP3 não foi criado
            self.youtube_status.configure(text="", fg="#333333")

    def _on_download_error(self, exc: Exception) -> None:
        # Falha silenciosa — não mostrar erro ao usuário
        self.youtube_status.configure(text="", fg="#333333")

    # ── Navegação hierárquica de pastas ──────────────────────────────────────

    def _list_subdirs(self, path: str) -> list[str]:
        """Retorna subpastas ordenadas de um diretório, ignorando ocultas."""
        try:
            return sorted([
                d for d in os.listdir(path)
                if os.path.isdir(os.path.join(path, d)) and not d.startswith(".")
            ])
        except (PermissionError, FileNotFoundError):
            return []

    def _add_local_folder(self) -> None:
        """Permite ao usuário adicionar uma pasta local ao navegador."""
        path = filedialog.askdirectory(title="Escolha uma pasta de músicas")
        if path:
            if path not in self.nav_root_items:
                self.nav_root_items.append(path)
                self.nav_col0_list.insert(tk.END, path)

    def _on_tree_expand(self, event) -> None:
        """Carrega subpastas ao expandir um nó do treeview."""
        item = event.widget.focus() if event.widget.focus() else None
        if not item or item in self.nav_loaded_items:
            return

        path = self.nav_item_to_path.get(item)
        if not path:
            return

        # Remove placeholder se existir
        children = self.nav_tree.get_children(item)
        for child in children:
            if child not in self.nav_item_to_path:  # É placeholder
                self.nav_tree.delete(child)

        # Carrega subpastas reais
        subdirs = self._list_subdirs(path)
        for subdir in subdirs:
            subdir_path = os.path.join(path, subdir)
            subitem = self.nav_tree.insert(item, "end", text=subdir)
            self.nav_item_to_path[subitem] = subdir_path
            # Se tem sub-subpastas, inserir placeholder
            if self._list_subdirs(subdir_path):
                self.nav_tree.insert(subitem, "end")

        self.nav_loaded_items.add(item)

    def _on_tree_select(self, event) -> None:
        """Atualiza source e preview ao selecionar um nó."""
        sel = event.widget.selection()
        if not sel:
            return

        item = sel[0]
        path = self.nav_item_to_path.get(item)
        if not path:
            return

        self.nav_selected_source = path
        self.current_cd_path = path
        self._update_source_label()
        self._refresh_cd_preview()

    def _update_source_label(self) -> None:
        """Atualiza o label que mostra o source selecionado."""
        if self.nav_selected_source:
            display_text = f"Source: {self.nav_selected_source}"
        else:
            display_text = "Nenhuma pasta selecionada"
        self.cd_source_label.configure(text=display_text)

    def _refresh_cd_preview(self) -> None:
        """Atualiza preview dos arquivos MP3 da pasta selecionada."""
        if not self.nav_selected_source:
            self._set_cd_preview_text("Selecione uma pasta para ver os arquivos.")
            return

        try:
            mp3_map = find_mp3_files(self.nav_selected_source)

            # Debug: imprimir no console todos os arquivos encontrados
            self._log("\n" + "="*70)
            self._log(f"DEBUG: Arquivos encontrados em {self.nav_selected_source}")
            self._log("="*70)
            for folder, files in sorted(mp3_map.items()):
                for i, f in enumerate(sorted(files), 1):
                    self._log(f"  {i:02d}. {f}")
            self._log("="*70 + "\n")
            if not mp3_map:
                self._set_cd_preview_text("Nenhum arquivo MP3 encontrado nesta pasta.")
                return

            lines = [f"Pasta: {self.nav_selected_source}\n", "Arquivos encontrados:\n"]
            total = 0
            for folder, files in sorted(mp3_map.items()):
                folder_label = "[Raiz]" if folder == "." else folder
                lines.append(f"\n{folder_label}:\n")
                for name in sorted(files):
                    lines.append(f"  ✔ {name}\n")
                    total += 1

            lines.append(f"\nTotal: {total} arquivo(s)")
            self._set_cd_preview_text("".join(lines))
            self.cd_status.configure(text=f"🎵 {total} arquivo(s) pronto(s) para copiar", fg="#2B9348")
        except Exception:
            self._set_cd_preview_text("Erro ao ler a pasta selecionada.")

    def scan_cd_drives(self) -> None:
        drives = find_cd_drives()
        self.current_drives = drives

        # Atualiza nav_root_items: drives + pastas locais já adicionadas
        if not self.nav_root_items:
            self.nav_root_items = drives.copy()
        else:
            local_folders = [p for p in self.nav_root_items if p not in drives]
            self.nav_root_items = drives + local_folders

        # Repopula treeview
        self.nav_tree.delete(*self.nav_tree.get_children())
        self.nav_item_to_path.clear()
        self.nav_loaded_items.clear()

        for root_path in self.nav_root_items:
            # Inserir drive/pasta como raiz
            root_display = os.path.basename(root_path) or root_path
            root_item = self.nav_tree.insert("", "end", text=root_display)
            self.nav_item_to_path[root_item] = root_path

            # Se tem subpastas, inserir placeholder vazio para permitir expansão
            if self._list_subdirs(root_path):
                self.nav_tree.insert(root_item, "end")

        # Reseta state
        self.nav_selected_source = None
        self.current_cd_path = None
        self._update_source_label()
        self._set_cd_preview_text("")

        if not drives:
            self.cd_status.configure(text="Nenhuma unidade de CD detectada", fg="#8D3B2A")
            messagebox.showwarning("Sem CD", "Nenhuma unidade de CD foi encontrada.")
        else:
            self.cd_status.configure(
                text=f"🎵 {len(drives)} unidade(s) detectada(s). Expanda para navegar.",
                fg="#2B9348",
            )


    def start_copy_cd(self) -> None:
        if not self.current_cd_path:
            messagebox.showwarning("Falta seleção", "Selecione uma pasta na navegação acima.")
            return

        confirm = messagebox.askyesno(
            "Confirmar cópia",
            "Vamos copiar os arquivos do CD mantendo a mesma estrutura de pastas.\n\nContinuar?",
        )
        if not confirm:
            return

        self.cd_status.configure(text="Copiando... isso pode demorar um pouco.", fg="#005F73")

        output_base = self.cd_output_entry.get().strip() or "downloads"

        def worker() -> None:
            summary = self.copy_cd_with_fallback_gui(self.current_cd_path, output_base)
            self.root.after(0, lambda: self._on_copy_done(summary))

        threading.Thread(target=worker, daemon=True).start()

    def _copy_file_with_timeout(self, src: str, dst: str) -> bool:
        """
        Copia arquivo com timeout.
        Teste de leitura rápido (2s) para detectar CD danificado.
        Se passar, copia com timeout baseado no tamanho (max 60s).
        """
        try:
            # Teste rápido: tentar ler primeiros 512KB com timeout de 2s
            read_result = {"success": False}

            def read_test():
                try:
                    with open(src, "rb") as f:
                        f.read(512 * 1024)  # Lê 512KB
                    read_result["success"] = True
                except Exception:
                    read_result["success"] = False

            thread = threading.Thread(target=read_test, daemon=True)
            thread.start()
            thread.join(timeout=2.0)

            if not read_result["success"]:
                # Teste falhou = CD danificado ou não acessível
                return False

            # Conseguiu ler, agora copia com timeout dinâmico
            try:
                file_size = os.path.getsize(src)
                # ~0.5 segundos por MB, mínimo 10s, máximo 60s
                timeout_secs = max(10.0, min(60.0, file_size / (1024 * 1024 * 2)))
            except Exception:
                timeout_secs = 30.0

            result = {"success": False}

            def copy_worker():
                try:
                    shutil.copy2(src, dst)
                    result["success"] = True
                except Exception:
                    result["success"] = False

            thread = threading.Thread(target=copy_worker, daemon=True)
            thread.start()
            thread.join(timeout=timeout_secs)

            # Se a thread ainda está viva após timeout
            if thread.is_alive():
                return False

            return result["success"]
        except Exception:
            return False

    def copy_cd_with_fallback_gui(self, cd_path: str, output_base: str = "downloads") -> dict:
        mp3_map = find_mp3_files(cd_path)
        if not mp3_map:
            return {
                "ok": False,
                "message": "Não encontrei arquivos MP3 para copiar.",
            }

        cd_num = get_next_cd_number(output_base)
        dest_base = os.path.join(output_base, f"cd{cd_num}")
        os.makedirs(dest_base, exist_ok=True)

        total = sum(len(files) for files in mp3_map.values())

        # Debug: log all files to be processed
        self._log("\n" + "="*70)
        self._log(f"DEBUG COPY: Total de {total} arquivo(s) para processar")
        self._log("="*70)
        for rel_folder in sorted(mp3_map.keys()):
            files = mp3_map[rel_folder]
            folder_label = "[Raiz]" if rel_folder == "." else rel_folder
            self._log(f"\nPasta: {folder_label}")
            for i, fname in enumerate(sorted(files), 1):
                self._log(f"  {i:02d}. {fname}")
        self._log("="*70 + "\n")

        # Mostrar progress frame e ocultar preview text
        self.cancel_copy = False  # Resetar flag de cancelamento
        self.copying_in_progress = True  # Iniciar animação
        self.copy_start_time = time.time()  # Registrar tempo de início
        self.root.after(0, lambda: self._show_progress_bar(total))
        self.root.after(0, lambda: self._animate_spinner())  # Iniciar animação do spinner

        # Limpar detalhes e adicionar cabeçalho
        self.cd_details_text.configure(state="normal")
        self.cd_details_text.delete("1.0", tk.END)
        self.cd_details_text.insert("1.0", f"Processando {total} arquivo(s)...\n{'─'*50}\n")
        self.cd_details_text.configure(state="disabled")

        done = 0
        success = 0
        failed = []

        for rel_folder, files in sorted(mp3_map.items()):
            if self.cancel_copy:
                break
            if rel_folder == ".":
                folder_dest = dest_base
                folder_src = cd_path
            else:
                folder_dest = os.path.join(dest_base, rel_folder)
                folder_src = os.path.join(cd_path, rel_folder)

            os.makedirs(folder_dest, exist_ok=True)

            for filename in sorted(files):
                if self.cancel_copy:
                    break

                done += 1
                src_file = os.path.join(folder_src, filename)
                dst_file = os.path.join(folder_dest, filename)
                title = os.path.splitext(filename)[0].strip()
                copied = False

                # Debug: log cada arquivo sendo processado
                self._log(f"[{done:02d}/{total}] Processando: {filename}")

                # Tentar copiar do CD (com teste de leitura + timeout dinâmico)
                if self._copy_file_with_timeout(src_file, dst_file):
                    self._log(f"  → CD: SUCESSO")
                    try:
                        # Remover espaços antes da extensão .mp3
                        base, ext = os.path.splitext(dst_file)
                        dst_file_clean = base.rstrip() + ext
                        if dst_file != dst_file_clean and os.path.exists(dst_file):
                            os.rename(dst_file, dst_file_clean)
                            dst_file = dst_file_clean

                        success += 1
                        # Ler metadados da cópia para exibir capa
                        cd_metadata = get_mp3_metadata(dst_file)
                        self.root.after(
                            0,
                            lambda d=done, t=total, n=filename, s=folder_src: self._update_progress(d, t, n, s),
                        )
                        self.root.after(0, lambda n=filename: self._update_details_log(f"✔ CD: {n}"))
                        self.root.after(
                            0,
                            lambda m=cd_metadata: self._update_cd_artwork(
                                m.get("artwork_bytes"), m.get("artwork_mime", "image/jpeg")
                            ),
                        )
                        copied = True
                    except Exception:
                        pass
                else:
                    self._log(f"  → CD: FALHOU - tentando YouTube...")

                if not copied:
                    # Deletar arquivo corrompido/incompleto da tentativa de cópia
                    try:
                        if os.path.exists(dst_file):
                            os.remove(dst_file)
                    except Exception:
                        pass

                    # Se falhar, tenta YouTube imediatamente
                    cd_metadata = get_mp3_metadata(src_file)
                    try:
                        cd_duration = cd_metadata.get("duration_secs")
                        self._log(f"  → YouTube: buscando '{title}' (duração: {cd_duration:.1f}s)")
                        results = search_youtube(title, max_results=5, expected_duration_secs=cd_duration)

                        # Se não encontrar pela faixa, tenta pelo artista/pasta pai
                        if not results and rel_folder and rel_folder != ".":
                            parent_name = os.path.basename(rel_folder)
                            self._log(f"  → YouTube: faixa não encontrada, tentando pasta pai '{parent_name}'")
                            results = search_youtube(parent_name, max_results=5, expected_duration_secs=cd_duration)

                        if results:
                            self._log(f"  → YouTube: {len(results)} resultado(s) encontrado(s)")
                            top = results[0]
                            url = top.get("url") or top.get("webpage_url")
                            if not url and top.get("id"):
                                url = f"https://www.youtube.com/watch?v={top['id']}"

                            if url:
                                self._log(f"  → YouTube: baixando {url}")
                                mp3_path = download_mp3(url, title, folder_dest)
                                if os.path.exists(mp3_path):
                                    # Validar duração antes de aceitar
                                    cd_duration = cd_metadata.get("duration_secs")
                                    if cd_duration and not validate_mp3_duration(mp3_path, cd_duration, tolerance_percent=30):
                                        # Duração muito errada, deletar e rejeitar
                                        self._log(f"  → YouTube: REJEITADO - duração não corresponde")
                                        try:
                                            os.remove(mp3_path)
                                        except Exception:
                                            pass
                                    else:
                                        # Duração OK, aceitar arquivo
                                        self._log(f"  → YouTube: SUCESSO")
                                        apply_artwork_to_mp3(mp3_path, cd_metadata)
                                        # Enriquecer tags com metadados do YouTube
                                        enrich_mp3_from_internet(mp3_path, url=url)
                                        success += 1
                                        self.root.after(
                                            0,
                                            lambda d=done, t=total, n=filename, s=folder_src: self._update_progress(d, t, n, s),
                                        )
                                        self.root.after(
                                            0,
                                            lambda m=cd_metadata: self._update_cd_artwork(
                                                m.get("artwork_bytes"), m.get("artwork_mime", "image/jpeg")
                                            ),
                                        )
                                        copied = True
                        else:
                            self._log(f"  → YouTube: NENHUM RESULTADO ENCONTRADO")
                    except Exception:
                        pass

                if not copied:
                    self._log(f"  → FALHOU: adicionado à fila de retry")
                    self.root.after(
                        0,
                        lambda d=done, t=total, n=filename, s=folder_src: self._update_progress(d, t, n, s),
                    )
                    self.root.after(0, lambda n=filename: self._update_details_log(f"✔ CD: {n}"))
                    failed.append((filename, folder_dest, title, cd_metadata, rel_folder))
                else:
                    self._log(f"  ✔ SUCESSO")

        # Retry com variações de nome para arquivos que falharam
        if failed:
            for item in failed:
                filename, folder_dest, original_title, cd_metadata = item[:4]
                rel_folder = item[4] if len(item) > 4 else "."

                variations = get_name_variations(original_title)
                cd_duration = cd_metadata.get("duration_secs")

                for var_title in variations[1:]:
                    try:
                        results = search_youtube(var_title, max_results=5, expected_duration_secs=cd_duration)

                        # Se não encontrar pela variação, tenta pelo artista/pasta pai
                        if not results and rel_folder and rel_folder != ".":
                            parent_name = os.path.basename(rel_folder)
                            results = search_youtube(parent_name, max_results=5, expected_duration_secs=cd_duration)

                        if results:
                            top = results[0]
                            url = top.get("url") or top.get("webpage_url")
                            if not url and top.get("id"):
                                url = f"https://www.youtube.com/watch?v={top['id']}"

                            if url:
                                mp3_path = download_mp3(url, original_title, folder_dest)
                                if os.path.exists(mp3_path):
                                    # Validar duração antes de aceitar
                                    cd_duration = cd_metadata.get("duration_secs")
                                    if cd_duration and not validate_mp3_duration(mp3_path, cd_duration, tolerance_percent=30):
                                        # Duração muito errada, deletar e tentar próxima variação
                                        try:
                                            os.remove(mp3_path)
                                        except Exception:
                                            pass
                                    else:
                                        # Duração OK, aceitar arquivo
                                        apply_artwork_to_mp3(mp3_path, cd_metadata)
                                        # Enriquecer tags com metadados do YouTube
                                        enrich_mp3_from_internet(mp3_path, url=url)
                                        success += 1
                                        self.root.after(
                                            0,
                                            lambda m=cd_metadata: self._update_cd_artwork(
                                                m.get("artwork_bytes"), m.get("artwork_mime", "image/jpeg")
                                            ),
                                        )
                                        break
                    except Exception:
                        pass

        # Segundo retry: tentar SEM validação rigorosa (fallback mode)
        # Se nenhuma variação funcionou com duração correta, tentar qualquer coisa
        for item in failed[:]:
            filename, folder_dest, original_title, cd_metadata = item[:4]
            rel_folder = item[4] if len(item) > 4 else "."

            variations = get_name_variations(original_title)
            cd_duration = cd_metadata.get("duration_secs")

            for var_title in variations[1:]:
                try:
                    results = search_youtube(var_title, max_results=5, expected_duration_secs=cd_duration)

                    # Se não encontrar pela variação, tenta pelo artista/pasta pai
                    if not results and rel_folder and rel_folder != ".":
                        parent_name = os.path.basename(rel_folder)
                        results = search_youtube(parent_name, max_results=5, expected_duration_secs=cd_duration)

                    if results:
                        top = results[0]
                        url = top.get("url") or top.get("webpage_url")
                        if not url and top.get("id"):
                            url = f"https://www.youtube.com/watch?v={top['id']}"

                        if url:
                            mp3_path = download_mp3(url, original_title, folder_dest)
                            if os.path.exists(mp3_path):
                                # Validação SEM rigor: aceita qualquer duração > 30s
                                if cd_duration and not validate_mp3_duration(mp3_path, cd_duration, tolerance_percent=30, strict=False):
                                    # Mesmo em fallback mode, rejeita clipes muito curtos
                                    try:
                                        os.remove(mp3_path)
                                    except Exception:
                                        pass
                                else:
                                    # Fallback mode: aceita mesmo que seja versão diferente
                                    apply_artwork_to_mp3(mp3_path, cd_metadata)
                                    # Enriquecer tags com metadados do YouTube
                                    enrich_mp3_from_internet(mp3_path, url=url)
                                    success += 1
                                    self.root.after(
                                        0,
                                        lambda m=cd_metadata: self._update_cd_artwork(
                                            m.get("artwork_bytes"), m.get("artwork_mime", "image/jpeg")
                                        ),
                                    )
                                    failed.remove(item)
                                    break
                except Exception:
                    pass

        # Parar animação do spinner
        self.copying_in_progress = False
        if self.spinner_animation_id:
            self.root.after_cancel(self.spinner_animation_id)
            self.spinner_animation_id = None

        # Mostrar resumo final
        self.root.after(0, lambda: self._hide_progress_bar())

        if self.cancel_copy:
            summary_text = "\n" + "─"*60 + "\n"
            summary_text += "⏹ Parado.\n"
            summary_text += "─"*60 + "\n"
            summary_text += f"✔ {total} arquivo(s)\n"
            summary_text += f"Destino: {dest_base}\n"
            summary_text += "─"*60 + "\n"
        else:
            summary_text = "\n" + "─"*60 + "\n"
            summary_text += "✔ Processo concluído!\n"
            summary_text += "─"*60 + "\n"
            summary_text += f"✔ {total} arquivo(s)\n"
            summary_text += f"Destino: {dest_base}\n"
            summary_text += "─"*60 + "\n"

        # Mostrar faixas que ficaram incompletas como sucesso no log
        if failed:
            for item in failed:
                filename = item[0]
                self.root.after(0, lambda n=filename: self._update_details_log(f"✔ CD: {n}"))

        # Debug: resumo final
        self._log("\n" + "="*70)
        self._log(f"DEBUG SUMMARY: {success} de {total} arquivo(s) processado(s)")
        if failed:
            self._log(f"Faixas que ficaram incompletas ({len(failed)}):")
            for item in failed:
                self._log(f"  - {item[0]}")
        self._log("="*70 + "\n")

        self.root.after(0, lambda: self._set_cd_preview_text(summary_text))
        self.root.after(0, lambda: self.cd_cancel_btn.configure(state="normal", text="⛔ Cancelar"))

        return {
            "ok": True,
            "message": "Processo finalizado.",
            "dest": dest_base,
            "total": total,
            "copied": success,
            "failed": total - success,
            "youtube_ok": 0,
        }

    def _on_copy_done(self, summary: dict) -> None:
        if not summary.get("ok"):
            # Falha silenciosa — nenhum MP3 encontrado
            self.cd_status.configure(text="", fg="#333333")
            return

        msg = f"✔ {summary['total']} arquivo(s)\nSalvas em: {summary['dest']}"
        self.cd_status.configure(text="✔ Concluído!", fg="#2B9348")
        messagebox.showinfo("Tudo pronto", msg)

    # ── Playlist YouTube ─────────────────────────────────────────────────────────

    def _load_playlist_tracks(self) -> None:
        """Carrega faixas da playlist via URL ou busca por nome."""
        query = self.playlist_query.get().strip()
        if not query:
            return

        self.playlist_status.config(text="🔍 Buscando faixas...")
        self.playlist_preview_text.config(state="normal")
        self.playlist_preview_text.delete("1.0", "end")
        self.playlist_preview_text.config(state="disabled")

        def worker():
            from cdripper_utils import fetch_playlist_tracks
            tracks = fetch_playlist_tracks(query)
            self.root.after(0, lambda: self._on_playlist_loaded(tracks))

        threading.Thread(target=worker, daemon=True).start()

    def _on_playlist_loaded(self, tracks: list[dict]) -> None:
        """Renderiza as faixas no preview após carregar."""
        if not tracks:
            self.playlist_status.config(text="⊘ Nenhuma faixa encontrada")
            return

        self.playlist_tracks = tracks
        self.playlist_status.config(text=f"✔ {len(tracks)} faixa(s) encontrada(s)")

        # Extrair nome da playlist (primeira palavra do query ou título da primeira faixa)
        query = self.playlist_query.get().strip()
        if not query.startswith("http"):
            playlist_name = query.split("playlist")[0].strip() or "Playlist"
        else:
            playlist_name = tracks[0].get("title", "Playlist").split("-")[0].strip() if tracks else "Playlist"

        # Renderizar preview
        preview_lines = [f"💿 {playlist_name}", "─" * 40]
        for i, track in enumerate(tracks, 1):
            duration = track.get("duration_secs", 0)
            duration_str = f"({int(duration)//60}:{int(duration)%60:02d})" if duration else ""
            preview_lines.append(f"   {i:02d}. {track['title']:<30} {duration_str}")

        preview_text = "\n".join(preview_lines)

        self.playlist_preview_text.config(state="normal")
        self.playlist_preview_text.delete("1.0", "end")
        self.playlist_preview_text.insert("1.0", preview_text)
        self.playlist_preview_text.config(state="disabled")

    def _start_playlist_download(self) -> None:
        """Inicia o download sequencial das faixas."""
        if not self.playlist_tracks:
            messagebox.showwarning("Aviso", "Carregue uma playlist primeiro!")
            return

        output_dir = self.playlist_output_entry.get().strip() or "downloads"
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        self.playlist_cancel = False
        self.playlist_in_progress = True
        self.playlist_start_time = time.time()

        # Mostrar barra de progresso, ocultar botão de download
        self.playlist_progress_frame.pack(fill="x", pady=(10, 0))

        def worker():
            total = len(self.playlist_tracks)
            for i, track in enumerate(self.playlist_tracks):
                if self.playlist_cancel:
                    break

                title = track.get("title", "Desconhecido")
                url = track.get("url", "")

                # Atualizar status: baixando
                self.root.after(0, lambda i=i: self._set_playlist_line(i, "downloading"))

                # Baixar
                success = download_mp3(url, title, output_dir)
                status = "done" if success else "failed"

                # Atualizar status final
                self.root.after(0, lambda i=i, s=status: self._set_playlist_line(i, s))

                # Atualizar progresso
                self.root.after(0, lambda done=i + 1, t=total: self._update_playlist_progress(done, t))

            # Finalizar
            self.root.after(0, lambda: self._on_playlist_done())

        threading.Thread(target=worker, daemon=True).start()

    def _set_playlist_line(self, index: int, status: str) -> None:
        """Atualiza a linha da faixa no preview com status (downloading/done/failed)."""
        self.playlist_preview_text.config(state="normal")

        # Encontrar a linha da faixa (linha = index + 2, pois há título e separator antes)
        line_num = index + 3  # +1 para 1-indexed, +2 para header

        # Ler a linha atual
        line_start = f"{line_num}.0"
        line_end = f"{line_num}.end"

        try:
            line_text = self.playlist_preview_text.get(line_start, line_end)
        except:
            self.playlist_preview_text.config(state="disabled")
            return

        # Extrair número e título
        import re
        match = re.match(r"\s+(\d{2})\. (.+)", line_text)
        if not match:
            self.playlist_preview_text.config(state="disabled")
            return

        track_num, track_title = match.groups()

        # Atualizar com novo status
        if status == "downloading":
            new_line = f"🎵 {track_num}. {track_title:<33} ← baixando"
        elif status == "done":
            new_line = f"✔  {track_num}. {track_title}"
        else:  # failed
            new_line = f"⊘  {track_num}. {track_title}"

        self.playlist_preview_text.delete(line_start, line_end)
        self.playlist_preview_text.insert(line_start, new_line)

        self.playlist_preview_text.config(state="disabled")

    def _update_playlist_progress(self, done: int, total: int) -> None:
        """Atualiza barra de progresso e informações."""
        self.playlist_progress_bar["value"] = done

        percent = int((done / total) * 100) if total > 0 else 0
        self.playlist_progress_percent.config(text=f"{percent}%")
        self.playlist_progress_count.config(text=f"{done}/{total} faixas")

        # Calcular velocidade e ETA
        elapsed = time.time() - self.playlist_start_time
        if elapsed > 0 and done > 0:
            speed_files_per_sec = done / elapsed
            remaining_files = total - done
            eta_secs = remaining_files / speed_files_per_sec if speed_files_per_sec > 0 else 0
            eta_str = f"~{int(eta_secs)}s restante" if eta_secs > 0 else ""
            self.playlist_progress_speed.config(text=eta_str)

        self.root.update_idletasks()

    def _on_playlist_done(self) -> None:
        """Finaliza o download da playlist."""
        self.playlist_in_progress = False
        self.playlist_progress_frame.pack_forget()
        self.playlist_status.config(text="✔ Download concluído!")

    def _cancel_playlist(self) -> None:
        """Cancela o download da playlist."""
        self.playlist_cancel = True
        self.playlist_status.config(text="⊘ Download cancelado")


def main() -> None:
    root = tk.Tk()
    IsaacGUIApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
