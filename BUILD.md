# Compilando cdripper para Executáveis

Este projeto pode ser compilado para Windows, macOS e Linux usando PyInstaller.

## Pré-requisitos

Instale as dependências:

```bash
pip install -r requirements.txt
pip install pyinstaller
```

## Build Automático (Plataforma Atual)

Use o script de build fornecido:

```bash
chmod +x build.sh
./build.sh
```

O executável será criado na pasta `dist/`.

## Build Manual por Plataforma

### macOS

```bash
pyinstaller -y --windowed --name "cdripper" cdripper-gui.py
```

**Resultado:** `dist/cdripper.app` (aplicação macOS)

### Linux

```bash
pyinstaller -y --onefile --name "cdripper" cdripper-gui.py
```

**Resultado:** `dist/cdripper` (executável Linux)

### Windows

```bash
pyinstaller -y --onefile --windowed --name "cdripper" cdripper-gui.py
```

**Resultado:** `dist/cdripper.exe` (executável Windows)

## Compilação Cruzada (Cross-compilation)

Para compilar para outras plataformas, você precisa estar naquela plataforma específica:

| Plataforma | Compilar em | Resultado |
|-----------|-----------|----------|
| macOS | macOS | `dist/cdripper.app` |
| Linux | Linux | `dist/cdripper` |
| Windows | Windows | `dist/cdripper.exe` |

**Nota:** PyInstaller não suporta cross-compilation. Para gerar executáveis para múltiplas plataformas, você precisa:

1. Usar uma máquina macOS para compilar para macOS
2. Usar uma máquina Linux para compilar para Linux
3. Usar uma máquina Windows para compilar para Windows

Ou usar uma solução CI/CD (GitHub Actions, GitLab CI, etc.) que execute o build em diferentes ambientes.

## CI/CD com GitHub Actions

Crie `.github/workflows/build.yml`:

```yaml
name: Build Executables

on:
  push:
    tags:
      - 'v*'

jobs:
  build-macos:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt pyinstaller
      - run: ./build.sh
      - uses: actions/upload-artifact@v3
        with:
          name: cdripper-macos
          path: dist/cdripper.app

  build-linux:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt pyinstaller
      - run: ./build.sh
      - uses: actions/upload-artifact@v3
        with:
          name: cdripper-linux
          path: dist/cdripper

  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt pyinstaller
      - run: .\build.sh
      - uses: actions/upload-artifact@v3
        with:
          name: cdripper-windows
          path: dist/cdripper.exe
```

## Distribuição

Os executáveis podem ser distribuídos diretamente:

- **macOS:** Comprimir `cdripper.app` ou criar um DMG
- **Linux:** Distribuir `cdripper` direto ou criar pacote (deb, rpm, etc.)
- **Windows:** Distribuir `cdripper.exe` direto ou criar installer com NSIS/WiX

## Troubleshooting

### Erro: "icon is not in the correct format"
Remova a opção `--icon` ou use um ícone no formato correto (`.icns` para macOS, `.ico` para Windows).

### Erro: "tkinter not found"
Instale tkinter do sistema:
- **Ubuntu/Debian:** `sudo apt install python3-tk`
- **Fedora:** `sudo dnf install python3-tkinter`
- **macOS:** Use Python de `python.org` ou `brew install python-tk@3.12`
- **Windows:** Reinstale Python marcando "tcl/tk and IDLE"

### Arquivo muito grande
Use `--onedir` em vez de `--onefile` para arquivos menores (macOS recomenda `--onedir`).