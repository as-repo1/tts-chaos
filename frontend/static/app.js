// ─── TOAST NOTIFICATIONS ──────────────────────────────────────────────────

const Toast = {
  show(msg, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let icon = '<svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"></path></svg>';
    if (type === 'error') icon = '<svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M6 18L18 6M6 6l12 12"></path></svg>';
    if (type === 'info') icon = '<svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>';

    toast.innerHTML = `${icon}<span>${msg}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100%)';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }
};

// ─── API CLIENT ────────────────────────────────────────────────────────────

const API = {
  async getCatalog() {
    const res = await fetch('/api/models/catalog');
    const data = await res.json();
    return data.models;
  },
  async getVoices(offset = 0, limit = 50) {
    const res = await fetch(`/api/voices?offset=${offset}&limit=${limit}`);
    return res.json();
  },
  async searchVoices(q = '', model = '', lang = '') {
    const params = new URLSearchParams({ q, model, lang });
    const res = await fetch(`/api/voices/search?${params}`);
    return res.json();
  },
  async getModelVoices(modelId) {
    const res = await fetch(`/api/models/${modelId}/voices`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.voices;
  },
  async recommend(text, lang) {
    const res = await fetch(`/api/models/recommend?text=${encodeURIComponent(text)}&language=${lang}`);
    const data = await res.json();
    return data.recommended_model_id;
  },
  async createVoice(payload) {
    const res = await fetch('/api/voice', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to generate voice');
    }
    return res.json();
  },
  async createBatch(payload) {
    const res = await fetch('/api/voice/batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Batch generation failed');
    }
    return res.json();
  },
  async cloneVoice(formData) {
    const res = await fetch('/api/voice/clone', {
      method: 'POST',
      body: formData
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Cloning failed');
    }
    return res.json();
  },
  async startDownload(modelId) {
    const res = await fetch(`/api/models/download/${modelId}`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to start download');
    }
  },
  async deleteVoice(id) {
    const res = await fetch(`/api/voices/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete voice');
  },
  async getStats() {
    const res = await fetch('/api/voices/stats');
    return res.json();
  }
};

// ─── STATE & SETTINGS ─────────────────────────────────────────────────────

const State = {
  catalog: [],
  isBatch: false,
  isStreaming: false,
  settings: {
    format: localStorage.getItem('tts_format') || 'wav',
    autoplay: localStorage.getItem('tts_autoplay') !== 'false',
    playbackSpeed: parseFloat(localStorage.getItem('tts_playback_speed')) || 1.0,
  }
};

// ─── TAB ROUTER ────────────────────────────────────────────────────────────

function switchTab(tabId) {
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

  const navItem = document.querySelector(`.nav-item[data-tab="${tabId}"]`);
  const content = document.getElementById(`tab-${tabId}`);

  if (navItem) navItem.classList.add('active');
  if (content) content.classList.add('active');

  if (tabId === 'models') renderModels();
  if (tabId === 'library') {
    renderLibrary();
    renderDashboard();
  }
  if (tabId === 'director') {
    // any director init
  }
}

document.querySelectorAll('.nav-item[data-tab]').forEach(item => {
  item.addEventListener('click', (e) => {
    switchTab(e.currentTarget.dataset.tab);
  });
});

// ─── KEYBOARD SHORTCUTS ────────────────────────────────────────────────────

window.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
    if (e.ctrlKey && e.key === 'Enter') {
      e.preventDefault();
      document.getElementById('voice-form').requestSubmit();
    }
    return;
  }

  if (e.ctrlKey && e.key === '1') { e.preventDefault(); switchTab('studio'); }
  if (e.ctrlKey && e.key === '2') { e.preventDefault(); switchTab('models'); }
  if (e.ctrlKey && e.key === '3') { e.preventDefault(); switchTab('library'); }
  if (e.ctrlKey && e.key === '4') { e.preventDefault(); switchTab('cloning'); }

  if (e.key === '?') {
    e.preventDefault();
    document.getElementById('shortcuts-overlay').classList.add('open');
  }

  if (e.key === 'Escape') {
    e.preventDefault();
    document.getElementById('settings-overlay')?.classList.remove('open');
    document.getElementById('settings-drawer')?.classList.remove('open');
    document.getElementById('shortcuts-overlay')?.classList.remove('open');
  }

  if (e.key === ' ' || e.key === 'Spacebar') {
    e.preventDefault();
    if (currentAudio) {
      if (currentAudio.paused) currentAudio.play();
      else currentAudio.pause();
    }
  }

  if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 'd') {
    e.preventDefault();
    window.open('/docs', '_blank');
  }
});

// ─── STUDIO LOGIC ──────────────────────────────────────────────────────────

const form = document.getElementById('voice-form');
const textInput = document.getElementById('text');
const modelSelect = document.getElementById('model-id');
const voiceSelect = document.getElementById('voice-id');
const langSelect = document.getElementById('language');
const modeSelect = document.getElementById('voice-mode');
const autoHint = document.getElementById('auto-hint');
const generateBtn = document.getElementById('generate-btn');
const studioWaveform = document.getElementById('studio-waveform');
const speedInput = document.getElementById('speed');
const pitchInput = document.getElementById('pitch');
const speedVal = document.getElementById('speed-val');
const pitchVal = document.getElementById('pitch-val');
const batchSwitch = document.getElementById('batch-switch');
const streamSwitch = document.getElementById('stream-switch');
const batchHint = document.getElementById('batch-hint');
const charCount = document.getElementById('char-count');
const charBarFill = document.getElementById('char-bar-fill');

async function initStudio() {
  State.catalog = await API.getCatalog();
  filterModelsByMode();
  updateRecommendation();
  updateLibraryBadge();
}

function filterModelsByMode() {
  const mode = modeSelect.value;
  modelSelect.innerHTML = '<option value="">Auto Select (Recommended)</option>';
  
  State.catalog.filter(m => m.is_installed).forEach(m => {
    if (mode !== 'all' && (!m.use_cases || !m.use_cases.includes(mode))) return;
    const opt = document.createElement('option');
    opt.value = m.model_id;
    opt.textContent = m.display_name;
    modelSelect.appendChild(opt);
  });
}

modeSelect.addEventListener('change', () => {
  filterModelsByMode();
  updateRecommendation();
});

