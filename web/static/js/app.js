/**
 * BioSonification - Frontend Application
 * Handles user interaction, file upload, and API calls
 */

// DOM Elements
const elements = {
    // Navigation
    navBtns: document.querySelectorAll('.nav-btn'),
    pages: document.querySelectorAll('.page-content'),

    // Tabs
    tabBtns: document.querySelectorAll('.tab-btn'),
    tabContents: document.querySelectorAll('.tab-content'),
    
    // Input
    fastaInput: document.getElementById('fasta-input'),
    fastaFile: document.getElementById('fasta-file'),
    fileUploadArea: document.getElementById('file-upload-area'),
    fileName: document.getElementById('file-name'),
    
    // Buttons
    generateBtn: document.getElementById('generate-btn'),
    retryBtn: document.getElementById('retry-btn'),
    generateAnotherBtn: document.getElementById('generate-another-btn'),
    downloadMidiBtn: document.getElementById('download-midi-btn'),
    
    // Sections
    inputSection: document.querySelector('.input-section'),
    loadingSection: document.getElementById('loading-section'),
    errorSection: document.getElementById('error-section'),
    resultsSection: document.getElementById('results-section'),
    errorMessage: document.getElementById('error-message'),
    
    // Audio
    audioPlayer: document.getElementById('audio-player'),
    audioUnavailable: document.getElementById('audio-unavailable'),
    
    // Parameters
    paramTempo: document.getElementById('param-tempo'),
    paramKey: document.getElementById('param-key'),
    paramPitchRange: document.getElementById('param-pitch-range'),
    paramScaleType: document.getElementById('param-scale-type'),
    paramRhythm: document.getElementById('param-rhythm'),

    // Sequence info
    seqHeader: document.getElementById('seq-header'),
    seqLength: document.getElementById('seq-length'),
};

// State
let selectedFile = null;
const FASTA_SEQUENCE_CHARS = new Set('ABCDEFGHIKLMNPQRSTUVWXYZ*-.'.split(''));

// ============================================
// Navigation
// ============================================

elements.navBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        const pageId = btn.dataset.page;

        // Update buttons
        elements.navBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        // Update pages
        elements.pages.forEach(page => page.classList.remove('active'));
        document.getElementById(`${pageId}-page`).classList.add('active');

        // Load examples when switching to examples page
        if (pageId === 'examples') {
            const examplesGrid = document.getElementById('examples-grid');
            if (examplesGrid.children.length === 1 && examplesGrid.children[0].classList.contains('loading-examples')) {
                loadExamples();
            }
        }
    });
});

// ============================================
// Tab Switching
// ============================================

elements.tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        const tabId = btn.dataset.tab;
        
        // Update buttons
        elements.tabBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        
        // Update content
        elements.tabContents.forEach(content => content.classList.remove('active'));
        document.getElementById(`${tabId}-tab`).classList.add('active');
    });
});

// ============================================
// File Upload
// ============================================

// File input change
elements.fastaFile.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        selectedFile = e.target.files[0];
        elements.fileName.textContent = selectedFile.name;
        elements.fileUploadArea.classList.add('has-file');
    }
});

// Drag and drop
elements.fileUploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    elements.fileUploadArea.classList.add('dragover');
});

elements.fileUploadArea.addEventListener('dragleave', () => {
    elements.fileUploadArea.classList.remove('dragover');
});

elements.fileUploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    elements.fileUploadArea.classList.remove('dragover');
    
    if (e.dataTransfer.files.length > 0) {
        selectedFile = e.dataTransfer.files[0];
        elements.fastaFile.files = e.dataTransfer.files;
        elements.fileName.textContent = selectedFile.name;
        elements.fileUploadArea.classList.add('has-file');
    }
});

// Click on upload area to trigger file input
elements.fileUploadArea.addEventListener('click', (e) => {
    if (e.target !== elements.fastaFile) {
        elements.fastaFile.click();
    }
});

// ============================================
// Generation
// ============================================

elements.generateBtn.addEventListener('click', handleGenerate);
elements.retryBtn.addEventListener('click', resetToInput);
elements.generateAnotherBtn.addEventListener('click', resetToInput);

