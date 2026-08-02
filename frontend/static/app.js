// ─── UTILS & TOASTS ────────────────────────────────────────────────────────

const Toast = {
  show(msg, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
      <svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        ${type === 'success' ? '<path d="M5 13l4 4L19 7"></path>' : '<path d="M6 18L18 6M6 6l12 12"></path>'}
      </svg>
      <span>${msg}</span>
    `;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100%)';
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }
};

// ─── API ───────────────────────────────────────────────────────────────────

const API = {
  async getCatalog() {
    const res = await fetch('/api/models/catalog');
    const data = await res.json();
    return data.models;
  },
  async getVoices() {
    const res = await fetch('/api/voices');
    const data = await res.json();
    return data.voices;
  },
  async getModelVoices(modelId) {
    const res = await fetch(`/api/models/${modelId}/voices`);
    if(!res.ok) return [];
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
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
  async startDownload(modelId) {
    const res = await fetch(`/api/models/download/${modelId}`, { method: 'POST' });
    if (!res.ok) throw new Error(await res.text());
  },
  async deleteVoice(id) {
    const res = await fetch(`/api/voices/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete');
  }
};

// ─── TABS ──────────────────────────────────────────────────────────────────

document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', (e) => {
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    
    const target = e.currentTarget;
    target.classList.add('active');
    document.getElementById(`tab-${target.dataset.tab}`).classList.add('active');

    if(target.dataset.tab === 'models') renderModels();
    if(target.dataset.tab === 'library') renderLibrary();
  });
});

// ─── STUDIO ────────────────────────────────────────────────────────────────

const form = document.getElementById('voice-form');
const modelSelect = document.getElementById('model-id');
const voiceSelect = document.getElementById('voice-id');
const autoHint = document.getElementById('auto-hint');
const generateBtn = document.getElementById('generate-btn');
const studioWaveform = document.getElementById('studio-waveform');

let catalog = [];

async function initStudio() {
  catalog = await API.getCatalog();
  
  // Populate Models
  catalog.filter(m => m.is_installed).forEach(m => {
    const opt = document.createElement('option');
    opt.value = m.model_id;
    opt.textContent = m.display_name;
    modelSelect.appendChild(opt);
  });

  updateRecommendation();
}

async function updateRecommendation() {
  if (modelSelect.value !== "") {
    autoHint.textContent = "";
    loadVoicesForModel(modelSelect.value);
    return;
  }
  const text = document.getElementById('text').value || "Hello";
  const lang = document.getElementById('language').value;
  try {
    const modelId = await API.recommend(text, lang);
    const m = catalog.find(c => c.model_id === modelId);
    autoHint.textContent = `Auto will use: ${m ? m.display_name : modelId}`;
  } catch (e) {
    autoHint.textContent = "";
  }
}

async function loadVoicesForModel(modelId) {
  voiceSelect.innerHTML = '<option value="auto">Default for Model</option>';
  if(!modelId) return;
  const voices = await API.getModelVoices(modelId);
  voices.forEach(v => {
    const opt = document.createElement('option');
    opt.value = v.id;
    opt.textContent = v.name;
    voiceSelect.appendChild(opt);
  });
}

document.getElementById('text').addEventListener('input', () => {
  if(modelSelect.value === "") updateRecommendation();
});
document.getElementById('language').addEventListener('change', () => {
  if(modelSelect.value === "") updateRecommendation();
});
modelSelect.addEventListener('change', updateRecommendation);


form.addEventListener('submit', async (e) => {
  e.preventDefault();
  generateBtn.disabled = true;
  generateBtn.style.display = 'none';
  studioWaveform.style.display = 'flex';
  studioWaveform.classList.add('active');

  const payload = {
    text: document.getElementById('text').value,
    voice_name: document.getElementById('voice-name').value,
    language: document.getElementById('language').value,
    model_id: document.getElementById('model-id').value || null,
    voice_id: document.getElementById('voice-id').value,
    speed: parseFloat(document.getElementById('speed').value),
    pitch: parseFloat(document.getElementById('pitch').value),
  };

  try {
    await API.createVoice(payload);
    Toast.show('Voice generated successfully!');
    document.querySelector('[data-tab="library"]').click(); // switch to library
  } catch (err) {
    Toast.show(err.message, 'error');
  } finally {
    generateBtn.disabled = false;
    generateBtn.style.display = 'inline-flex';
    studioWaveform.style.display = 'none';
    studioWaveform.classList.remove('active');
  }
});

// ─── MODELS ────────────────────────────────────────────────────────────────

