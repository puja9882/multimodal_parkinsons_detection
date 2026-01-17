// =======================
// FILE UPLOAD DETECTION
// =======================
document.addEventListener('change', function(e) {
  if (e.target.id === 'drawingInput') {
    updateFileStatus('drawingStatus', e.target.files[0]);
  } else if (e.target.id === 'voiceInput') {
    updateFileStatus('voiceStatus', e.target.files[0]);
  }
});

function updateFileStatus(statusId, file) {
  const status = document.getElementById(statusId);
  if (!status) return;

  if (file) {
    status.textContent = `✅ ${file.name} (${Math.round(file.size / 1024)}KB)`;
    status.parentElement.classList.add('has-file');
  } else {
    if (statusId === 'drawingStatus') {
      status.textContent = '📁 Upload PNG/JPG file';
    } else {
      status.textContent = '📁 Upload WAV file';
    }
    if (status.parentElement) status.parentElement.classList.remove('has-file');
  }
}

// =======================
// PREDICT FUNCTION
// =======================
async function predict() {
  const drawingFile = document.querySelector("#drawingInput")?.files[0];
  const voiceFile = document.querySelector("#voiceInput")?.files[0];
  const name = document.querySelector("#nameInput")?.value.trim();
  const age = document.querySelector("#ageInput")?.value;
  const predictBtn = document.getElementById("predictBtn");
  const resDiv = document.getElementById("result");

  if (!drawingFile || !voiceFile) {
    alert("⚠️ Please provide BOTH spiral drawing AND voice recording!\n\n📁 Upload files OR use live draw/record options.");
    return;
  }

  if (!predictBtn || !resDiv) {
    alert("❌ Page not loaded properly. Please refresh.");
    return;
  }

  predictBtn.innerHTML = "🔄 Analyzing...";
  predictBtn.disabled = true;

  // 🔒 LOCK ALL INPUTS DURING ANALYSIS
  window.isAnalyzing = true;
  document.querySelectorAll('#recordBtn, #clearRecordBtn, #spiralCanvas, .draw-btn').forEach(el => {
    el.style.pointerEvents = 'none';
    el.style.opacity = '0.5';
  });

  resDiv.innerHTML = `
    <div style="text-align:center; padding:30px;">
      <div style="font-size:60px; margin-bottom:16px; color:#38bdf8;">🤖</div>
      <div style="font-size:18px; font-weight:700; margin-bottom:12px; color:#ffffff;">AI Processing...</div>
      <div style="font-size:14px; color:#94a3b8;">Analyzing spiral drawing + voice features</div>
      <div style="font-size:12px; color:#64748b; margin-top:12px;">3-5 seconds</div>
    </div>
  `;

  const formData = new FormData();
  formData.append("name", name);
  formData.append("spiral_img", drawingFile);
  formData.append("voice_wav", voiceFile);
  formData.append("age", age || "");

  try {
    const resp = await fetch("/predict", { 
      method: "POST", 
      body: formData 
    });

    const data = await resp.json();

    if (!resp.ok) {
      resDiv.innerHTML = `<div style="color:#f87171; padding:24px; text-align:center; background:rgba(239,68,68,0.2); border-radius:12px; border-left:5px solid #ef4444;">
        ❌ Server Error
        <div style="font-size:13px; margin-top:12px; color:#fecaca;">${data.error || 'Unknown server error'}</div>
      </div>`;
      return;
    }

    const confPct = (data.confidence * 100).toFixed(0);
    const predClass = data.prediction === "Parkinson" ? "result-risk" : "result-ok";
    const friendlyNote = data.risk_text || "This is a research screening tool and not a medical diagnosis.";

    const params = new URLSearchParams({
      name: name,
      prediction: data.prediction || "",
      conf: confPct || "",
      combined: data.combined_score != null ? data.combined_score.toFixed(3) : "",
      draw: data.drawing_prob != null ? (data.drawing_prob * 100).toFixed(1) : "",
      voice: data.voice_prob != null ? (data.voice_prob * 100).toFixed(1) : "",
      age: data.age || "",
      risk_text: data.risk_text || "",
      severity: data.severity_label || "",
      caution: data.caution || "",
      total_tests: (data.total_tests ?? "").toString(),
      total_parkinson: (data.total_parkinson ?? "").toString(),
      total_no_parkinson: (data.total_no_parkinson ?? "").toString()
    });

    const reportUrl = "/report?" + params.toString();

    resDiv.innerHTML = `
      <div class="result-summary ${predClass}">
        <div class="confidence-meter">
         <div class="confidence-bar">
           <div class="confidence-fill" style="width:${confPct}%"></div>
         </div>
         <div class="confidence-labels">
           <span>Low Confidence</span>
           <span>High Confidence</span>
         </div>
        </div>
        <div class="result-main">
         <div>
           <span class="result-label">Screening result</span>
           <div class="result-value">${data.prediction}</div>
         </div>
         <div>
           <span class="result-label">Confidence</span>
           <div class="result-value">${confPct}%</div>
         </div>
        </div>
        <p class="result-note">
         Combined score: ${data.combined_score.toFixed(3)} · 
         🖌️ Drawing: ${(data.drawing_prob * 100).toFixed(1)}% · 
         🎤 Voice: ${(data.voice_prob * 100).toFixed(1)}%
        </p>
        <p class="result-note">
         ${friendlyNote}
        </p>
        ${data.caution ? `<p style="background:rgba(245,158,11,0.3); color:#f59e0b; padding:14px; border-radius:10px; margin:12px 0; font-size:14px; border-left:5px solid #f59e0b; font-weight:600;">${data.caution}</p>` : ''}
        <button type="button" class="btn btn-secondary" style="margin-top:10px;" onclick="window.open('${reportUrl}', '_blank')">
         📄 Generate Detailed Report
        </button>
      </div>
    `;
  } catch (err) {
    console.error('Predict error:', err);
    resDiv.innerHTML = `<div style="color:#f87171; padding:30px; text-align:center; background:rgba(239,68,68,0.2); border-radius:16px; border-left:6px solid #ef4444;">
      ❌ Network Error
      <div style="font-size:14px; font-weight:600; margin-top:12px;">Please check your internet connection</div>
      <div style="font-size:12px; color:#fecaca; margin-top:8px;">${err.message}</div>
    </div>`;
  } finally {
    // 🔓 UNLOCK ALL INPUTS AFTER RESULT
    window.isAnalyzing = false;
    document.querySelectorAll('#recordBtn, #clearRecordBtn, #spiralCanvas, .draw-btn').forEach(el => {
      el.style.pointerEvents = '';
      el.style.opacity = '';
    });

    if (predictBtn) {
      predictBtn.innerHTML = "✅ Analyze Again";
      predictBtn.disabled = false;
      setTimeout(() => {
        if (predictBtn) predictBtn.innerHTML = "🚀 Analyze Now";
      }, 2000);
    }
  }
}

