#!/bin/bash
# Script para compilar cdripper em diferentes plataformas

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     cdripper - Build Script            ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo ""

# Verificar se PyInstaller está instalado
if ! command -v pyinstaller &> /dev/null; then
    echo -e "${YELLOW}Instalando PyInstaller...${NC}"
    pip install pyinstaller -q
fi

# Verificar plataforma
PLATFORM=$(uname -s)

case "$PLATFORM" in
    Darwin)
        echo -e "${GREEN}Sistema detectado: macOS${NC}"
        echo "Compilando para macOS..."
        pyinstaller -y --windowed --name "cdripper" cdripper-gui.py
        echo -e "${GREEN}✔ Executável macOS criado em: dist/cdripper.app${NC}"
        ;;
    Linux)
        echo -e "${GREEN}Sistema detectado: Linux${NC}"
        echo "Compilando para Linux..."
        pyinstaller -y --onefile --name "cdripper" cdripper-gui.py
        echo -e "${GREEN}✔ Executável Linux criado em: dist/cdripper${NC}"
        ;;
    MSYS*|MINGW*|CYGWIN*)
        echo -e "${GREEN}Sistema detectado: Windows${NC}"
        echo "Compilando para Windows..."
        pyinstaller -y --onefile --windowed --name "cdripper" cdripper-gui.py
        echo -e "${GREEN}✔ Executável Windows criado em: dist/cdripper.exe${NC}"
        ;;
    *)
        echo -e "${RED}Sistema não suportado: $PLATFORM${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}Build concluído!${NC}"
echo -e "${YELLOW}Arquivos gerados em: dist/${NC}"