async function handleGenerate() {
    // Get FASTA data
    let fastaText = elements.fastaInput.value.trim();
    
    // If no text, check if file is selected
    if (!fastaText && !selectedFile) {
        showError('Введите FASTA последовательность или загрузите FASTA файл');
        return;
    }

    let validationText = fastaText;
    if (selectedFile) {
        try {
            validationText = await selectedFile.text();
        } catch (error) {
            showError('Не удалось прочитать файл. Загрузите текстовый FASTA файл в кодировке UTF-8.');
            return;
        }
    }

    const validation = validateFastaFormat(validationText);
    if (!validation.valid) {
        showError(validation.message);
        return;
    }
    
    // Show loading
    showLoading();
    
    try {
        let response;
        
        if (selectedFile) {
            // Upload file
            const formData = new FormData();
            formData.append('fasta_file', selectedFile);
            
            response = await fetch('/api/generate', {
                method: 'POST',
                body: formData
            });
        } else {
            // Send text
            response = await fetch('/api/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ fasta: fastaText })
            });
        }
        
        const data = await response.json();
        
        if (!response.ok || !data.success) {
            throw new Error(data.error || 'Generation failed');
        }
        
        // Show results
        showResults(data);
        
    } catch (error) {
        showError(error.message);
    }
}

// ============================================
// Display Functions
// ============================================

function showLoading() {
    elements.inputSection.classList.add('hidden');
    elements.loadingSection.classList.remove('hidden');
    elements.errorSection.classList.add('hidden');
    elements.resultsSection.classList.add('hidden');
}

function showError(message) {
    elements.inputSection.classList.add('hidden');
    elements.loadingSection.classList.add('hidden');
    elements.errorSection.classList.remove('hidden');
    elements.resultsSection.classList.add('hidden');
    elements.errorMessage.textContent = message;
}

function showResults(data) {
    elements.inputSection.classList.add('hidden');
    elements.loadingSection.classList.add('hidden');
    elements.errorSection.classList.add('hidden');
    elements.resultsSection.classList.remove('hidden');
    
    // Audio player
    if (data.audio_available) {
        elements.audioPlayer.src = `/api/download/${data.session_id}/ogg`;
        elements.audioPlayer.classList.remove('hidden');
        elements.audioUnavailable.classList.add('hidden');
    } else {
        elements.audioPlayer.classList.add('hidden');
        elements.audioUnavailable.classList.remove('hidden');
    }
    
    // Download link
    elements.downloadMidiBtn.href = `/api/download/${data.session_id}/midi`;
    
    // Parameters
    const params = data.musical_params;
    elements.paramTempo.textContent = Math.round(params.tempo);
    elements.paramKey.textContent = params.key;
    elements.paramPitchRange.textContent = params.sequence_type;
    elements.paramScaleType.textContent = params.harmony_bars;
    elements.paramRhythm.textContent = params.melody_notes;

    // Sequence info
    elements.seqHeader.textContent = data.header || 'User Sequence';
    elements.seqLength.textContent = data.sequence_length.toLocaleString();
}

function resetToInput() {
    elements.inputSection.classList.remove('hidden');
    elements.loadingSection.classList.add('hidden');
    elements.errorSection.classList.add('hidden');
    elements.resultsSection.classList.add('hidden');
    
    // Reset file selection
    selectedFile = null;
    elements.fastaFile.value = '';
    elements.fileName.textContent = '';
    elements.fileUploadArea.classList.remove('has-file');
    
    // Stop audio
    elements.audioPlayer.pause();
    elements.audioPlayer.src = '';
}

// ============================================
// Utility Functions
// ============================================

function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}

function validateFastaFormat(fastaText) {
    const text = fastaText.replace(/^\uFEFF/, '').trim();

    if (!text) {
        return { valid: false, message: 'Введите FASTA последовательность или загрузите FASTA файл.' };
    }

    if (!text.startsWith('>')) {
        return { valid: false, message: "FASTA должна начинаться со строки заголовка: >sequence_id" };
    }

    let currentHeader = null;
    let currentHasSequence = false;
    let hasRecord = false;

    for (const rawLine of text.split(/\r?\n/)) {
        const line = rawLine.trim();
        if (!line) {
            continue;
        }

        if (line.startsWith('>')) {
            if (currentHeader !== null && !currentHasSequence) {
                return { valid: false, message: `FASTA запись "${currentHeader}" не содержит последовательность.` };
            }

            currentHeader = line.slice(1).trim() || 'Sequence';
            currentHasSequence = false;
            hasRecord = true;
            continue;
        }

        if (currentHeader === null) {
            return { valid: false, message: 'Строки последовательности должны идти после FASTA заголовка.' };
        }

        const invalidChar = [...line.toUpperCase()].find(char => !FASTA_SEQUENCE_CHARS.has(char));
        if (invalidChar) {
            return {
                valid: false,
                message: `Недопустимый символ в FASTA последовательности: "${invalidChar}".`
            };
        }

        currentHasSequence = true;
    }

    if (!hasRecord) {
        return { valid: false, message: 'FASTA запись не найдена.' };
    }

    if (!currentHasSequence) {
        return { valid: false, message: `FASTA запись "${currentHeader}" не содержит последовательность.` };
    }

    return { valid: true, message: '' };
}

