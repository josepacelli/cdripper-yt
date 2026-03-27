aj# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**cdripper-yt** is a multi-platform music downloader with dual functionality:
- Download MP3s from YouTube
- Copy MP3s from physical CDs to local storage with automatic YouTube fallback (if CD read fails)

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
- YouTube search and download functions (using yt-dlp)
- Cross-platform CD drive detection (macOS `/Volumes`, Windows drive letters, Linux `/mnt`/`/media`)
- MP3 file discovery and organization
- Progress tracking for downloads
- Filename sanitization

**cdripper-console.py** — Command-line interface:
- Menu-driven TUI with colored output (colorama)
- Main entry point for console users
- Imports and extends utilities from cdripper_utils

**cdripper-gui.py** (Isaac GUI) — Tkinter-based GUI:
- Child-friendly interface with large buttons and colorful design
- Same functionality as console but with visual UI
- Requires system tkinter (not a pip package)
- Imports from cdripper_utils

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

**System:**
- `tkinter` — GUI toolkit (comes with Python but requires system install on Linux):
  - Ubuntu/Debian: `sudo apt install python3-tk`
  - Fedora: `sudo dnf install python3-tkinter`
  - macOS: Use official Python from python.org or homebrew with Tk
  - Windows: Reinstall Python with tcl/tk option

**Optional:**
- `ffmpeg` — Audio format conversion (improves MP3 quality from YouTube downloads)

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

4. **Per-File Fallback Strategy with Smart Retries**: For each file being copied from CD:
   - First attempts to copy from physical CD
   - If that fails, immediately searches YouTube and downloads the MP3
   - Marks files that fail both CD copy and first YouTube search for retry
   - After initial pass, retries failed files with name variations:
     - Removes trailing numbers ("Música 1" → "Música")
     - Removes parenthetical content ("Música (Remix)" → "Música")
     - Removes brackets ("Música [Official]" → "Música")
     - Uses first 2-3 words if title is long
   - Shows progress with emoji feedback (✔ for CD success, 🎵 for YouTube success, ⊘ if neither works)
   - Never exposes errors to the user; silently handles all failures

## Development Notes

- **Language**: Portuguese comments and output strings throughout the codebase (UI/UX is in Portuguese)
- **Python Version**: Targets Python 3.12+ (based on BUILD.md GitHub Actions example)
- **Cross-platform**: Test changes on macOS, Linux, and Windows if they touch:
  - `find_cd_drives()` — OS-specific drive detection
  - Build scripts or executable generation
  - File path operations

- **Testing CD Features**: Requires actual CD drive and MP3-containing media; console and GUI can be tested independently

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
   - Display status with emoji (✔ CD copy ok, 🎵 YouTube download ok, ⊘ unavailable)
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