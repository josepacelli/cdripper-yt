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

try:
    import tkinter as tk
    from tkinter import messagebox, ttk
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
    find_cd_drives,
    find_mp3_files,
    get_mp3_metadata,
    get_next_cd_number,
    search_youtube,
    get_name_variations,

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
    """Barra de progresso estilo Windows 7 com efeito visual."""
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
        self.root = root
        self.root.title("Isaac Music - Modo Infantil")
        self.root.geometry("1080x760")
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

        self._build_styles()
        self._build_header()
        self._build_tabs()

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

        notebook.add(self.youtube_tab, text="📺 YouTube")
        notebook.add(self.cd_tab, text="💿 Copiar CD")

        self._build_youtube_tab()
        self._build_cd_tab()

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

        top_row = tk.Frame(container, bg="#F6FBFF")
        top_row.pack(fill="x")

        tk.Label(
            top_row,
            text="1) Encontre seu CD",
            font=self.section_font,
            bg="#F6FBFF",
            fg="#6B4E16",
        ).pack(side="left")

        scan_btn = tk.Button(
            top_row,
            text="💿 Procurar CD",
            font=self.big_btn_font,
            bg="#FFB703",
            fg="#4A2D00",
            activebackground="#F4A261",
            padx=20,
            pady=8,
            command=self.scan_cd_drives,
        )
        scan_btn.pack(side="right")

        drives_row = tk.Frame(container, bg="#F6FBFF")
        drives_row.pack(fill="both", pady=(8, 12))

        self.drives_list = tk.Listbox(
            drives_row,
            font=("Arial", 14),
            height=4,
            activestyle="none",
            selectbackground="#FFE8A3",
            selectforeground="#523200",
        )
        self.drives_list.pack(fill="x")

        preview_row = tk.Frame(container, bg="#F6FBFF")
        preview_row.pack(fill="x", pady=(0, 8))

        preview_btn = tk.Button(
            preview_row,
            text="👀 Mostrar músicas do CD",
            font=self.big_btn_font,
            bg="#8ECAE6",
            fg="#09324C",
            activebackground="#74B7D6",
            padx=20,
            pady=8,
            command=self.preview_cd,
        )
        preview_btn.pack(side="left")

        # Input para pasta de destino
        path_frame = tk.Frame(preview_row, bg="#F6FBFF")
        path_frame.pack(side="right", fill="x", expand=False, padx=(10, 0))

        tk.Label(
            path_frame,
            text="Pasta:",
            font=("Arial", 12, "bold"),
            bg="#F6FBFF",
            fg="#264653",
        ).pack(side="left", padx=(0, 8))

        self.cd_output_entry = tk.Entry(
            path_frame,
            font=("Arial", 12),
            bg="white",
            fg="#333333",
            width=20,
        )
        self.cd_output_entry.pack(side="left")
        self.cd_output_entry.insert(0, "downloads")
        # Atualizar label quando o usuário digita
        self.cd_output_entry.bind("<KeyRelease>", lambda e: self._update_cd_target_label())

        self.cd_target_label = tk.Label(
            preview_row,
            text="",
            font=("Arial", 13, "bold"),
            bg="#F6FBFF",
            fg="#264653",
        )
        self.cd_target_label.pack(side="right", padx=(10, 0))

        # Inicializar label com o valor padrão
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
            height=14,
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

        # Frame horizontal: imagem à esquerda + nome do arquivo à direita
        artwork_row = tk.Frame(self.cd_progress_frame, bg="#F6FBFF")
        artwork_row.pack(fill="x", pady=(0, 8))

        # Label para capa de álbum (80x80, placeholder cinza)
        self.cd_artwork_label = tk.Label(
            artwork_row,
            bg="#E8E8E8",
            width=10,
            height=4,
            relief="flat",
        )
        self.cd_artwork_label.pack(side="left", padx=(0, 12))
        self.cd_artwork_photo = None  # Referência para evitar garbage collection

        # Nome do arquivo à direita
        self.cd_current_file_label = tk.Label(
            artwork_row,
            text="",
            font=("Arial", 14, "bold"),
            bg="#F6FBFF",
            fg="#333333",
            anchor="w",
            justify="left",
        )
        self.cd_current_file_label.pack(side="left", fill="x", expand=True)

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
            text="Quando algum arquivo falhar, vamos tentar no YouTube automaticamente.",
            font=("Arial", 12, "bold"),
            bg="#F6FBFF",
            fg="#8D3B2A",
        )
        self.cd_status.pack(side="left")

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
        self.cd_progress_percent.configure(text="0%")
        self.cd_progress_count.configure(text=f"0/{total} arquivos")
        self._update_cd_artwork(None)  # Limpar imagem para placeholder

    def _hide_progress_bar(self) -> None:
        """Oculta a barra de progresso e mostra o preview text."""
        self.cd_progress_bar.stop_animation()  # Parar animação da barra
        self._update_cd_artwork(None)  # Limpar imagem
        self.cd_progress_frame.pack_forget()
        self.cd_preview_text.pack(fill="both", expand=True)

    def _update_progress(self, done: int, total: int, filename: str = "") -> None:
        """Atualiza a barra de progresso com velocidade e ETA."""
        pct = int((done / total * 100)) if total > 0 else 0
        self.cd_progress_bar["value"] = done

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
        SIZE = 80
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
        self.youtube_status.configure(text="Não consegui buscar agora.", fg="#B00020")
        messagebox.showerror("Erro na busca", f"Não foi possível buscar no YouTube.\n\nDetalhe: {exc}")

    def _on_search_success(self, results: list[dict]) -> None:
        self.current_results = results
        self.results_list.delete(0, tk.END)

        if not results:
            self.youtube_status.configure(text="Não encontrei músicas com esse nome.", fg="#B00020")
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
        title = item.get("title") or f"musica_{idx + 1}"
        url = item.get("url") or item.get("webpage_url")
        if not url and item.get("id"):
            url = f"https://www.youtube.com/watch?v={item['id']}"

        if not url:
            messagebox.showerror("Erro", "Não encontrei o link desse vídeo.")
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
            self.youtube_status.configure(text=f"Concluído: {title}", fg="#2B9348")
            messagebox.showinfo("Concluído", f"Música salva em:\n{mp3_path}")
        else:
            self.youtube_status.configure(
                text="Download terminou, mas o MP3 não apareceu.",
                fg="#B26A00",
            )
            messagebox.showwarning(
                "Atenção",
                "Não achei o MP3 final. Verifique se o ffmpeg está instalado.",
            )

    def _on_download_error(self, exc: Exception) -> None:
        self.youtube_status.configure(text="Não consegui baixar essa música.", fg="#B00020")
        messagebox.showerror("Erro no download", f"Falha ao baixar:\n{exc}")

    def scan_cd_drives(self) -> None:
        drives = find_cd_drives()
        self.current_drives = drives
        self.drives_list.delete(0, tk.END)

        if not drives:
            self.cd_status.configure(text="Não encontrei unidade de CD agora.", fg="#B00020")
            messagebox.showwarning("Sem CD", "Nenhuma unidade de CD foi encontrada.")
            return

        for drive in drives:
            self.drives_list.insert(tk.END, drive)

        self.cd_status.configure(
            text="Agora selecione a unidade e clique em 'Mostrar músicas do CD'.",
            fg="#8D3B2A",
        )

    def preview_cd(self) -> None:
        selected = self.drives_list.curselection()
        if not selected:
            messagebox.showwarning("Escolha uma unidade", "Selecione uma unidade de CD na lista.")
            return

        drive_path = self.current_drives[selected[0]]
        self.current_cd_path = drive_path

        mp3_map = find_mp3_files(drive_path)
        if not mp3_map:
            self._set_cd_preview_text("Não encontrei arquivos MP3 nesse CD.\n")
            self.cd_status.configure(text="Esse CD não tem arquivos MP3.", fg="#B00020")
            return

        lines = [f"CD selecionado: {drive_path}\n", "Arquivos encontrados:\n"]
        total = 0
        for folder, files in sorted(mp3_map.items()):
            folder_label = "[Raiz]" if folder == "." else folder
            lines.append(f"\nPasta: {folder_label}\n")
            for name in sorted(files):
                lines.append(f"  - {name}\n")
                total += 1

        lines.append(f"\nTotal: {total} arquivo(s) MP3\n")
        lines.append("\nSe tudo estiver certo, clique em 'Copiar para downloads/cdX'.\n")

        self._set_cd_preview_text("".join(lines))
        self.cd_status.configure(text="Prévia pronta. Pode iniciar a cópia.", fg="#2B9348")

    def start_copy_cd(self) -> None:
        if not self.current_cd_path:
            messagebox.showwarning("Falta prévia", "Primeiro clique em 'Mostrar músicas do CD'.")
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
                title = os.path.splitext(filename)[0]
                copied = False

                # Tentar copiar do CD
                try:
                    shutil.copy2(src_file, dst_file)
                    success += 1
                    # Ler metadados da cópia para exibir capa
                    cd_metadata = get_mp3_metadata(dst_file)
                    self.root.after(
                        0,
                        lambda d=done, t=total, n=filename: self._update_progress(d, t, n),
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
                    # Se falhar, tenta YouTube imediatamente
                    cd_metadata = get_mp3_metadata(src_file)
                    try:
                        cd_duration = cd_metadata.get("duration_secs")
                        results = search_youtube(title, max_results=5, expected_duration_secs=cd_duration)
                        if results:
                            top = results[0]
                            url = top.get("url") or top.get("webpage_url")
                            if not url and top.get("id"):
                                url = f"https://www.youtube.com/watch?v={top['id']}"

                            if url:
                                mp3_path = download_mp3(url, title, folder_dest)
                                if os.path.exists(mp3_path):
                                    apply_artwork_to_mp3(mp3_path, cd_metadata)
                                    success += 1
                                    self.root.after(
                                        0,
                                        lambda d=done, t=total, n=filename: self._update_progress(d, t, n),
                                    )
                                    self.root.after(0, lambda n=filename: self._update_details_log(f"🎵 YouTube: {n}"))
                                    self.root.after(
                                        0,
                                        lambda m=cd_metadata: self._update_cd_artwork(
                                            m.get("artwork_bytes"), m.get("artwork_mime", "image/jpeg")
                                        ),
                                    )
                                    copied = True
                    except Exception:
                        pass

                if not copied:
                    self.root.after(
                        0,
                        lambda d=done, t=total, n=filename: self._update_progress(d, t, n),
                    )
                    self.root.after(0, lambda n=filename: self._update_details_log(f"⊘ Falhou: {n}"))
                    failed.append((filename, folder_dest, title, cd_metadata))

        # Retry com variações de nome para arquivos que falharam
        if failed:
            for filename, folder_dest, original_title, cd_metadata in failed:
                variations = get_name_variations(original_title)
                cd_duration = cd_metadata.get("duration_secs")

                for var_title in variations[1:]:
                    try:
                        results = search_youtube(var_title, max_results=5, expected_duration_secs=cd_duration)
                        if results:
                            top = results[0]
                            url = top.get("url") or top.get("webpage_url")
                            if not url and top.get("id"):
                                url = f"https://www.youtube.com/watch?v={top['id']}"

                            if url:
                                mp3_path = download_mp3(url, filename, folder_dest)
                                if os.path.exists(mp3_path):
                                    apply_artwork_to_mp3(mp3_path, cd_metadata)
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

        # Parar animação do spinner
        self.copying_in_progress = False
        if self.spinner_animation_id:
            self.root.after_cancel(self.spinner_animation_id)
            self.spinner_animation_id = None

        # Mostrar resumo final
        self.root.after(0, lambda: self._hide_progress_bar())

        if self.cancel_copy:
            summary_text = f"\n{'─'*60}\n"
            summary_text += f"⏹ Cópia Cancelada!\n"
            summary_text += f"{'─'*60}\n"
            summary_text += f"✔ Sucesso: {success}/{done} arquivos processados\n"
            summary_text += f"⚠ Não processados: {total - done}/{total} arquivos\n"
            summary_text += f"Destino: {dest_base}\n"
            summary_text += f"{'─'*60}\n"
        else:
            summary_text = f"\n{'─'*60}\n"
            summary_text += f"Processamento Concluído!\n"
            summary_text += f"{'─'*60}\n"
            summary_text += f"✔ Sucesso: {success}/{total} arquivos\n"
            summary_text += f"⊘ Não obtidos: {total - success}/{total} arquivos\n"
            summary_text += f"Destino: {dest_base}\n"
            summary_text += f"{'─'*60}\n"

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
            self.cd_status.configure(text=summary.get("message", "Falha na cópia."), fg="#B00020")
            messagebox.showerror("Falha", summary.get("message", "Falha na cópia."))
            return

        msg = (
            f"Destino: {summary['dest']}\n"
            f"Copiados do CD: {summary['copied']}/{summary['total']}\n"
            f"Falhas na cópia: {summary['failed']}\n"
            f"Recuperados no YouTube: {summary['youtube_ok']}"
        )
        self.cd_status.configure(text="Cópia concluída com sucesso!", fg="#2B9348")
        self._append_cd_preview_text("\n" + "-" * 60 + "\nConcluído!\n")
        messagebox.showinfo("Tudo pronto", msg)


def main() -> None:
    root = tk.Tk()
    IsaacGUIApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