// ============================================
// Keyboard Shortcuts
// ============================================

document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + Enter to generate
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        if (!elements.inputSection.classList.contains('hidden')) {
            handleGenerate();
        }
    }
});

// ============================================
// Initialization
// ============================================

// Check server status on load
async function checkStatus() {
    try {
        const response = await fetch('/api/status');
        const status = await response.json();
        
        if (!status.ready) {
            console.warn('Generator not ready:', status.error);
            // Could show a warning banner here
        }
        
        if (!status.audio_enabled) {
            console.info('Audio playback disabled - no synthesizer found');
        }
    } catch (error) {
        console.error('Failed to check status:', error);
    }
}

// Run status check
checkStatus();

// ============================================
// Examples Gallery
// ============================================

async function loadExamples() {
    try {
        const response = await fetch('/api/examples');
        const data = await response.json();

        if (data.examples && data.examples.length > 0) {
            renderExamples(data.examples);
        } else {
            showExamplesError('No examples available');
        }
    } catch (error) {
        console.error('Failed to load examples:', error);
        showExamplesError('Failed to load examples');
    }
}

async function renderExamples(examples) {
    const grid = document.getElementById('examples-grid');
    grid.innerHTML = '';

    for (const example of examples) {
        const card = await createExampleCard(example);
        grid.appendChild(card);
    }
}

async function createExampleCard(example) {
    const card = document.createElement('div');
    card.className = 'example-card';

    const audioUrl = `/api/examples/${example.id}/audio`;
    const midiUrl = `/api/examples/${example.id}/midi`;

    // Check if audio is available
    let audioAvailable = false;
    try {
        const response = await fetch(audioUrl, { method: 'HEAD' });
        audioAvailable = response.ok;
    } catch (error) {
        audioAvailable = false;
    }

    const audioPlayerHTML = audioAvailable
        ? `<div class="example-audio-player">
            <audio controls preload="none">
                <source src="${audioUrl}" type="audio/ogg">
                Your browser does not support the audio element.
            </audio>
        </div>`
        : `<div class="audio-unavailable-example">
            <p>Audio playback requires FluidSynth with OGG support</p>
        </div>`;

    card.innerHTML = `
        <div class="example-header">
            <div class="organism-icon">${example.icon}</div>
            <div class="organism-info">
                <div class="organism-name">${example.organism}</div>
                <div class="scientific-name">${example.scientific_name}</div>
            </div>
        </div>

        <p class="example-description">${example.description}</p>

        ${audioPlayerHTML}

        <div class="example-metadata">
            <div class="metadata-item">
                <span class="metadata-icon">📊</span>
                <span>${example.bars} bars</span>
            </div>
            <div class="metadata-item">
                <span class="metadata-icon">⏱️</span>
                <span>~${example.duration_seconds}s</span>
            </div>
        </div>

        <div class="example-actions">
            <a href="${midiUrl}" class="example-download-btn" download>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="7 10 12 15 17 10"/>
                    <line x1="12" y1="15" x2="12" y2="3"/>
                </svg>
                Download MIDI
            </a>
        </div>
    `;

    return card;
}

function showExamplesError(message) {
    const grid = document.getElementById('examples-grid');
    grid.innerHTML = `
        <div class="audio-unavailable-example">
            <p>${message}</p>
        </div>
    `;
}

// Load examples on page load
document.addEventListener('DOMContentLoaded', () => {
    // Don't load examples automatically - they will load when user switches to examples page
});

// ============================================
// Demo Data (for testing)
// ============================================

function loadDemoData() {
    const demoFasta = `>BRCA1 gene fragment (demo)
ATCGGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGC
TAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTA
GCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGC
TAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTA
GCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGC`;
    
    elements.fastaInput.value = demoFasta;
}

// Uncomment to load demo data on page load:
// loadDemoData();
