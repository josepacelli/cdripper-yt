# Script para compilar cdripper no Windows (PowerShell)

# Cores para output
$GREEN = "`e[0;32m"
$YELLOW = "`e[1;33m"
$RED = "`e[0;31m"
$NC = "`e[0m"

Write-Host "$GREEN╔════════════════════════════════════════╗$NC"
Write-Host "$GREEN║     cdripper - Build Script            ║$NC"
Write-Host "$GREEN╚════════════════════════════════════════╝$NC"
Write-Host ""

# Verificar se PyInstaller está instalado
try {
    $pyinstaller = Get-Command pyinstaller -ErrorAction Stop
} catch {
    Write-Host "$YELLOW`Instalando PyInstaller...$NC"
    python -m pip install pyinstaller -q
}

# Sistema detectado: Windows
Write-Host "$GREEN`Sistema detectado: Windows$NC"
Write-Host "Compilando para Windows..."

# Compilar
pyinstaller -y --onefile --windowed --name "cdripper" cdripper-gui.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "$GREEN`✔ Executável Windows criado em: dist/cdripper.exe$NC"
} else {
    Write-Host "$RED`✘ Erro na compilação$NC"
    exit 1
}

Write-Host ""
Write-Host "$GREEN`Build concluído!$NC"
Write-Host "$YELLOW`Arquivos gerados em: dist/$NC"
