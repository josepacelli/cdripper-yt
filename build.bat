@echo off
REM Script para compilar cdripper no Windows (Batch)

setlocal enabledelayedexpansion

echo.
echo ╔════════════════════════════════════════╗
echo ║     cdripper - Build Script            ║
echo ╚════════════════════════════════════════╝
echo.

REM Verificar se PyInstaller está instalado
where pyinstaller >nul 2>nul
if errorlevel 1 (
    echo Instalando PyInstaller...
    python -m pip install pyinstaller -q
)

REM Sistema detectado: Windows
echo Sistema detectado: Windows
echo Compilando para Windows...
echo.

REM Compilar
pyinstaller -y --onefile --windowed --name "cdripper" cdripper-gui.py

if errorlevel 1 (
    echo [ERRO] Erro na compilacao
    exit /b 1
) else (
    echo [OK] Executavel Windows criado em: dist\cdripper.exe
)

echo.
echo Build concluido!
echo Arquivos gerados em: dist\
echo.

endlocal
