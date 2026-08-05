// Audio Mixer Logic

let mixerClips = [];
const PIXELS_PER_SECOND = 20; // 20px = 1s, so 1px = 50ms
const MS_PER_PIXEL = 1000 / PIXELS_PER_SECOND;

// We need a global Toast reference since this is not a module
const Toast = {
    show: (msg, type='success') => {
        const c = document.getElementById('toast-container');
        if(!c) return;
        const el = document.createElement('div');
        el.className = `toast toast-${type}`;
        el.innerText = msg;
        c.appendChild(el);
        setTimeout(() => el.remove(), 3000);
    }
};

document.addEventListener('DOMContentLoaded', () => {
    // Tab switching listener to populate mixer library
    const mixerTabBtn = document.querySelector('[data-tab="mixer"]');
    if(mixerTabBtn) {
        mixerTabBtn.addEventListener('click', loadMixerLibrary);
    }

    // Setup drag and drop for tracks
    const tracks = document.querySelectorAll('.mixer-track');
    tracks.forEach(track => {
        track.addEventListener('dragover', (e) => {
            e.preventDefault();
            track.style.background = 'rgba(255,255,255,0.1)';
        });

        track.addEventListener('dragleave', (e) => {
            track.style.background = '';
        });

        track.addEventListener('drop', (e) => {
            e.preventDefault();
            track.style.background = '';
            
            const voiceId = e.dataTransfer.getData('voiceId');
            const voiceName = e.dataTransfer.getData('voiceName');
            if(!voiceId) return;

            // Calculate drop position
            const rect = track.querySelector('.track-content').getBoundingClientRect();
            // Restrict X to within the track content area
            let x = e.clientX - rect.left;
            if(x < 0) x = 0;

            addClipToTrack(track, voiceId, voiceName, x);
        });
    });

    // Export button
    const exportBtn = document.getElementById('export-mix-btn');
    if(exportBtn) {
        exportBtn.addEventListener('click', exportMix);
    }
});

async function loadMixerLibrary() {
    const list = document.getElementById('mixer-library-list');
    list.innerHTML = '<div style="color: var(--text-secondary); text-align: center; font-size: 13px; padding: 20px 0;">Loading library...</div>';
    
    try {
        const res = await fetch('/api/voice/library');
        const voices = await res.json();
        
        if(!voices.length) {
            list.innerHTML = '<div style="color: var(--text-secondary); text-align: center; font-size: 13px; padding: 20px 0;">No clips found in your library.</div>';
            return;
        }

        list.innerHTML = '';
        voices.forEach(v => {
            const el = document.createElement('div');
            el.className = 'library-item';
            el.setAttribute('draggable', 'true');
            el.innerHTML = `
                <div style="font-weight: 600; color: white;">${v.voice_name || 'Unnamed'}</div>
                <div style="font-size: 11px; color: var(--text-tertiary); margin-top: 4px;">${v.text.substring(0, 30)}...</div>
            `;
            
            el.addEventListener('dragstart', (e) => {
                e.dataTransfer.setData('voiceId', v.id);
                e.dataTransfer.setData('voiceName', v.voice_name || 'Clip');
            });

            list.appendChild(el);
        });
    } catch(err) {
        console.error('Failed to load library for mixer', err);
        list.innerHTML = '<div style="color: #ff4444; font-size: 13px;">Failed to load library</div>';
    }
}

function addClipToTrack(trackElement, voiceId, voiceName, offsetPixels) {
    const trackContent = trackElement.querySelector('.track-content');
    
    const clipEl = document.createElement('div');
    clipEl.className = 'mixer-clip';
    clipEl.style.left = `${offsetPixels}px`;
    // We assume an arbitrary width for now, a real implementation would fetch duration
    clipEl.style.width = '100px'; 
    clipEl.innerHTML = voiceName;
    clipEl.dataset.voiceId = voiceId;

    // Enable dragging inside track
    let isDragging = false;
    let startX = 0;
    let originalLeft = 0;

    clipEl.addEventListener('mousedown', (e) => {
        isDragging = true;
        startX = e.clientX;
        originalLeft = parseInt(clipEl.style.left || 0);
        clipEl.style.cursor = 'grabbing';
    });

    document.addEventListener('mousemove', (e) => {
        if(!isDragging) return;
        let newLeft = originalLeft + (e.clientX - startX);
        if(newLeft < 0) newLeft = 0;
        clipEl.style.left = `${newLeft}px`;
    });

    document.addEventListener('mouseup', () => {
        if(isDragging) {
            isDragging = false;
            clipEl.style.cursor = 'grab';
        }
    });

    // Double click to remove
    clipEl.addEventListener('dblclick', () => {
        clipEl.remove();
    });

    trackContent.appendChild(clipEl);
}

async function exportMix() {
    const clips = [];
    document.querySelectorAll('.mixer-clip').forEach(el => {
        const leftPx = parseInt(el.style.left || 0);
        const startTimeMs = Math.floor(leftPx * MS_PER_PIXEL);
        clips.push({
            voice_id: el.dataset.voiceId,
            start_time_ms: startTimeMs
        });
    });

    if(clips.length === 0) {
        return Toast.show('No clips in timeline to mix', 'error');
    }

    const exportBtn = document.getElementById('export-mix-btn');
    const originalText = exportBtn.innerHTML;
    exportBtn.disabled = true;
    exportBtn.innerHTML = '<span>Mixing...</span>';

    try {
        const res = await fetch('/api/voice/mix', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                name: `Mix ${new Date().toLocaleTimeString()}`,
                clips: clips,
                output_format: 'wav'
            })
        });

        if(!res.ok) {
            let msg = 'Mix failed';
            try { const err = await res.json(); msg = err.detail || msg; } catch(e){}
            throw new Error(msg);
        }

        Toast.show('Mixed successfully! Added to your library.', 'success');
        
        // Trigger library reload if window.renderLibrary exists (from app.js)
        if(typeof window.renderLibrary === 'function') {
            window.renderLibrary();
        }

    } catch(err) {
        Toast.show(err.message, 'error');
    } finally {
        exportBtn.disabled = false;
        exportBtn.innerHTML = originalText;
    }
}