async function updateRecommendation() {
  const barkHint = document.getElementById('bark-hint');
  
  if (modelSelect.value !== '') {
    autoHint.textContent = '';
    
    // Show bark hint if Bark is selected
    if (modelSelect.value.includes('bark')) {
      barkHint.style.display = 'block';
    } else {
      barkHint.style.display = 'none';
    }
    
    loadVoicesForModel(modelSelect.value);
    return;
  }
  
  barkHint.style.display = 'none';
  const text = textInput.value || 'Hello';
  const lang = langSelect.value;
  try {
    const modelId = await API.recommend(text, lang);
    const m = State.catalog.find(c => c.model_id === modelId);
    autoHint.textContent = `Auto choice: ${m ? m.display_name : modelId}`;
  } catch (e) {
    autoHint.textContent = '';
  }
}

async function loadVoicesForModel(modelId) {
  voiceSelect.innerHTML = '<option value="auto">Default Persona</option>';
  if (!modelId) return;
  const voices = await API.getModelVoices(modelId);
  voices.forEach(v => {
    const opt = document.createElement('option');
    opt.value = v.id;
    opt.textContent = v.name;
    voiceSelect.appendChild(opt);
  });
}

// Event Listeners for Studio Controls
speedInput.addEventListener('input', (e) => {
  speedVal.textContent = `${parseFloat(e.target.value).toFixed(2)}x`;
});

pitchInput.addEventListener('input', (e) => {
  const val = parseInt(e.target.value);
  pitchVal.textContent = val >= 0 ? `+${val} Hz` : `${val} Hz`;
});

textInput.addEventListener('input', () => {
  const len = textInput.value.length;
  charCount.textContent = `${len} / 5000 chars`;
  const pct = Math.min(100, (len / 5000) * 100);
  charBarFill.style.width = `${pct}%`;

  if (pct > 90) charBarFill.className = 'char-bar-fill over';
  else if (pct > 75) charBarFill.className = 'char-bar-fill warn';
  else charBarFill.className = 'char-bar-fill';

  if (modelSelect.value === '') updateRecommendation();
});

langSelect.addEventListener('change', updateRecommendation);
modelSelect.addEventListener('change', updateRecommendation);

// Batch Mode Switch
batchSwitch.addEventListener('click', () => {
  State.isBatch = !State.isBatch;
  batchSwitch.classList.toggle('active', State.isBatch);
  document.getElementById('batch-hint').style.display = State.isBatch ? 'block' : 'none';
  document.getElementById('text-label').childNodes[0].textContent = State.isBatch ? 'Batch Lines ' : 'Text Prompt ';
  
  if (State.isBatch && State.isStreaming) {
    State.isStreaming = false;
    streamSwitch.classList.remove('active');
  }
});

streamSwitch.addEventListener('click', () => {
  State.isStreaming = !State.isStreaming;
  streamSwitch.classList.toggle('active', State.isStreaming);
  
  if (State.isStreaming && State.isBatch) {
    State.isBatch = false;
    batchSwitch.classList.remove('active');
    document.getElementById('batch-hint').style.display = 'none';
    document.getElementById('text-label').childNodes[0].textContent = 'Text Prompt ';
  }
});

// Form Submission
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  generateBtn.disabled = true;
  studioWaveform.style.display = 'flex';
  studioWaveform.classList.add('active');

  const text = textInput.value.trim();
  if (!text) return;

  const reverb = document.getElementById('effect-reverb')?.classList.contains('active') || false;
  const compressor = document.getElementById('effect-compressor')?.classList.contains('active') || false;
  const eq = document.getElementById('effect-eq')?.classList.contains('active') || false;

  const basePayload = {
    voice_name: document.getElementById('voice-name').value,
    language: langSelect.value,
    model_id: modelSelect.value || null,
    voice_id: voiceSelect.value,
    speed: parseFloat(speedInput.value),
    pitch: parseFloat(pitchInput.value),
    output_format: State.settings.format,
    style: typeof selectedStyle !== 'undefined' ? selectedStyle : 'neutral',
    smart_style: document.getElementById('smart-style')?.classList.contains('active') || false,
    chunking_strategy: document.getElementById('chunking-strategy')?.value || 'standard',
    effects: { reverb, compressor, eq }
  };

  try {
    if (State.isStreaming) {
      // Connect to WebSocket and stream audio
      generateBtn.disabled = true;
      Toast.show('Starting stream...');
      await playAudioStream({ ...basePayload, text });
      Toast.show('Stream finished!');
      return; // We don't switch to library tab for streams
    } else if (State.isBatch) {
      const lines = text.split('\n').map(l => l.trim()).filter(l => l.length > 0);
      if (lines.length === 0) throw new Error('No valid text lines found');
      const res = await API.createBatch({ ...basePayload, texts: lines });
      Toast.show(`Generated ${res.generated} audio clips!`);
    } else {
      const result = await API.createVoice({ ...basePayload, text });
      if (State.settings.autoplay && result.id) {
        const audio = new Audio(`/api/voices/${result.id}/audio`);
        audio.play().catch(() => {});
      }
      Toast.show('Audio generated successfully!');
    }

    updateLibraryBadge();
    switchTab('library');
  } catch (err) {
    Toast.show(err.message, 'error');
  } finally {
    generateBtn.disabled = false;
    studioWaveform.style.display = 'none';
    studioWaveform.classList.remove('active');
  }
});

// --- Stream Playback Logic ---
async function playAudioStream(payload) {
  return new Promise((resolve, reject) => {
    const wsUrl = (window.location.protocol === 'https:' ? 'wss:' : 'ws:') + '//' + window.location.host + '/api/stream';
    const ws = new WebSocket(wsUrl);
    
    // Web Audio API context
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    let nextStartTime = audioCtx.currentTime;
    let chunksReceived = 0;
    
    ws.onopen = () => {
      ws.send(JSON.stringify(payload));
    };
    
    ws.onmessage = async (event) => {
      if (typeof event.data === 'string') {
        const msg = JSON.parse(event.data);
        if (msg.type === 'error') {
          ws.close();
          reject(new Error(msg.message));
        } else if (msg.type === 'done') {
          ws.close();
          // Wait for all audio to finish playing if needed, but we'll just resolve here
          setTimeout(resolve, 1000); 
        }
      } else {
        // We received binary WAV data
        chunksReceived++;
        try {
          const arrayBuffer = await event.data.arrayBuffer();
          const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
          
          const source = audioCtx.createBufferSource();
          source.buffer = audioBuffer;
          source.playbackRate.value = State.settings.playbackSpeed;
          source.connect(audioCtx.destination);
          
          if (nextStartTime < audioCtx.currentTime) {
             nextStartTime = audioCtx.currentTime;
          }
          source.start(nextStartTime);
          nextStartTime += audioBuffer.duration / State.settings.playbackSpeed;
        } catch (e) {
          console.error("Error decoding audio chunk:", e);
        }
      }
    };
    
    ws.onerror = (e) => {
      ws.close();
      reject(new Error("WebSocket error"));
    };
  });
}

