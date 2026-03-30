// Referência à API do PyWebView
let api = window.pywebview?.api;

// Estado global
let selectedFiles = [];
let youtubeDownloading = false;
let cdCopying = false;

// Inicializar ao carregar a página
document.addEventListener('DOMContentLoaded', async () => {
    setupTabs();
    await loadCDDrives();
    setupEventListeners();
});

// ── Abas ────────────────────────────────────────────────────────────────────

function setupTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const tabName = button.getAttribute('data-tab');

            // Desativar todas as abas
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));

            // Ativar aba selecionada
            button.classList.add('active');
            document.getElementById(tabName).classList.add('active');
        });
    });
}

// ── Event Listeners ──────────────────────────────────────────────────────────

function setupEventListeners() {
    // Enter no campo de busca YouTube
    const youtubeQuery = document.getElementById('youtube-query');
    if (youtubeQuery) {
        youtubeQuery.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') searchYouTube();
        });
    }
}

// ── YouTube ──────────────────────────────────────────────────────────────────

async function searchYouTube() {
    const query = document.getElementById('youtube-query').value.trim();
    const folder = document.getElementById('youtube-folder').value.trim() || 'downloads';

    if (!query) {
        showStatus('youtube-status', 'Por favor, escreva o nome de uma música.', 'error');
        return;
    }

    if (!api) {
        showStatus('youtube-status', 'API não disponível.', 'error');
        return;
    }

    showStatus('youtube-status', '🔍 Buscando...', 'info');
    youtubeDownloading = true;

    try {
        const results = await api.search_youtube(query);

        if (!results || results.length === 0) {
            showStatus('youtube-status', '❌ Nenhuma música encontrada.', 'error');
            return;
        }

        displayYouTubeResults(results, folder);
    } catch (error) {
        console.error('Erro ao buscar:', error);
        showStatus('youtube-status', '❌ Erro ao buscar. Tente novamente.', 'error');
    } finally {
        youtubeDownloading = false;
    }
}

function displayYouTubeResults(results, folder) {
    const container = document.getElementById('youtube-results');
    container.innerHTML = '';

    results.forEach((result, index) => {
        const duration = formatDuration(result.duration || 0);
        const title = result.title || 'Sem título';

        const div = document.createElement('div');
        div.className = 'result-item';
        div.innerHTML = `
            <img src="${result.thumbnail || ''}" alt="Capa" class="result-thumbnail" onerror="this.src='data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22%3E%3Crect fill=%22%23ddd%22 width=%22100%22 height=%22100%22/%3E%3C/svg%3E'">
            <div class="result-info">
                <div class="result-title">${escapeHtml(title)}</div>
                <div class="result-duration">⏱ ${duration}</div>
            </div>
            <button class="result-btn" onclick="downloadFromYouTube(${index}, '${escapeHtml(folder)}')">
                ⬇ Baixar
            </button>
        `;
        container.appendChild(div);
    });

    showStatus('youtube-status', `✔ ${results.length} resultado(s) encontrado(s)`, 'success');
}

async function downloadFromYouTube(index, folder) {
    const query = document.getElementById('youtube-query').value.trim();

    if (!api) {
        showStatus('youtube-status', 'API não disponível.', 'error');
        return;
    }

    showStatus('youtube-status', '⬇ Baixando...', 'info');

    try {
        const results = await api.search_youtube(query);
        const result = results[index];

        if (!result) {
            showStatus('youtube-status', '❌ Erro: resultado não encontrado.', 'error');
            return;
        }

        const url = result.url || result.webpage_url || `https://www.youtube.com/watch?v=${result.id}`;
        const title = result.title || 'Música';

        const response = await api.download_mp3(url, title, folder);

        if (response.success) {
            showStatus('youtube-status', `✔ Baixado: ${response.filename}`, 'success');
            document.getElementById('youtube-query').value = '';
            document.getElementById('youtube-results').innerHTML = '';
        } else {
            showStatus('youtube-status', '❌ Erro ao baixar.', 'error');
        }
    } catch (error) {
        console.error('Erro ao baixar:', error);
        showStatus('youtube-status', '❌ Erro ao baixar. Tente novamente.', 'error');
    }
}

// ── CD ───────────────────────────────────────────────────────────────────────

async function loadCDDrives() {
    if (!api) return;

    try {
        const drives = await api.find_cd_drives();
        const select = document.getElementById('cd-drive');

        select.innerHTML = '';

        if (!drives || drives.length === 0) {
            const option = document.createElement('option');
            option.value = '';
            option.textContent = 'Nenhuma unidade encontrada';
            select.appendChild(option);
            return;
        }

        drives.forEach(drive => {
            const option = document.createElement('option');
            option.value = drive;
            option.textContent = drive;
            select.appendChild(option);
        });

        if (drives.length > 0) {
            select.value = drives[0];
        }
    } catch (error) {
        console.error('Erro ao carregar unidades:', error);
    }
}

