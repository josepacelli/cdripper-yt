# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**cdripper-yt** is a multi-platform music downloader with dual functionality:
- Download MP3s from YouTube
- Copy MP3s from physical CDs to local storage with automatic YouTube fallback (if CD read fails)
- Download videos from YouTube as MP4 with real-time progress tracking
- Download entire YouTube playlists as MP3s

The project provides both CLI and GUI interfaces, and can be compiled to native executables for Windows, macOS, and Linux.

### Purpose & Accessibility

This application is specifically designed for **autistic children and individuals with neurological differences** who experience anxiety or distress from error messages and technical jargon. Key design considerations:

- **Friendly, Non-Alarming Error Handling**: Error messages are removed or silent; failures are handled gracefully without alarming users
- **Visual-Friendly Design**: Large buttons, bright colors, and clear visual hierarchy to reduce cognitive load
- **Immediate Recovery**: When copying a file from CD fails, the application immediately attempts to download it from YouTube without exposing error states
- **Sensory-Conscious**: Colorful, child-friendly GUI (Isaac Music) with supportive feedback using emoji (✔, 🎵, ⊘) instead of technical language
- **Silent Failure Handling**: Errors are caught and handled internally; users see progress with simple visual indicators

## Architecture

### Core Modules

**cdripper_utils.py** — Shared utility module used by both CLI and GUI:
- **YouTube Operations**:
  - `search_youtube(query, max_results, expected_duration_secs)` — Search YouTube videos
  - `download_mp3(url, title, output_dir)` — Download and convert to MP3 (with FFmpeg)
  - `download_mp4(url, title, output_dir, progress_hook)` — Download video as MP4 (supports progress callbacks)
  - `get_name_variations(title)` — Generate search variations for retry logic
  - `enrich_mp3_from_internet(mp3_path, url)` — Add metadata and artwork to MP3 files from YouTube
  - `apply_artwork_to_mp3(mp3_path, metadata)` — Embed album art into MP3 ID3 tags
- **CD Operations**:
  - `find_cd_drives()` — Detect CD/DVD drives (platform-specific)
  - `find_mp3_files(directory)` — Recursively find MP3 files, grouped by folder
- **Metadata & Utilities**:
  - `get_mp3_metadata(path)` — Extract duration and artwork from MP3 files
  - `sanitize_filename(name)` — Remove unsafe characters from filenames
  - `fetch_playlist_tracks(query)` — Extract tracks from YouTube playlists
  - `validate_mp3_duration(path, expected_secs, tolerance_percent)` — Verify downloaded file duration matches expected
- **Logging**: `setup_logging(log_file)`, `get_logger()` — File-based logging system

**cdripper-console.py** — Command-line interface:
- Menu-driven TUI with colored output (colorama)
- Main entry point for console users
- Imports and extends utilities from cdripper_utils

**cdripper-gui.py** (Isaac GUI) — Tkinter-based GUI:
- Child-friendly interface with large buttons and colorful design
- Four tabs: YouTube Search, Copy CD, Playlist, Download Video (MP4)
- Requires system tkinter (not a pip package)
- Imports from cdripper_utils
- Features:
  - `📺 YouTube` — Search and download MP3 from YouTube
  - `💿 Copiar CD` — Copy MP3s from physical CD (with YouTube fallback)
  - `💿 Playlist` — Download entire YouTube playlists as MP3
  - `🎬 Baixar Vídeo` — Search and download videos as MP4 with size/speed display

### Build System

**build.sh** — Cross-platform build script:
- Uses PyInstaller to create native executables
- Auto-detects OS (Darwin/macOS, Linux, Windows)
- Platform-specific output:
  - macOS: `dist/cdripper.app`
  - Linux: `dist/cdripper` (single file)
  - Windows: `dist/cdripper.exe` (windowed)
- Automatically installs PyInstaller if missing

**BUILD.md** — Detailed build documentation covering manual compilation, cross-platform notes, and CI/CD setup.

## Common Commands

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Install PyInstaller for building
pip install pyinstaller
```

### Running
```bash
# Run console version
python3 cdripper-console.py

# Run GUI version
python3 cdripper-gui.py
```

### Debugging & Logging
```bash
# View live logs during execution
tail -f cdripper.log