// ─── MODELS LOGIC ──────────────────────────────────────────────────────────

async function renderModels() {
  State.catalog = await API.getCatalog();
  const grid = document.getElementById('models-grid');
  grid.innerHTML = '';

  State.catalog.forEach(model => {
    const card = document.createElement('div');
    card.className = 'model-card glass';

    let badge = '<span class="badge badge-default">Not Downloaded</span>';
    let btnHtml = `<button class="btn btn-secondary download-btn" data-id="${model.model_id}">Download Model</button>`;

    if (model.is_cloud) {
      badge = '<span class="badge badge-cloud">Cloud Engine</span>';
      btnHtml = '<button class="btn btn-ghost" disabled>Cloud Available</button>';
    } else if (model.is_installed) {
      badge = '<span class="badge badge-installed">Ready</span>';
      btnHtml = '<button class="btn btn-ghost" disabled style="color:var(--success)">Installed</button>';
    } else if (model.is_downloading) {
      badge = '<span class="badge badge-downloading">Downloading...</span>';
      btnHtml = `
        <div style="width:100%">
          <div class="progress-bar">
            <div class="progress-bar-fill" id="prog-fill-${model.model_id}" style="width: 0%;"></div>
          </div>
          <div class="progress-info">
            <span id="prog-txt-${model.model_id}">0 MB</span>
            <span id="prog-pct-${model.model_id}">0%</span>
          </div>
        </div>
      `;
    }

    card.innerHTML = `
      <div class="model-header">
        <div>
          <div class="model-title">${model.display_name}</div>
          <div class="model-engine">engine: ${model.engine} · ${model.size_mb} MB</div>
        </div>
        ${badge}
      </div>
      <div class="model-desc">${model.description}</div>
      <div class="model-tags">
        ${model.languages.map(l => `<span class="model-tag">${l.toUpperCase()}</span>`).join('')}
        ${(model.use_cases || []).map(u => `<span class="model-tag use-case">${u}</span>`).join('')}
        <span class="model-tag">Score: ${model.quality_score}</span>
      </div>
      <div class="model-footer">${btnHtml}</div>
    `;
    grid.appendChild(card);
  });

  document.querySelectorAll('.download-btn').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const id = e.target.dataset.id;
      e.target.disabled = true;
      try {
        await API.startDownload(id);
        renderModels();
        startSSEProgress(id);
      } catch (err) {
        Toast.show(err.message, 'error');
        e.target.disabled = false;
      }
    });
  });
}

function startSSEProgress(modelId) {
  const evtSource = new EventSource(`/api/models/download/${modelId}/progress`);
  evtSource.onmessage = function (event) {
    if (event.data === ': keepalive') return;
    const msg = JSON.parse(event.data);

    if (msg.event === 'download_progress') {
      const fill = document.getElementById(`prog-fill-${modelId}`);
      const txt = document.getElementById(`prog-txt-${modelId}`);
      const pct = document.getElementById(`prog-pct-${modelId}`);

      if (fill && pct) {
        const p = Math.round(msg.progress * 100);
        fill.style.width = `${p}%`;
        pct.textContent = `${p}%`;
        if (txt) txt.textContent = `${msg.mb_received} / ${msg.mb_total} MB`;
      }
    } else if (msg.event === 'download_complete') {
      Toast.show(`Model ${modelId} installed!`);
      evtSource.close();
      renderModels();
      initStudio();
    } else if (msg.event === 'download_error') {
      Toast.show(`Error: ${msg.error}`, 'error');
      evtSource.close();
      renderModels();
    }
  };
}

// ─── LIBRARY LOGIC ─────────────────────────────────────────────────────────

let currentAudio = null;
let currentWaveform = null;

let libraryPage = 0;
const PAGE_SIZE = 20;