async function renderModels() {
  catalog = await API.getCatalog();
  const grid = document.getElementById('models-grid');
  grid.innerHTML = '';

  catalog.forEach(model => {
    const card = document.createElement('div');
    card.className = 'model-card glass';
    
    let badge = `<span class="badge">Not Installed</span>`;
    let btnHtml = `<button class="btn download-btn" data-id="${model.model_id}">Download Model</button>`;

    if (model.is_cloud) {
      badge = `<span class="badge cloud">Cloud Engine</span>`;
      btnHtml = `<button class="btn" disabled>Always Available</button>`;
    } else if (model.is_installed) {
      badge = `<span class="badge installed">Installed</span>`;
      btnHtml = `<button class="btn" disabled style="background:var(--success)">Ready to Use</button>`;
    } else if (model.is_downloading) {
      badge = `<span class="badge">Downloading...</span>`;
      btnHtml = `
        <div class="progress-ring" id="prog-${model.model_id}">
          <svg width="40" height="40">
            <circle class="progress-ring-bg" cx="20" cy="20" r="16"></circle>
            <circle class="progress-ring-fg" cx="20" cy="20" r="16" id="prog-circle-${model.model_id}"></circle>
          </svg>
          <div class="progress-text" id="prog-text-${model.model_id}">0%</div>
        </div>
      `;
    }

    card.innerHTML = `
      <div class="model-header">
        <div>
          <div class="model-title">${model.display_name}</div>
          <div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">${model.size_mb} MB</div>
        </div>
        ${badge}
      </div>
      <div class="model-desc">${model.description}</div>
      <div class="model-meta">
        <span>🗣️ ${model.languages.join(', ').toUpperCase()}</span>
        <span>⭐ Q-Score: ${model.quality_score}</span>
      </div>
      <div style="margin-top: auto;">${btnHtml}</div>
    `;
    grid.appendChild(card);
  });

  // Attach download handlers
  document.querySelectorAll('.download-btn').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const id = e.target.dataset.id;
      e.target.disabled = true;
      try {
        await API.startDownload(id);
        renderModels(); // re-render to show progress ring
        startSSEProgress(id);
      } catch (err) {
        Toast.show('Failed to start download', 'error');
        e.target.disabled = false;
      }
    });
  });
}

function startSSEProgress(modelId) {
  const evtSource = new EventSource(`/api/models/download/${modelId}/progress`);
  evtSource.onmessage = function(event) {
    if(event.data === ": keepalive") return;
    const msg = JSON.parse(event.data);
    
    if (msg.event === 'download_progress') {
      const circle = document.getElementById(`prog-circle-${modelId}`);
      const text = document.getElementById(`prog-text-${modelId}`);
      if(circle && text) {
        const offset = 100 - (msg.progress * 100);
        circle.style.strokeDashoffset = offset;
        text.textContent = Math.round(msg.progress * 100) + '%';
      }
    } else if (msg.event === 'download_complete') {
      Toast.show(`${modelId} installed successfully!`);
      evtSource.close();
      renderModels(); // re-render as installed
      initStudio(); // refresh dropdowns
    } else if (msg.event === 'download_error') {
      Toast.show(`Error: ${msg.error}`, 'error');
      evtSource.close();
      renderModels();
    }
  };
}

// ─── LIBRARY ───────────────────────────────────────────────────────────────

let currentAudio = null;
let currentWaveform = null;

async function renderLibrary() {
  const voices = await API.getVoices();
  const list = document.getElementById('library-list');
  list.innerHTML = '';

  if(voices.length === 0) {
    list.innerHTML = '<div style="color:var(--text-secondary)">No voices generated yet.</div>';
    return;
  }

  voices.forEach(voice => {
    const card = document.createElement('div');
    card.className = 'voice-card glass';
    card.innerHTML = `
      <div class="voice-header">
        <div class="voice-title">${voice.voice_name}</div>
        <div class="voice-meta">${new Date(voice.created_at).toLocaleString()}</div>
      </div>
      <div class="voice-meta">
        Model: <b>${voice.model_id}</b> | Lang: <b>${voice.language.toUpperCase()}</b> | Speed: <b>${voice.speed}x</b>
      </div>
      <div class="voice-text">"${voice.text}"</div>
      
      <div class="voice-controls">
        <button class="btn-icon play-btn" data-url="/api/voices/${voice.id}/audio" data-id="${voice.id}">
          <svg width="18" height="18" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
        </button>
        <div class="waveform" id="wf-${voice.id}">
          <div class="waveform-bar"></div><div class="waveform-bar"></div>
          <div class="waveform-bar"></div><div class="waveform-bar"></div>
          <div class="waveform-bar"></div><div class="waveform-bar"></div>
        </div>
        <a href="/api/voices/${voice.id}/audio" download="${voice.file_name || 'audio.wav'}" class="btn-icon">
          <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
        </a>
        <button class="btn-icon danger del-btn" data-id="${voice.id}">
          <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
        </button>
      </div>
    `;
    list.appendChild(card);
  });

  // Playback
  document.querySelectorAll('.play-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const url = e.currentTarget.dataset.url;
      const wfId = `wf-${e.currentTarget.dataset.id}`;
      
      if(currentAudio) {
        currentAudio.pause();
        if(currentWaveform) currentWaveform.classList.remove('active');
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

  // Delete
  document.querySelectorAll('.del-btn').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const id = e.currentTarget.dataset.id;
      if(confirm('Delete this voice?')) {
        await API.deleteVoice(id);
        renderLibrary();
        Toast.show('Voice deleted');
      }
    });
  });
}

// ─── INIT ──────────────────────────────────────────────────────────────────

initStudio();