# Analyze logs after completion
cat cdripper.log | grep "FALHOU\|SUCESSO\|YouTube\|CD:"
```

All operations are automatically logged to `cdripper.log` with timestamps (timestamp - level - message format).

## User Features

### Folder Selection
Both console and GUI versions allow users to choose where files are saved:
- **Console**: Prompts before each operation (YouTube search or CD copy)
- **GUI**: Input field in each tab showing default "downloads" but allowing custom paths
- Both support relative or absolute paths; default is "downloads" in current directory

### Building
```bash
# Automatic platform-based build
chmod +x build.sh
./build.sh

# Manual build for specific platform
# macOS
pyinstaller -y --windowed --name "cdripper" cdripper-gui.py

# Linux
pyinstaller -y --onefile --name "cdripper" cdripper-gui.py

# Windows
pyinstaller -y --onefile --windowed --name "cdripper" cdripper-gui.py
```

## Dependencies

**Runtime (pip):**
- `yt-dlp >= 2024.0.0` — YouTube downloader and metadata extraction
- `colorama >= 0.4.6` — Terminal color output
- `python-dateutil >= 2.8.0` — Date utilities
- `mutagen >= 1.47.0` — MP3 metadata editing
- `Pillow >= 10.0.0` — Image processing for artwork

**System:**
- `tkinter` — GUI toolkit (comes with Python but requires system install on Linux):
  - Ubuntu/Debian: `sudo apt install python3-tk`
  - Fedora: `sudo dnf install python3-tkinter`
  - macOS: Use official Python from python.org or homebrew with Tk
  - Windows: Reinstall Python with tcl/tk option

**Optional:**
- `ffmpeg` — Audio format conversion (improves MP3 quality from YouTube downloads)

## GUI Components & Patterns

### Win7ProgressBar (Custom Widget)
- Custom `tk.Canvas` widget styled like Windows 7 progress bar
- Supports `bar["value"]` and `bar["maximum"]` dictionary interface for compatibility
- Features animated green gradient with moving stripe pattern
- Used in all tabs for download/copy progress visualization
- Methods: `start_animation()`, `stop_animation()`, `set_value()`

### Progress Hooks & Callbacks
- Downloads use `progress_hook` callbacks to update GUI in real-time
- Hooks receive dict from yt-dlp with: `total_bytes`, `downloaded_bytes`, `speed`, `status`
- GUI updates via `self.root.after(0, ...)` to run on main thread (thread-safe)
- Format: bytes to MB conversion (`value / (1024 * 1024)`), speed calculation, ETA estimation

### Thread Pattern
- All network operations (search, download) run in daemon threads
- GUI updates scheduled back to main thread via `self.root.after(0, callback)`
- Prevents UI freezing during long operations
- Cancellation via flags: `self.cancel_copy`, `self.video_cancel`, `self.playlist_cancel`

### Details Log Widget
- `self.cd_details_text` — Read-only Text widget showing operation results
- Populated via `_update_details_log(message)` method during file processing
- Displays: `✔ CD: filename` (success from any source)
- Shows real-time progress as files are processed
- Auto-scrolls to bottom to show latest operations

## Key Design Patterns

1. **Utility Module Pattern**: cdripper_utils.py contains all reusable logic; both interfaces import from it to avoid duplication

2. **Cross-platform Compatibility**:
   - CD detection uses platform-specific paths per OS
   - Build script auto-detects and creates appropriate executables
   - Uses `pathlib` and `os.path` for path handling

3. **Graceful Degradation**:
   - Colorama falls back to plain text if import fails
   - yt-dlp auto-installs if missing
   - Missing tkinter provides clear installation instructions

4. **Per-File Fallback Strategy with Smart Retries** (`copy_cd_with_fallback_gui()`): For each file being copied from CD:
   - First attempts to copy from physical CD (with timeout-based read test)
   - If that fails, immediately searches YouTube and downloads the MP3
   - Marks files that fail both CD copy and first YouTube search for retry
   - After initial pass, retries failed files with name variations:
     - Removes trailing numbers ("Música 1" → "Música")
     - Removes parenthetical content ("Música (Remix)" → "Música")
     - Removes brackets ("Música [Official]" → "Música")
     - Uses first 2-3 words if title is long
   - Third pass: tries WITHOUT duration validation (fallback mode)
   - Shows progress with emoji feedback (✔ CD success, displays as `✔ CD:` in details log)
   - Never exposes errors to the user; silently handles all failures

## Development Notes

- **Language**: Portuguese comments and output strings throughout the codebase (UI/UX is in Portuguese)
- **Python Version**: Targets Python 3.12+ (based on BUILD.md GitHub Actions example)
- **Cross-platform**: Test changes on macOS, Linux, and Windows if they touch:
  - `find_cd_drives()` — OS-specific drive detection
  - Build scripts or executable generation
  - File path operations

- **Testing CD Features**: Requires actual CD drive and MP3-containing media; console and GUI can be tested independently

- **GUI Colors & Fonts**:
  - Title font: `("Arial Rounded MT Bold", 28)`
  - Section font: `("Arial Rounded MT Bold", 19)`
  - Text font: `("Arial", 14)`
  - Button font: `("Arial Rounded MT Bold", 16)`
  - Primary colors: `#F6FBFF` (background), `#CDEBFF` (header), `#00B4D8` (search), `#2A9D8F` (download)
  - Defined in `_build_styles()` method

