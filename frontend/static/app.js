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
  settings: {
    format: localStorage.getItem('tts_format') || 'wav',
    autoplay: localStorage.getItem('tts_autoplay') !== 'false',
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
  if (tabId === 'library') renderLibrary();
  if (tabId === 'dashboard') renderDashboard();
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
  if (e.ctrlKey && e.key === '4') { e.preventDefault(); switchTab('dashboard'); }

  if (e.key === '?') {
    e.preventDefault();
    document.getElementById('shortcuts-overlay').classList.toggle('open');
  }
});

// ─── STUDIO LOGIC ──────────────────────────────────────────────────────────

const form = document.getElementById('voice-form');
const textInput = document.getElementById('text');
const modelSelect = document.getElementById('model-id');
const voiceSelect = document.getElementById('voice-id');
const langSelect = document.getElementById('language');
const autoHint = document.getElementById('auto-hint');
const generateBtn = document.getElementById('generate-btn');
const studioWaveform = document.getElementById('studio-waveform');
const speedInput = document.getElementById('speed');
const pitchInput = document.getElementById('pitch');
const speedVal = document.getElementById('speed-val');
const pitchVal = document.getElementById('pitch-val');
const charCount = document.getElementById('char-count');
const charBarFill = document.getElementById('char-bar-fill');
const batchSwitch = document.getElementById('batch-switch');

async function initStudio() {
  State.catalog = await API.getCatalog();

  // Populate models dropdown
  modelSelect.innerHTML = '<option value="">Auto Select (Recommended)</option>';
  State.catalog.filter(m => m.is_installed).forEach(m => {
    const opt = document.createElement('option');
    opt.value = m.model_id;
    opt.textContent = m.display_name;
    modelSelect.appendChild(opt);
  });

  updateRecommendation();
  updateLibraryBadge();
}

async function updateRecommendation() {
  if (modelSelect.value !== '') {
    autoHint.textContent = '';
    loadVoicesForModel(modelSelect.value);
    return;
  }
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
});

// Form Submission
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  generateBtn.disabled = true;
  studioWaveform.style.display = 'flex';
  studioWaveform.classList.add('active');

  const text = textInput.value.trim();
  if (!text) return;

  const basePayload = {
    voice_name: document.getElementById('voice-name').value,
    language: langSelect.value,
    model_id: modelSelect.value || null,
    voice_id: voiceSelect.value,
    speed: parseFloat(speedInput.value),
    pitch: parseFloat(pitchInput.value),
    output_format: State.settings.format,
  };

  try {
    if (State.isBatch) {
      const lines = text.split('\n').map(l => l.trim()).filter(l => l.length > 0);
      if (lines.length === 0) throw new Error('No valid text lines found');
      const res = await API.createBatch({ ...basePayload, texts: lines });
      Toast.show(`Generated ${res.generated} audio clips!`);
    } else {
      await API.createVoice({ ...basePayload, text });
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

async function renderLibrary() {
  const q = document.getElementById('library-search').value;
  const model = document.getElementById('filter-model').value;
  const lang = document.getElementById('filter-lang').value;

  const data = await API.searchVoices(q, model, lang);
  const list = document.getElementById('library-list');
  list.innerHTML = '';

  if (data.voices.length === 0) {
    list.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🎙️</div>
        <h4>No audio clips found</h4>
        <p>Synthesize text in the Studio tab to see your generated voices here.</p>
      </div>
    `;
    return;
  }

  data.voices.forEach(voice => {
    const card = document.createElement('div');
    card.className = 'voice-card glass';
    card.innerHTML = `
      <div class="voice-row-top">
        <div class="voice-title">${voice.voice_name}</div>
        <div class="voice-meta">
          <span class="voice-meta-item">🤖 ${voice.model_id}</span>
          <span class="voice-meta-item">🗣️ ${voice.language.toUpperCase()}</span>
          <span class="voice-meta-item">⚡ ${voice.speed}x</span>
          <span class="voice-meta-item">📅 ${new Date(voice.created_at).toLocaleTimeString()}</span>
        </div>
      </div>
      <div class="voice-text">"${voice.text}"</div>
      <div class="voice-controls">
        <button class="btn-icon play play-btn" data-url="/api/voices/${voice.id}/audio" data-id="${voice.id}">
          <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
        </button>
        <div class="waveform" id="wf-${voice.id}">
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

  // Attach playback handlers
  document.querySelectorAll('.play-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const url = e.currentTarget.dataset.url;
      const wfId = `wf-${e.currentTarget.dataset.id}`;

      if (currentAudio) {
        currentAudio.pause();
        if (currentWaveform) currentWaveform.classList.remove('active');
      }

      currentAudio = new Audio(url);
      currentWaveform = document.getElementById(wfId);

      currentWaveform.classList.add('active');
      currentAudio.play();

      currentAudio.onended = () => {
        currentWaveform.classList.remove('active');
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

  document.getElementById('stat-total-voices').textContent = stats.total_voices;
  document.getElementById('stat-total-duration').textContent = `${stats.total_duration_sec}s`;
  document.getElementById('stat-disk-usage').textContent = `${stats.disk.audio_mb} MB`;
  document.getElementById('stat-models-count').textContent = stats.installed_models;

  // Storage breakdown
  const storageEl = document.getElementById('storage-breakdown');
  storageEl.innerHTML = `
    <div style="display:flex; justify-content:space-between; font-size:13px; color:var(--text-secondary);">
      <span>Downloaded Models:</span> <b>${stats.disk.models_mb} MB</b>
    </div>
    <div style="display:flex; justify-content:space-between; font-size:13px; color:var(--text-secondary);">
      <span>Generated Audio Clips:</span> <b>${stats.disk.audio_mb} MB</b>
    </div>
  `;

  // Models usage breakdown
  const usageEl = document.getElementById('models-usage-breakdown');
  if (stats.models_used.length === 0) {
    usageEl.innerHTML = '<div style="font-size:13px; color:var(--text-tertiary);">No generation activity recorded yet.</div>';
  } else {
    usageEl.innerHTML = stats.models_used.map(m => `
      <div style="display:flex; justify-content:space-between; font-size:13px; color:var(--text-secondary);">
        <span>${m.model_id}:</span> <b>${m.cnt} clips</b>
      </div>
    `).join('');
  }
}

// ─── SETTINGS DRAWER ───────────────────────────────────────────────────────

const settingsOverlay = document.getElementById('settings-overlay');
const settingsDrawer = document.getElementById('settings-drawer');
const settingFormat = document.getElementById('setting-format');
const settingAutoplay = document.getElementById('setting-autoplay');

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

settingFormat.value = State.settings.format;
settingAutoplay.value = State.settings.autoplay.toString();

settingFormat.addEventListener('change', (e) => {
  State.settings.format = e.target.value;
  localStorage.setItem('tts_format', e.target.value);
  document.getElementById('format-tag').textContent = `Format: ${e.target.value.toUpperCase()}`;
});

settingAutoplay.addEventListener('change', (e) => {
  State.settings.autoplay = e.target.value === 'true';
  localStorage.setItem('tts_autoplay', e.target.value);
});

// Shortcuts overlay
document.getElementById('open-shortcuts').addEventListener('click', () => {
  document.getElementById('shortcuts-overlay').classList.add('open');
});
document.getElementById('close-shortcuts').addEventListener('click', () => {
  document.getElementById('shortcuts-overlay').classList.remove('open');
});

// ─── INIT ──────────────────────────────────────────────────────────────────

initStudio();