// =======================
// SUPER-SMOOTH CANVAS DRAWING
// =======================
let canvas, ctx;
let isDrawing = false;
let lastX = 0;
let lastY = 0;

window.addEventListener("load", function () {
  canvas = document.getElementById("spiralCanvas");
  if (!canvas) {
    console.warn("Canvas not found");
    return;
  }

  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width;
  canvas.height = rect.height;
  ctx = canvas.getContext("2d");

  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  canvas.addEventListener("mousedown", handlePointerDown);
  canvas.addEventListener("mousemove", handlePointerMove);
  canvas.addEventListener("mouseup", handlePointerUp);
  canvas.addEventListener("mouseleave", handlePointerUp);

  canvas.addEventListener("touchstart", handlePointerDown, { passive: false });
  canvas.addEventListener("touchmove", handlePointerMove, { passive: false });
  canvas.addEventListener("touchend", handlePointerUp);

  const ageInput = document.getElementById("ageInput");
  if (ageInput) {
    ageInput.addEventListener("input", validateAge);
  }
});

// (pointer functions, clearCanvas, useCanvasAsImage, validateAge remain unchanged)

// =======================
// FIXED AUDIO RECORDING
// =======================
// (toggleRecording and clearRecording remain unchanged, just remove SW + network status code from inside)

let mediaRecorder, audioChunks = [], isRecording = false;
let recordedAudioPreview = null;

// toggleRecording() { ... }   <-- keep as is
// clearRecording() { ... }    <-- keep as is, but without SW/network code inside

// =======================
// SERVICE WORKER & OFFLINE WARNING (GLOBAL)
// =======================

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/service-worker.js')
    .then(() => console.log('✅ Service Worker Registered'))
    .catch(err => console.log('❌ SW registration failed', err));
}

// Network status indicator
function updateNetworkStatus() {
  const status = document.getElementById("netStatus");
  if (!status) return;

  if (!navigator.onLine) {
    status.style.display = "block";
  } else {
    status.style.display = "none";
  }
}

// Check network status immediately and listen for changes
window.addEventListener("load", updateNetworkStatus);
window.addEventListener("online", updateNetworkStatus);
window.addEventListener("offline", updateNetworkStatus);