## Logging System

**File**: `cdripper.log` (created automatically in working directory)

**Features**:
- Initialized at GUI startup via `setup_logging("cdripper.log")`
- All console output also written to file with timestamps
- Format: `YYYY-MM-DD HH:MM:SS - LEVEL - message`
- Useful for post-mortem analysis of which files succeeded/failed

**Key Log Entries**:
- `DEBUG COPY: Total de X arquivo(s) para processar` — Copy operation started
- `[##/##] Processando: filename` — File being processed
- `→ CD: SUCESSO` — File copied from physical CD
- `→ CD: FALHOU - tentando YouTube...` — CD copy failed, trying YouTube
- `→ YouTube: N resultado(s) encontrado(s)` — YouTube search results count
- `→ YouTube: baixando URL` — Download starting
- `→ YouTube: SUCESSO` — File successfully downloaded
- `✔ SUCESSO` — File successfully obtained (CD or YouTube)
- `DEBUG SUMMARY: X de Y arquivo(s) processado(s)` — Operation completed
- `Faixas que ficaram incompletas (N):` — Files that failed all methods

**Debugging with logs**:
```bash
# Monitor during operation
tail -f cdripper.log

# Find failed files
grep "FALHOU\|incompleta" cdripper.log

# Count successes
grep "✔ SUCESSO" cdripper.log | wc -l
```

## Accessibility & Inclusive Design Standards

**When modifying code, maintain these accessibility principles:**

1. **Error Messages Must Be User-Friendly**:
   - ❌ Never use technical error codes, stack traces, or alarming language
   - ✅ Use emoji and simple, positive language (e.g., "✔ Arquivo encontrado!" instead of "INFO: File located successfully")
   - ✅ Provide constructive guidance ("Tente novamente" / "Try again") rather than failure statements

2. **GUI Development (cdripper-gui.py)**:
   - Maintain large button sizes and readable fonts
   - Use warm, friendly colors
   - Keep visual hierarchy simple and clear
   - Test with actual target users (children with autism spectrum) when possible

3. **Error Recovery** (Per-File Strategy):
   - Process each file independently: try CD copy → if fails, try YouTube immediately
   - Never wait to collect failures or show error summaries
   - Silently handle all edge cases; users only see progress indicators
   - Display status with emoji (✔ CD copy ok from any source, ⊘ unavailable)
   - Never expose exception details or technical error messages

4. **Console Output (cdripper-console.py)**:
   - Use emoji and colors for visual feedback
   - Keep messages brief and supportive
   - Avoid technical jargon in user-facing text

5. **Continuous Visual Feedback**:
   - Show animated spinner (⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏) during all operations
   - Never let the user think the application is frozen
   - Include progress bar during downloads with real-time speed display
   - Update display continuously without interruption

These principles are core to the project's mission and should guide all development decisions.

## Build Output

Artifacts are generated in `dist/` directory after build:
- `.app` bundles (macOS)
- Single executables (Linux)
- `.exe` windows applications
- `__pycache__` and `.spec` files are generated during build (already in .gitignore)
