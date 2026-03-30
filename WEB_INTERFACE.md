# Interface Web - PyWebView

## Sobre

A branch `gui/pywebview` contém uma nova interface para **cdripper-yt** usando **PyWebView**.

**PyWebView** executa uma aplicação web como uma janela de desktop nativa, combinando:
- ✅ HTML/CSS/JavaScript moderno
- ✅ Acesso a arquivos locais (CDs, pastas)
- ✅ Empacotável como executável (.exe, .app, .dmg)
- ✅ Design completamente personalizável
- ✅ Sem necessidade de navegador externo

## Instalação

```bash
# Ativar a branch
git checkout gui/pywebview

# Instalar dependências
pip install -r requirements.txt
```

Requisitos adicionais:
- **macOS/Linux**: GTK+ 3.0+ (geralmente já instalado)
- **Windows**: Webview2 (instalado automaticamente)

## Execução

```bash
python3 cdripper-web.py
```

Uma janela de aplicação desktop vai abrir com a interface.

## Estrutura de Arquivos

```
.
├── cdripper-web.py          # Backend (API Python + PyWebView)
├── cdripper_utils.py        # Funções compartilhadas
├── web/                     # Frontend web
│   ├── index.html          # Interface HTML
│   ├── css/
│   │   └── style.css       # Estilos (cores, layout, responsivo)
│   └── js/
│       └── app.js          # Lógica JavaScript + comunicação com backend
└── requirements.txt         # Dependências

```

## Características

### YouTube
- 🔍 Busca de músicas
- ⬇ Download direto com validação de duração
- 🎵 Suporte a metadados (artwork, título, duração)

### CD
- 💿 Detecção automática de unidades de CD
- 📂 Listagem de arquivos com seleção individual
- 🎵 Cópia com fallback para YouTube (3 fases)
  - Fase 1: Cópia direta do CD
  - Fase 2: Retry com variações de nome
  - Fase 3: Fallback mode (qualquer duração > 30s)
- 📊 Barra de progresso com artwork dinâmica
- ✔ Contagem total de arquivos (sempre mostrada)

### Design
- 🎨 Cores vibrantes (roxo/ouro) para acessibilidade
- 📏 Fontes grandes (14-35rem) para legibilidade
- 🔘 Botões grandes (150%+ padrão)
- 🎭 Ícones emoji para contexto visual
- 📱 Responsivo (desktop e mobile)

## API Backend (Python → JavaScript)

Todas as funções são expostas via `api.` no JavaScript:

```javascript
// Buscar no YouTube
const results = await api.search_youtube("Bohemian Rhapsody");

// Baixar MP3
const result = await api.download_mp3(url, title, folder);

// Encontrar CDs
const drives = await api.find_cd_drives();

// Listar MP3s em pasta
const files = await api.find_mp3_files("/Volumes/CD");

// Copiar CD com fallback
const result = await api.copy_cd_with_fallback(
    "/Volumes/CD",
    "downloads",
    selectedFiles
);

// Abrir diálogo de pasta
const folder = await api.browse_folder();
```

## Callbacks Frontend (JavaScript → Python)

O backend chama funções JavaScript para atualizar a UI:

```javascript
// Atualizar barra de progresso
updateProgress(processed, total, filename);

// Atualizar artwork exibida
updateArtwork(artworkBase64);
```

## Diferenças vs Tkinter

| Aspecto | Tkinter | PyWebView |
|---------|---------|-----------|
| **Frameworks** | Tkinter (Python) | PyWebView + HTML/CSS/JS |
| **Design** | Limitado, código Python | Completo, CSS moderno |
| **Responsivo** | Não | Sim (mobile-friendly) |
| **Emojis** | Suportados | Nativos |
| **Customização** | Difícil | Fácil (CSS) |
| **Tamanho** | Menor | Maior (inclui webview) |
| **Performance** | Rápida | Rápida |

## Desenvolvimento

### Modificar a Interface

Edite `web/index.html` para adicionar elementos e `web/css/style.css` para estilo.

Exemplo: aumentar tamanho dos botões
```css
.btn-large {
    padding: 25px;  /* de 20px */
    font-size: 1.5rem;  /* de 1.3rem */
}
```

### Adicionar Funcionalidade

1. Escrever função em `cdripper-web.py` classe `API`
2. Chamar via `await api.sua_funcao(args)` no JavaScript
3. Atualizar UI via `this.window.evaluate_js()`

Exemplo:
```python
# cdripper-web.py
def sua_funcao(self, parametro):
    resultado = fazer_algo(parametro)
    self.window.evaluate_js(f"updateUI('{resultado}')")
    return resultado
```

```javascript
// web/js/app.js
const resultado = await api.sua_funcao("valor");
```

## Build para Executável

```bash
pip install pyinstaller

# macOS
pyinstaller -y --windowed --name "cdripper" \
    --add-data "web:web" \
    cdripper-web.py

# Windows
pyinstaller -y --onefile --windowed --name "cdripper" \
    --add-data "web;web" \
    cdripper-web.py

# Linux
pyinstaller -y --onefile --name "cdripper" \
    --add-data "web:web" \
    cdripper-web.py
```

Executável gerado em `dist/`

## Notas

- A pasta `web/` deve estar no mesmo diretório que `cdripper-web.py` quando empacotado
- PyWebView requer uma janela visível para iniciar (não funciona em headless)
- Suportado em: Windows 10+, macOS 10.13+, Linux (GTK+)

## Acessibilidade

Projeto mantém foco em **acessibilidade para crianças com autismo**:

✅ **Sem mensagens de erro assustadoras**
- Falhas são silenciosas e tratadas internamente
- Interface sempre mostra progresso positivo

✅ **Design visual amigável**
- Cores vibrantes e quentes
- Fontes grandes e claras
- Ícones emoji para contexto
- Botões grandes fáceis de clicar

✅ **Feedback imediato**
- Barra de progresso contínua
- Artwork dinâmica durante cópia
- Contagem total sempre visível

## Troubleshooting

### PyWebView não inicia
```bash
# Verificar instalação
pip install --upgrade pywebview

# Testar importação
python3 -c "import webview; print('OK')"
```

### Artwork não aparece
Verificar em DevTools (F12) se `updateArtwork()` é chamada com base64 válido.

### Aplicação lenta ao copiar
Normal - downloads de YouTube são lentos. Progressão é mostrada continuamente.

## Feedback

Issues e sugestões para melhorar a interface web são bem-vindos! 🎵