async function renderLibrary() {
  const q = document.getElementById('library-search').value;
  const model = document.getElementById('filter-model').value;
  const lang = document.getElementById('filter-lang').value;
  
  const filterModel = document.getElementById('filter-model');
  if (filterModel && filterModel.options.length <= 1) {
      const catalog = await API.getCatalog();
      catalog.filter(m => m.is_installed).forEach(m => {
          const opt = document.createElement('option');
          opt.value = m.model_id;
          opt.textContent = m.display_name;
          filterModel.appendChild(opt);
      });
  }

  const offset = libraryPage * PAGE_SIZE;
  const data = await API.searchVoices(q, model, lang);
  const list = document.getElementById('library-list');
  list.innerHTML = '';

  const total = data.voices.length;
  const paginatedVoices = data.voices.slice(offset, offset + PAGE_SIZE);

  if (total === 0) {
    list.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🎙️</div>
        <h4>No audio clips found</h4>
        <p>Synthesize text in the Studio tab to see your generated voices here.</p>
      </div>
    `;
    document.getElementById('library-pagination').innerHTML = '';
    return;
  }

  paginatedVoices.forEach(voice => {
    const card = document.createElement('div');
    card.className = 'voice-card glass';
    
    let durationHtml = '';
    if (voice.duration) {
      durationHtml = `<span class="voice-meta-item">⏱️ ${formatDuration(voice.duration)}</span>`;
    }

    card.innerHTML = `
      <div class="voice-row-top">
        <div class="voice-title">
          <button class="favorite-btn ${isFavorite(voice.id) ? 'active' : ''}" data-id="${voice.id}">★</button>
          ${voice.voice_name}
        </div>
        <div class="voice-meta">
          <span class="voice-meta-item">🤖 ${voice.model_id}</span>
          <span class="voice-meta-item">🗣️ ${voice.language.toUpperCase()}</span>
          <span class="voice-meta-item">⚡ ${voice.speed}x</span>
          ${durationHtml}
          <span class="voice-meta-item">📅 ${new Date(voice.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
        </div>
      </div>
      <div class="voice-text">"${voice.text}"</div>
      <div class="voice-controls">
        <button class="btn-icon play play-btn" data-url="/api/voices/${voice.id}/audio" data-id="${voice.id}">
          <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
        </button>
        <canvas class="waveform-canvas" id="wf-${voice.id}" width="400" height="60" style="display:none;"></canvas>
        <div class="waveform" id="wf-anim-${voice.id}">
          <div class="waveform-bar"></div><div class="waveform-bar"></div>
          <div class="waveform-bar"></div><div class="waveform-bar"></div>
          <div class="waveform-bar"></div><div class="waveform-bar"></div>
          <div class="waveform-bar"></div><div class="waveform-bar"></div>
        </div>
        <a href="/api/voices/${voice.id}/audio" download="${voice.voice_name}.${voice.output_format}" class="btn-icon">
          <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
        </a>
        <button class="btn-icon danger del-btn" data-id="${voice.id}">
          <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
        </button>
      </div>
    `;
    list.appendChild(card);
  });

  // Attach favorite handlers
  document.querySelectorAll('.favorite-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const id = e.currentTarget.dataset.id;
      toggleFavorite(id);
      e.currentTarget.classList.toggle('active', isFavorite(id));
    });
  });

  // Attach playback handlers
  let activeVisualizer = null;
  document.querySelectorAll('.play-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const url = e.currentTarget.dataset.url;
      const wfCanvas = document.getElementById(`wf-${e.currentTarget.dataset.id}`);
      const wfAnim = document.getElementById(`wf-anim-${e.currentTarget.dataset.id}`);

      if (currentAudio) {
        currentAudio.pause();
        if (currentWaveform) {
            currentWaveform.style.display = 'none';
        }
        if (activeVisualizer) activeVisualizer.stop();
        document.querySelectorAll('.waveform-canvas').forEach(c => c.style.display = 'none');
        document.querySelectorAll('.spectrogram-canvas').forEach(c => c.style.display = 'none');
        document.querySelectorAll('.waveform').forEach(c => c.classList.remove('active'));
      }

      currentAudio = new Audio(url);
      currentAudio.crossOrigin = "anonymous";
      currentAudio.playbackRate = State.settings.playbackSpeed || 1.0;
      
      if (wfAnim) wfAnim.style.display = 'none';
      wfCanvas.style.display = 'block';
      currentWaveform = wfCanvas;

      const specCanvas = document.getElementById(`spec-${e.currentTarget.dataset.id}`);
      if (specCanvas) specCanvas.style.display = 'block';

      activeVisualizer = new WaveformVisualizer(wfCanvas, specCanvas);
      activeVisualizer.connectAudio(currentAudio);
      
      currentAudio.play();

      currentAudio.onended = () => {
        wfCanvas.style.display = 'none';
        if (specCanvas) specCanvas.style.display = 'none';
        activeVisualizer.stop();
      };
    });
  });

  // Attach delete handlers
  document.querySelectorAll('.del-btn').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const id = e.currentTarget.dataset.id;
      if (confirm('Delete this audio clip permanently?')) {
        await API.deleteVoice(id);
        Toast.show('Clip deleted');
        renderLibrary();
        updateLibraryBadge();
      }
    });
  });
  
  renderPagination(total, libraryPage);
}

function renderPagination(total, currentPage) {
  const container = document.getElementById('library-pagination');
  if (!container) return;
  const totalPages = Math.ceil(total / PAGE_SIZE);
  if (totalPages <= 1) { container.innerHTML = ''; return; }
  let html = `<button class="pagination-btn" ${currentPage === 0 ? 'disabled' : ''} onclick="goToPage(${currentPage - 1})">← Prev</button>`;
  html += `<span class="pagination-info">Page ${currentPage + 1} of ${totalPages}</span>`;
  html += `<button class="pagination-btn" ${currentPage >= totalPages - 1 ? 'disabled' : ''} onclick="goToPage(${currentPage + 1})">Next →</button>`;
  container.innerHTML = html;
}

window.goToPage = (page) => {
  libraryPage = page;
  renderLibrary();
}

// Search & Filter input debouncing
let searchTimeout;
document.getElementById('library-search').addEventListener('input', () => {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(renderLibrary, 250);
});
document.getElementById('filter-model').addEventListener('change', renderLibrary);
document.getElementById('filter-lang').addEventListener('change', renderLibrary);

async function updateLibraryBadge() {
  const data = await API.getVoices(0, 1);
  document.getElementById('library-count-badge').textContent = data.total || 0;
}

// ─── DASHBOARD LOGIC ───────────────────────────────────────────────────────

async function renderDashboard() {
  const stats = await API.getStats();

  const elVoices = document.getElementById('stat-total-voices');
  const elDuration = document.getElementById('stat-total-duration');
  const elDisk = document.getElementById('stat-disk-usage');
  
  if (elVoices) elVoices.textContent = stats.total_voices;
  if (elDuration) elDuration.textContent = `${stats.total_duration_sec}s`;
  if (elDisk) elDisk.textContent = `${stats.disk.audio_mb} MB`;
}

// ─── CLONING TAB LOGIC ─────────────────────────────────────────────────────

const uploadZone = document.getElementById('upload-zone');
const cloneAudio = document.getElementById('clone-audio');
const uploadText = document.getElementById('upload-text');
const cloneForm = document.getElementById('clone-form');
const cloneBtn = document.getElementById('clone-btn');
const cloneWaveform = document.getElementById('clone-waveform');

uploadZone.addEventListener('click', () => cloneAudio.click());

['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
  uploadZone.addEventListener(eventName, preventDefaults, false);
});

function preventDefaults(e) {
  e.preventDefault();
  e.stopPropagation();
}

['dragenter', 'dragover'].forEach(eventName => {
  uploadZone.addEventListener(eventName, () => uploadZone.classList.add('dragover'), false);
});

['dragleave', 'drop'].forEach(eventName => {
  uploadZone.addEventListener(eventName, () => uploadZone.classList.remove('dragover'), false);
});

uploadZone.addEventListener('drop', (e) => {
  let dt = e.dataTransfer;
  let files = dt.files;
  if (files.length) {
    cloneAudio.files = files;
    uploadText.textContent = files[0].name;
  }
});

cloneAudio.addEventListener('change', (e) => {
  if (e.target.files.length) {
    uploadText.textContent = e.target.files[0].name;
  }
});

cloneForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  
  if (!cloneAudio.files.length) {
    Toast.show('Please upload an audio sample first.', 'error');
    return;
  }

  cloneBtn.disabled = true;
  cloneWaveform.style.display = 'flex';
  cloneWaveform.classList.add('active');

  try {
    const formData = new FormData(cloneForm);
    await API.cloneVoice(formData);
    Toast.show('Voice successfully cloned and synthesized!');
    updateLibraryBadge();
    switchTab('library');
  } catch (err) {
    Toast.show(err.message, 'error');
  } finally {
    cloneBtn.disabled = false;
    cloneWaveform.style.display = 'none';
    cloneWaveform.classList.remove('active');
  }
});

// ─── SETTINGS DRAWER ───────────────────────────────────────────────────────

const settingsOverlay = document.getElementById('settings-overlay');
const settingsDrawer = document.getElementById('settings-drawer');
const settingFormat = document.getElementById('setting-format');
const settingAutoplay = document.getElementById('setting-autoplay');
const settingPlaybackSpeed = document.getElementById('setting-playback-speed');
const settingPlaybackSpeedVal = document.getElementById('setting-playback-speed-val');

document.getElementById('open-settings').addEventListener('click', () => {
  settingsOverlay.classList.add('open');
  settingsDrawer.classList.add('open');
});

document.getElementById('close-settings').addEventListener('click', closeSettings);
settingsOverlay.addEventListener('click', closeSettings);

function closeSettings() {
  settingsOverlay.classList.remove('open');
  settingsDrawer.classList.remove('open');
}

settingAutoplay.value = State.settings.autoplay.toString();

settingAutoplay.addEventListener('change', (e) => {
  State.settings.autoplay = e.target.value === 'true';
  localStorage.setItem('tts_autoplay', e.target.value);
});

if (settingPlaybackSpeed) {
  settingPlaybackSpeed.value = State.settings.playbackSpeed;
  settingPlaybackSpeedVal.textContent = State.settings.playbackSpeed.toFixed(1) + 'x';
  
  settingPlaybackSpeed.addEventListener('input', (e) => {
    const val = parseFloat(e.target.value);
    State.settings.playbackSpeed = val;
    localStorage.setItem('tts_playback_speed', val.toString());
    settingPlaybackSpeedVal.textContent = val.toFixed(1) + 'x';
    
    if (currentAudio) {
      currentAudio.playbackRate = val;
    }
  });
}

// Shortcuts overlay
document.getElementById('open-shortcuts').addEventListener('click', () => {
  document.getElementById('shortcuts-overlay').classList.add('open');
});
document.getElementById('close-shortcuts').addEventListener('click', () => {
  document.getElementById('shortcuts-overlay').classList.remove('open');
});

// ─── INIT ──────────────────────────────────────────────────────────────────

(function() {
  const saved = localStorage.getItem('tts_theme') || 'default';
  if (saved && saved !== 'default') {
    document.documentElement.setAttribute('data-theme', saved);
  }
})();

initStudio();
initThemes();
initStyles();
initFormatOptions();

// ─── BATCH DOCUMENT UPLOAD ──────────────────────────────────────────────────

const documentUpload = document.getElementById('document-upload');
const batchContainer = document.getElementById('batch-progress-container');
const batchProgressFill = document.getElementById('batch-progress-fill');
const batchProgressText = document.getElementById('batch-progress-text');
const batchActionContainer = document.getElementById('batch-action-container');
const batchErrorText = document.getElementById('batch-error-text');

let currentBatchJobId = null;
let batchPollInterval = null;

if(documentUpload) {
  documentUpload.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // Build form data
    const formData = new FormData();
    formData.append('file', file);
    formData.append('voice_name', document.getElementById('voice-name').value || 'Document Audio');
    formData.append('language', document.getElementById('language').value);
    formData.append('style', 'neutral');
    formData.append('speed', document.getElementById('speed').value);
    formData.append('pitch', document.getElementById('pitch').value);
    formData.append('chunking_strategy', document.getElementById('chunking-strategy').value || 'standard');
    
    const mId = document.getElementById('model-id').value;
    if(mId) formData.append('model_id', mId);
    
    const vId = document.getElementById('voice-id').value;
    if(vId && vId !== 'auto') formData.append('voice_id', vId);

    // Show Progress UI
    batchContainer.style.display = 'block';
    batchActionContainer.style.display = 'none';
    batchProgressFill.style.width = '0%';
    batchProgressText.textContent = `Uploading ${file.name}...`;

    try {
      const res = await fetch('/api/voice/document', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      
      if (!res.ok) throw new Error(data.detail || 'Upload failed');
      
      currentBatchJobId = data.job_id;
      startPollingBatchJob();
      
    } catch(err) {
      Toast.show(err.message, 'error');
      batchContainer.style.display = 'none';
    } finally {
      documentUpload.value = ''; // Reset
    }
  });
}

// ─── NEW PHASE 2/3 FEATURES ────────────────────────────────────────────────

// Toggle switch logic
document.querySelectorAll('.toggle-switch').forEach(ts => {
  ts.addEventListener('click', () => ts.classList.toggle('active'));
});

// Director Tab Logic
const characterList = document.getElementById('character-list');

document.getElementById('add-character-btn')?.addEventListener('click', async () => {
  const charDiv = document.createElement('div');
  charDiv.className = 'form-group glass';
  charDiv.style.padding = '12px';
  charDiv.style.marginBottom = '8px';
  charDiv.style.border = '1px solid var(--panel-border)';
  
  const nameInput = document.createElement('input');
  nameInput.type = 'text';
  nameInput.placeholder = 'Character Name (e.g. ALICE)';
  nameInput.style.marginBottom = '8px';
  nameInput.className = 'char-name-input';
  
  const modelSelect = document.createElement('select');
  modelSelect.style.marginBottom = '8px';
  modelSelect.innerHTML = '<option value="">Select Engine...</option>';
  State.catalog.filter(m => m.is_installed).forEach(m => {
    const opt = document.createElement('option');
    opt.value = m.model_id;
    opt.textContent = m.display_name;
    modelSelect.appendChild(opt);
  });
  
  const voiceSelect = document.createElement('select');
  voiceSelect.innerHTML = '<option value="">Select Voice...</option>';
  voiceSelect.className = 'char-voice-input';
  
  modelSelect.addEventListener('change', async () => {
    voiceSelect.innerHTML = '<option value="">Loading...</option>';
    const voices = await API.getModelVoices(modelSelect.value);
    voiceSelect.innerHTML = '<option value="">Select Voice...</option>';
    voices.forEach(v => {
      const opt = document.createElement('option');
      opt.value = v.id;
      opt.textContent = v.name;
      voiceSelect.appendChild(opt);
    });
  });
  
  const removeBtn = document.createElement('button');
  removeBtn.textContent = 'Remove';
  removeBtn.className = 'btn btn-secondary btn-sm';
  removeBtn.style.marginTop = '8px';
  removeBtn.onclick = () => charDiv.remove();
  
  charDiv.appendChild(nameInput);
  charDiv.appendChild(modelSelect);
  charDiv.appendChild(voiceSelect);
  charDiv.appendChild(removeBtn);
  
  characterList.appendChild(charDiv);
});

document.getElementById('generate-scene-btn')?.addEventListener('click', async () => {
  const charInputs = document.querySelectorAll('.char-name-input');
  const voiceInputs = document.querySelectorAll('.char-voice-input');
  
  const characters = {};
  for(let i = 0; i < charInputs.length; i++) {
    const name = charInputs[i].value.trim();
    const voice = voiceInputs[i].value;
    if(name && voice) characters[name] = voice;
  }
  
  const script = document.getElementById('director-script').value.trim();
  if(!script) return Toast.show('Script is empty', 'error');
  
  const generateBtn = document.getElementById('generate-scene-btn');
  generateBtn.disabled = true;
  generateBtn.textContent = 'Generating...';
  document.getElementById('director-waveform').style.display = 'flex';
  
  try {
    const res = await fetch('/api/voice/scene', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ characters, script })
    });
    if(!res.ok) {
        let msg = 'Failed';
        try { const err = await res.json(); msg = err.detail || msg; } catch(e){}
        throw new Error(msg);
    }
    const data = await res.json();
    Toast.show('Scene generated successfully!');
    if(State.settings.autoplay && data.id) {
        const audio = new Audio(`/api/voices/${data.id}/audio`);
        audio.play().catch(() => {});
    }
    updateLibraryBadge();
    switchTab('library');
  } catch (err) {
    Toast.show(err.message, 'error');
  } finally {
    generateBtn.disabled = false;
    generateBtn.innerHTML = '<span>Generate Scene</span>';
    document.getElementById('director-waveform').style.display = 'none';
  }
});

// RSS Podcast Generator Logic
document.getElementById('rss-generate-btn')?.addEventListener('click', async () => {
  const url = document.getElementById('rss-url').value.trim();
  if(!url) return Toast.show('Enter RSS URL', 'error');
  
  const btn = document.getElementById('rss-generate-btn');
  btn.disabled = true;
  btn.textContent = 'Starting...';
  
  try {
    const summarize_content = document.getElementById('rss-summarize')?.checked || false;
    const res = await fetch('/api/voice/rss', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ url, summarize_content })
    });
    if(!res.ok) {
        let msg = 'Failed';
        try { const err = await res.json(); msg = err.detail || msg; } catch(e){}
        throw new Error(msg);
    }
    Toast.show('RSS Podcast generation started!');
    renderLibrary();
    updateLibraryBadge();
  } catch(err) {
    Toast.show(err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'RSS Podcast';
  }
});

function startPollingBatchJob() {
  if(batchPollInterval) clearInterval(batchPollInterval);
  
  batchPollInterval = setInterval(async () => {
    if(!currentBatchJobId) {
      clearInterval(batchPollInterval);
      return;
    }
    
    try {
      const res = await fetch(`/api/voice/document/${currentBatchJobId}/progress`);
      const data = await res.json();
      
      if(data.status === 'not_found') {
        clearInterval(batchPollInterval);
        batchContainer.style.display = 'none';
        return;
      }
      
      batchProgressFill.style.width = `${data.progress_percent || 0}%`;
      
      if(data.status === 'running' || data.status === 'queued') {
        batchProgressText.textContent = `Generating Chunk ${data.chunks_completed || 0} of ${data.total_chunks || '...'}`;
        batchActionContainer.style.display = 'none';
      } 
      else if(data.status === 'merging') {
        batchProgressText.textContent = `Merging audio chunks...`;
      }
      else if(data.status === 'completed') {
        clearInterval(batchPollInterval);
        batchProgressText.textContent = `Completed successfully!`;
        batchProgressFill.style.width = `100%`;
        setTimeout(() => { batchContainer.style.display = 'none'; }, 3000);
        renderLibrary();
        updateLibraryBadge();
        Toast.show('Document audio generated successfully!');
      }
      else if(data.status === 'requires_action') {
        batchProgressText.textContent = `Error on chunk ${data.failed_chunk_idx || '?'}`;
        batchErrorText.textContent = data.error || 'Unknown error';
        batchActionContainer.style.display = 'flex';
      }
      else if(data.status === 'cancelled' || data.status === 'error') {
        clearInterval(batchPollInterval);
        batchProgressText.textContent = `Job ${data.status}`;
        setTimeout(() => { batchContainer.style.display = 'none'; }, 3000);
      }
      
    } catch(err) {
      console.error("Failed to poll batch job", err);
    }
  }, 2000);
}

document.getElementById('btn-batch-retry')?.addEventListener('click', () => sendBatchAction('retry'));
document.getElementById('btn-batch-skip')?.addEventListener('click', () => sendBatchAction('skip'));
document.getElementById('btn-batch-cancel')?.addEventListener('click', () => sendBatchAction('cancel'));

async function sendBatchAction(action) {
  if(!currentBatchJobId) return;
  batchActionContainer.style.display = 'none';
  batchProgressText.textContent = `Sending ${action} command...`;
  await fetch(`/api/voice/document/${currentBatchJobId}/action`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({action})
  });
}

// ─── NEW FEATURES ────────────────────────────────────────────────────────

const THEMES = [
  { id: 'default', name: 'Indigo Night', colors: ['#050507', '#6366f1', '#d946ef'] },
  { id: 'gruvbox', name: 'Gruvbox', colors: ['#1d2021', '#d79921', '#b8bb26'] },
  { id: 'tokyo-night', name: 'Tokyo Night', colors: ['#1a1b26', '#7aa2f7', '#bb9af7'] },
  { id: 'nord', name: 'Nord', colors: ['#2e3440', '#88c0d0', '#b48ead'] },
  { id: 'dark-nord', name: 'Dark Nord', colors: ['#1c1f26', '#81a1c1', '#b48ead'] },
  { id: 'dracula', name: 'Dracula', colors: ['#282a36', '#bd93f9', '#ff79c6'] },
  { id: 'retro', name: 'Retro Amber', colors: ['#0a0a0a', '#ffb000', '#ff6600'] },
  { id: 'catppuccin', name: 'Catppuccin', colors: ['#1e1e2e', '#89b4fa', '#f5c2e7'] },
];

function initThemes() {
  const saved = localStorage.getItem('tts_theme') || 'default';
  applyTheme(saved);
  const grid = document.getElementById('theme-grid');
  if (!grid) return;
  grid.innerHTML = '';
  THEMES.forEach(t => {
    const swatch = document.createElement('div');
    swatch.className = `theme-swatch ${t.id === saved ? 'active' : ''}`;
    swatch.style.background = `linear-gradient(135deg, ${t.colors[0]}, ${t.colors[1]}, ${t.colors[2]})`;
    swatch.dataset.theme = t.id;
    swatch.innerHTML = `<span class="theme-swatch-label">${t.name}</span>`;
    swatch.addEventListener('click', () => {
      applyTheme(t.id);
      grid.querySelectorAll('.theme-swatch').forEach(s => s.classList.remove('active'));
      swatch.classList.add('active');
    });
    grid.appendChild(swatch);
  });
}

function applyTheme(themeId) {
  document.documentElement.setAttribute('data-theme', themeId === 'default' ? '' : themeId);
  localStorage.setItem('tts_theme', themeId);
}

let selectedStyle = 'neutral';

async function initStyles() {
  try {
    const res = await fetch('/api/styles');
    const data = await res.json();
    const emotionalContainer = document.getElementById('emotional-styles');
    const readingContainer = document.getElementById('reading-styles');
    if (!emotionalContainer || !readingContainer) return;
    emotionalContainer.innerHTML = '';
    readingContainer.innerHTML = '';
    data.styles.forEach(s => {
      const pill = document.createElement('button');
      pill.type = 'button';
      pill.className = `style-pill ${s.category} ${s.id === selectedStyle ? 'active' : ''}`;
      pill.textContent = s.name;
      pill.dataset.style = s.id;
      pill.addEventListener('click', () => {
        selectedStyle = s.id;
        document.querySelectorAll('.style-pill').forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
      });
      if (s.category === 'emotional') emotionalContainer.appendChild(pill);
      else readingContainer.appendChild(pill);
    });
  } catch (e) {
    console.warn('Could not load styles:', e);
  }
}

const FORMATS = ['wav', 'mp3', 'ogg', 'flac'];

function initFormatOptions() {
  const container = document.getElementById('format-options');
  if (!container) return;
  container.innerHTML = '';
  FORMATS.forEach(fmt => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = `format-option ${fmt === State.settings.format ? 'active' : ''}`;
    btn.textContent = fmt.toUpperCase();
    btn.addEventListener('click', () => {
      State.settings.format = fmt;
      localStorage.setItem('tts_format', fmt);
      container.querySelectorAll('.format-option').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const formatTag = document.getElementById('format-tag');
      if (formatTag) formatTag.textContent = fmt.toUpperCase();
    });
    container.appendChild(btn);
  });
}

class WaveformVisualizer {
  constructor(canvasOrContainer, spectrogramCanvas = null) {
    this.ctx = null;
    this.analyser = null;
    this.audioCtx = null;
    this.animId = null;
    this.specAnimId = null;
    this.canvas = canvasOrContainer;
    this.spectrogramCanvas = spectrogramCanvas;
  }

  connectAudio(audioElement) {
    if (!this.audioCtx) this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const src = this.audioCtx.createMediaElementSource(audioElement);
    this.analyser = this.audioCtx.createAnalyser();
    this.analyser.fftSize = 256;
    src.connect(this.analyser);
    this.analyser.connect(this.audioCtx.destination);
    this.draw();
    if (this.spectrogramCanvas) {
      this.drawSpectrogram();
    }
  }

  draw() {
    if (!this.analyser || !this.canvas) return;
    const ctx = this.canvas.getContext('2d');
    const bufferLength = this.analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    const W = this.canvas.width;
    const H = this.canvas.height;
    const barWidth = (W / bufferLength) * 2;

    const render = () => {
      this.animId = requestAnimationFrame(render);
      this.analyser.getByteFrequencyData(dataArray);
      ctx.clearRect(0, 0, W, H);
      const primaryColor = getComputedStyle(document.documentElement).getPropertyValue('--primary').trim() || '#6366f1';
      const accentColor = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#d946ef';
      let x = 0;
      for (let i = 0; i < bufferLength; i++) {
        const barHeight = (dataArray[i] / 255) * H;
        const gradient = ctx.createLinearGradient(0, H, 0, H - barHeight);
        gradient.addColorStop(0, primaryColor);
        gradient.addColorStop(1, accentColor);
        ctx.fillStyle = gradient;
        ctx.fillRect(x, H - barHeight, barWidth - 1, barHeight);
        x += barWidth;
      }
    };
    render();
  }

  drawSpectrogram() {
    if (!this.analyser || !this.spectrogramCanvas) return;
    const ctx = this.spectrogramCanvas.getContext('2d');
    const bufferLength = this.analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    const W = this.spectrogramCanvas.width;
    const H = this.spectrogramCanvas.height;

    // A separate canvas for shifting to prevent cumulative anti-aliasing issues
    const tempCanvas = document.createElement('canvas');
    tempCanvas.width = W;
    tempCanvas.height = H;
    const tempCtx = tempCanvas.getContext('2d', { willReadFrequently: true });
    
    // Primary/Accent for heat mapping
    const pColor = getComputedStyle(document.documentElement).getPropertyValue('--primary').trim() || '#6366f1';
    
    // parse color string to rgb roughly
    let rgb = [99, 102, 241];
    if (pColor.startsWith('#')) {
      const hex = pColor.replace('#', '');
      if (hex.length === 6) {
        rgb = [parseInt(hex.substring(0,2), 16), parseInt(hex.substring(2,4), 16), parseInt(hex.substring(4,6), 16)];
      }
    }

    const render = () => {
      this.specAnimId = requestAnimationFrame(render);
      this.analyser.getByteFrequencyData(dataArray);

      // Copy current frame to temp
      tempCtx.clearRect(0, 0, W, H);
      tempCtx.drawImage(this.spectrogramCanvas, 0, 0, W, H);

      // Clear main and draw temp shifted left by 1
      ctx.clearRect(0, 0, W, H);
      ctx.drawImage(tempCanvas, -1, 0, W, H);

      // Draw new column at W-1
      const colW = 1;
      const rowH = H / bufferLength;
      
      for (let i = 0; i < bufferLength; i++) {
        const val = dataArray[i]; // 0-255
        const intensity = val / 255;
        // Map intensity to opacity of primary color
        ctx.fillStyle = `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${intensity})`;
        // Invert Y axis
        ctx.fillRect(W - colW, H - (i * rowH) - rowH, colW, rowH);
      }
    };
    render();
  }

  stop() {
    if (this.animId) cancelAnimationFrame(this.animId);
    if (this.specAnimId) cancelAnimationFrame(this.specAnimId);
  }
}

function getFavorites() {
  try { return JSON.parse(localStorage.getItem('tts_favorites') || '[]'); }
  catch { return []; }
}
function toggleFavorite(voiceId) {
  const favs = getFavorites();
  const idx = favs.indexOf(voiceId);
  if (idx >= 0) favs.splice(idx, 1); else favs.push(voiceId);
  localStorage.setItem('tts_favorites', JSON.stringify(favs));
}
function isFavorite(voiceId) { return getFavorites().includes(voiceId); }

function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return '0s';
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function formatDurationLong(seconds) {
  if (!seconds || seconds <= 0) return '0s';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.round(seconds % 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

// --- UI INTERACTIONS & EASTER EGGS ---

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize Lucide Icons
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }

    // 2. Interactive Glow on Glass panels
    const glassPanels = document.querySelectorAll('.glass');
    glassPanels.forEach(panel => {
        panel.addEventListener('pointermove', (e) => {
            const rect = panel.getBoundingClientRect();
            const x = ((e.clientX - rect.left) / rect.width) * 100;
            const y = ((e.clientY - rect.top) / rect.height) * 100;
            panel.style.setProperty('--mouse-x', `${x}%`);
            panel.style.setProperty('--mouse-y', `${y}%`);
        });
    });

    // 3. Konami Code Easter Egg
    const konamiCode = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 'b', 'a'];
    let konamiIndex = 0;
    document.addEventListener('keydown', (e) => {
        if (e.key === konamiCode[konamiIndex]) {
            konamiIndex++;
            if (konamiIndex === konamiCode.length) {
                document.body.classList.toggle('easter-egg-active');
                konamiIndex = 0;
            }
        } else {
            konamiIndex = 0;
        }
    });

    // 4. Clickable Logo Easter Egg (5 clicks for confetti)
    const logo = document.querySelector('.page-header h2');
    let logoClicks = 0;
    if (logo) {
        logo.addEventListener('click', () => {
            logoClicks++;
            if (logoClicks >= 5) {
                spawnConfetti();
                logoClicks = 0;
            }
        });
    }

    function spawnConfetti() {
        for (let i = 0; i < 50; i++) {
            const conf = document.createElement('div');
            conf.classList.add('confetti');
            conf.style.left = Math.random() * 100 + 'vw';
            conf.style.backgroundColor = `hsl(${Math.random() * 360}, 100%, 60%)`;
            conf.style.animationDuration = (Math.random() * 2 + 1) + 's';
            document.body.appendChild(conf);
            setTimeout(() => conf.remove(), 3000);
        }
    }

    // 5. Waveform reacts to typing
    const textInput = document.getElementById('text');
    if (textInput && window.visualizer) {
        textInput.addEventListener('input', () => {
            if(window.visualizer.draw) {
                const dataArray = new Uint8Array(window.visualizer.bufferLength || 128);
                for(let i=0; i < dataArray.length; i++) {
                    dataArray[i] = 128 + (Math.random() * 50 - 25);
                }
                window.visualizer.draw(dataArray);
            }
        });
    }

    // 6. Fetch Recent Voices
    fetchRecentVoices();
});

async function fetchRecentVoices() {
    const grid = document.getElementById('recent-voices-grid');
    if (!grid) return;
    
    try {
        const res = await fetch('/api/voices?limit=6');
        const data = await res.json();
        
        if (!data.voices || data.voices.length === 0) {
            grid.innerHTML = '<div style="color: var(--text-tertiary); padding: 16px;">No recent generations found.</div>';
            return;
        }
        
        grid.innerHTML = '';
        data.voices.forEach(voice => {
            const card = document.createElement('div');
            card.className = 'glass recent-card';
            card.innerHTML = `
                <div class="recent-header">
                    <span class="badge badge-primary">${voice.model_id}</span>
                    <span style="font-size: 12px; color: var(--text-tertiary);">${new Date(voice.created_at).toLocaleDateString()}</span>
                </div>
                <div class="recent-prompt">"${voice.prompt_text || 'No prompt'}"</div>
                <div class="recent-actions">
                    <button class="btn btn-secondary btn-sm" onclick="playRecentAudio(this, '${voice.file_path}')" title="Play">
                        <i data-lucide="play" style="width: 14px; height: 14px;"></i>
                    </button>
                    <a class="btn btn-secondary btn-sm" href="/api/download?path=${encodeURIComponent(voice.file_path)}" title="Download">
                        <i data-lucide="download" style="width: 14px; height: 14px;"></i>
                    </a>
                </div>
            `;
            grid.appendChild(card);
        });
        
        if (typeof lucide !== 'undefined') lucide.createIcons();
        
        // Re-attach pointermove to newly created glass cards
        const newGlassPanels = grid.querySelectorAll('.glass');
        newGlassPanels.forEach(panel => {
            panel.addEventListener('pointermove', (e) => {
                const rect = panel.getBoundingClientRect();
                const x = ((e.clientX - rect.left) / rect.width) * 100;
                const y = ((e.clientY - rect.top) / rect.height) * 100;
                panel.style.setProperty('--mouse-x', `${x}%`);
                panel.style.setProperty('--mouse-y', `${y}%`);
            });
        });
        
    } catch (err) {
        console.error('Failed to fetch recent voices', err);
    }
}

window.playRecentAudio = function(btn, path) {
    const icon = btn.querySelector('i');
    if (window.recentAudio) {
        window.recentAudio.pause();
        if (window.recentPlayingBtn && window.recentPlayingBtn !== btn) {
            const oldIcon = window.recentPlayingBtn.querySelector('i');
            if (oldIcon && typeof lucide !== 'undefined') {
                oldIcon.setAttribute('data-lucide', 'play');
                lucide.createIcons();
            }
        }
    }
    
    if (window.recentPlayingBtn === btn && window.recentAudio && !window.recentAudio.paused) {
        // Just pause it
        if (icon && typeof lucide !== 'undefined') {
            icon.setAttribute('data-lucide', 'play');
            lucide.createIcons();
        }
        return;
    }
    
    window.recentAudio = new Audio(`/api/audio?path=${encodeURIComponent(path)}`);
    window.recentAudio.play();
    window.recentPlayingBtn = btn;
    
    if (icon && typeof lucide !== 'undefined') {
        icon.setAttribute('data-lucide', 'pause');
        lucide.createIcons();
    }
    
    window.recentAudio.onended = () => {
        if (icon && typeof lucide !== 'undefined') {
            icon.setAttribute('data-lucide', 'play');
            lucide.createIcons();
        }
        window.recentPlayingBtn = null;
    };
};