async function listCDFiles() {
    const drive = document.getElementById('cd-drive').value;

    if (!drive) {
        showStatus('cd-status', 'Por favor, selecione uma unidade de CD.', 'error');
        return;
    }

    if (!api) {
        showStatus('cd-status', 'API não disponível.', 'error');
        return;
    }

    showStatus('cd-status', '📂 Lendo CD...', 'info');

    try {
        const fileList = await api.find_mp3_files(drive);

        if (!fileList || Object.keys(fileList).length === 0) {
            showStatus('cd-status', 'Nenhum arquivo MP3 encontrado no CD.', 'error');
            document.getElementById('cd-files').innerHTML = '';
            return;
        }

        displayCDFiles(fileList);
        showStatus('cd-status', '✔ Arquivos carregados', 'success');
    } catch (error) {
        console.error('Erro ao ler CD:', error);
        showStatus('cd-status', 'Erro ao ler CD. Verifique a unidade.', 'error');
    }
}

function displayCDFiles(fileList) {
    const container = document.getElementById('cd-files');
    let html = '<div class="files-list">';
    selectedFiles = [];

    Object.entries(fileList).forEach(([folder, files]) => {
        files.forEach((file, index) => {
            const fileId = `${folder}/${file}`;
            selectedFiles.push({ folder, file, selected: true });

            html += `
                <div class="file-item">
                    <input type="checkbox" class="file-checkbox" data-folder="${folder}" data-file="${file}" checked>
                    <div class="file-name">🎵 ${escapeHtml(file)}</div>
                </div>
            `;
        });
    });

    html += '</div>';
    container.innerHTML = html;

    // Adicionar listeners aos checkboxes
    document.querySelectorAll('.file-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', updateSelectedFiles);
    });

    // Mostrar botão de cópia
    document.getElementById('cd-copy-btn').style.display = 'block';
}

function updateSelectedFiles() {
    selectedFiles = [];
    document.querySelectorAll('.file-checkbox').forEach(checkbox => {
        if (checkbox.checked) {
            selectedFiles.push({
                folder: checkbox.getAttribute('data-folder'),
                file: checkbox.getAttribute('data-file'),
            });
        }
    });
}

async function copyCDFiles() {
    const drive = document.getElementById('cd-drive').value;
    const folder = document.getElementById('cd-folder').value.trim() || 'downloads';

    if (!drive) {
        showStatus('cd-status', 'Por favor, selecione uma unidade de CD.', 'error');
        return;
    }

    updateSelectedFiles();

    if (selectedFiles.length === 0) {
        showStatus('cd-status', 'Por favor, selecione pelo menos um arquivo.', 'error');
        return;
    }

    if (!api) {
        showStatus('cd-status', 'API não disponível.', 'error');
        return;
    }

    showStatus('cd-status', '');
    document.getElementById('cd-progress').style.display = 'block';
    cdCopying = true;

    try {
        const result = await api.copy_cd_with_fallback(drive, folder, selectedFiles);

        if (result.success) {
            showStatus('cd-status', `✔ ${result.total} arquivo(s) copiado(s)`, 'success');
        } else {
            showStatus('cd-status', `✔ ${result.total} arquivo(s)`, 'success');
        }
    } catch (error) {
        console.error('Erro ao copiar:', error);
        showStatus('cd-status', 'Erro ao copiar CD.', 'error');
    } finally {
        cdCopying = false;
        setTimeout(() => {
            document.getElementById('cd-progress').style.display = 'none';
        }, 2000);
    }
}

// ── Callbacks do Backend ─────────────────────────────────────────────────────

function updateProgress(processed, total, filename) {
    const percentage = Math.round((processed / total) * 100);
    const fill = document.getElementById('cd-progress-fill');
    const text = document.getElementById('cd-progress-text');
    const current = document.getElementById('cd-current-file');

    if (fill) fill.style.width = percentage + '%';
    if (text) text.textContent = percentage + '%';
    if (current) current.textContent = `📁 ${filename}`;
}

function updateArtwork(artworkBase64) {
    const container = document.getElementById('cd-artwork-display');

    if (!artworkBase64) {
        container.innerHTML = '<div class="artwork-placeholder">🎵</div>';
        return;
    }

    container.innerHTML = `<img src="data:image/jpeg;base64,${artworkBase64}" alt="Capa">`;
}

// ── Utilitários ──────────────────────────────────────────────────────────────

function formatDuration(seconds) {
    if (!seconds) return '--:--';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function showStatus(elementId, message, type) {
    const element = document.getElementById(elementId);
    if (!element) return;

    element.textContent = message;
    element.className = `status-message show ${type}`;

    if (type === 'success') {
        setTimeout(() => {
            element.classList.remove('show');
        }, 5000);
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function browseFolder(elementId) {
    if (!api) return;

    try {
        const folder = await api.browse_folder();
        if (folder) {
            document.getElementById(elementId).value = folder;
        }
    } catch (error) {
        console.error('Erro ao navegar pasta:', error);
    }
}
