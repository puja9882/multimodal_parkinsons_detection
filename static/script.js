// ========== FILE UPLOAD DETECTION ==========
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

// ========== FIXED PREDICT FUNCTION ==========
async function predict() {
  const drawingFile = document.querySelector("#drawingInput")?.files[0];
  const voiceFile = document.querySelector("#voiceInput")?.files[0];
  const age = document.querySelector("#ageInput")?.value;
  const predictBtn = document.getElementById("predictBtn");
  const resDiv = document.getElementById("result");

  // Validate inputs
  if (!drawingFile || !voiceFile) {
    alert("⚠️ Please provide BOTH spiral drawing AND voice recording!\n\n📁 Upload files OR use live draw/record options.");
    return;
  }

  if (!predictBtn || !resDiv) {
    alert("❌ Page not loaded properly. Please refresh.");
    return;
  }

  // Show loading
  predictBtn.innerHTML = "🔄 Analyzing...";
  predictBtn.disabled = true;
  
  resDiv.innerHTML = `
    <div style="text-align:center; padding:30px;">
      <div style="font-size:60px; margin-bottom:16px; color:#38bdf8;">🤖</div>
      <div style="font-size:18px; font-weight:700; margin-bottom:12px; color:#ffffff;">AI Processing...</div>
      <div style="font-size:14px; color:#94a3b8;">Analyzing spiral drawing + voice features</div>
      <div style="font-size:12px; color:#64748b; margin-top:12px;">3-5 seconds</div>
    </div>
  `;

  const formData = new FormData();
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
            <span class="result-label">Prediction</span>
            <div class="result-value">${data.prediction}</div>
          </div>
          <div>
            <span class="result-label">Confidence</span>
            <div class="result-value">${confPct}%</div>
          </div>
        </div>
        <div class="confidence-explain">
          <strong>Confidence Score:</strong><br>
          0-25%: Very uncertain | 25-50%: Fair | 50-75%: Good | 75-100%: Very confident
        </div>
        <p class="result-note">
          Combined: ${data.combined_score.toFixed(3)} | 
          🖌️ Drawing: ${(data.drawing_prob * 100).toFixed(1)}% | 
          🎤 Voice: ${(data.voice_prob * 100).toFixed(1)}%
        </p>
        ${data.caution ? `<p style="background:rgba(245,158,11,0.3); color:#f59e0b; padding:14px; border-radius:10px; margin:16px 0; font-size:14px; border-left:5px solid #f59e0b; font-weight:600;">${data.caution}</p>` : ''}
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
    if (predictBtn) {
      predictBtn.innerHTML = "✅ Analyze Again";
      predictBtn.disabled = false;
      setTimeout(() => {
        if (predictBtn) predictBtn.innerHTML = "🚀 Analyze Now";
      }, 2000);
    }
  }
}

// ========== SUPER-SMOOTH CANVAS DRAWING ==========
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

  // Plain white background
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  // Mouse events
  canvas.addEventListener("mousedown", handlePointerDown);
  canvas.addEventListener("mousemove", handlePointerMove);
  canvas.addEventListener("mouseup", handlePointerUp);
  canvas.addEventListener("mouseleave", handlePointerUp);

  // Touch events
  canvas.addEventListener("touchstart", handlePointerDown, { passive: false });
  canvas.addEventListener("touchmove", handlePointerMove, { passive: false });
  canvas.addEventListener("touchend", handlePointerUp);

  // Age validation
  const ageInput = document.getElementById("ageInput");
  if (ageInput) {
    ageInput.addEventListener("input", validateAge);
  }
});

// Get position exactly under the pointer
function getPos(e) {
  const rect = canvas.getBoundingClientRect();
  let clientX, clientY;
  if (e.touches && e.touches.length > 0) {
    clientX = e.touches[0].clientX;
    clientY = e.touches[0].clientY;
  } else {
    clientX = e.clientX;
    clientY = e.clientY;
  }
  return {
    x: clientX - rect.left,
    y: clientY - rect.top
  };
}

function handlePointerDown(e) {
  e.preventDefault();
  if (!ctx) return;
  const pos = getPos(e);
  isDrawing = true;
  lastX = pos.x;
  lastY = pos.y;
}

function handlePointerMove(e) {
  if (!isDrawing || !ctx) return;
  e.preventDefault();
  const pos = getPos(e);

  ctx.strokeStyle = "#1e40af";
  ctx.lineWidth = 4;
  ctx.lineCap = "round";

  ctx.beginPath();
  ctx.moveTo(lastX, lastY);
  ctx.lineTo(pos.x, pos.y);
  ctx.stroke();

  lastX = pos.x;
  lastY = pos.y;
}

function handlePointerUp(e) {
  if (!isDrawing) return;
  e?.preventDefault();
  isDrawing = false;
}

// Clear to plain white
function clearCanvas() {
  if (!ctx || !canvas) return;
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  const drawingInput = document.querySelector("#drawingInput");
  if (drawingInput) drawingInput.value = "";
  updateFileStatus("drawingStatus", null);

  const feedback = document.getElementById("drawFeedback");
  if (feedback) {
    feedback.textContent = "Draw tight spiral →";
    feedback.style.color = "#94a3b8";
  }
}

// Export drawing as PNG and attach to file input
function useCanvasAsImage() {
  if (!canvas) return;

  canvas.toBlob(blob => {
    if (!blob) {
      alert("❌ Failed to create image from canvas");
      return;
    }
    const file = new File([blob], "spiral_drawn.png", { type: "image/png" });
    const drawingInput = document.querySelector("#drawingInput");
    if (drawingInput) {
      const dataTransfer = new DataTransfer();
      dataTransfer.items.add(file);
      drawingInput.files = dataTransfer.files;
      updateFileStatus("drawingStatus", file);
    }
    const feedback = document.getElementById("drawFeedback");
    if (feedback) {
      feedback.textContent = "✅ Live drawing attached!";
      feedback.style.color = "#10b981";
    }
  }, "image/png");
}

// ========== AGE VALIDATION ==========
function validateAge() {
  const ageInput = document.getElementById("ageInput");
  const feedback = document.getElementById("ageFeedback");
  if (!ageInput || !feedback) return;
  
  const age = parseInt(ageInput.value);
  if (age >= 11 && age <= 75) {
    feedback.innerHTML = "✅ Optimal range (11-75 years)";
    feedback.className = "feedback valid";
  } else if (age) {
    feedback.innerHTML = "⚠️ Less reliable outside 11-75";
    feedback.className = "feedback warning";
  } else {
    feedback.textContent = "";
  }
}

// ========== AUDIO RECORDING ==========
let mediaRecorder, audioChunks = [], isRecording = false;

async function toggleRecording() {
  const recordBtn = document.getElementById("recordBtn");
  const recordText = document.getElementById("recordText");
  const statusSpan = document.getElementById("recordStatus");
  const waveDiv = document.getElementById("recordWave");
  const clearBtn = document.getElementById("clearRecordBtn");
  const audioElem = document.getElementById("recordedAudio");

  if (!recordBtn || !recordText || !statusSpan) return;

  if (!isRecording) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream);
      audioChunks = [];

      mediaRecorder.ondataavailable = e => {
        if (e.data.size > 0) audioChunks.push(e.data);
      };

      mediaRecorder.onstop = () => {
        if (audioChunks.length === 0) return;
        
        const blob = new Blob(audioChunks, { type: "audio/webm" });
        const file = new File([blob], "voice_recorded.webm", { type: blob.type });

        const voiceInput = document.querySelector("#voiceInput");
        if (voiceInput) {
          const dt = new DataTransfer();
          dt.items.add(file);
          voiceInput.files = dt.files;
          updateFileStatus('voiceStatus', file);
        }

        if (audioElem) {
          const url = URL.createObjectURL(blob);
          audioElem.src = url;
          audioElem.style.display = "block";
        }
        
        if (statusSpan) statusSpan.textContent = `✅ Recorded ${Math.round(blob.size/1024)}KB`;
        if (waveDiv) waveDiv.style.display = "block";
        if (clearBtn) clearBtn.style.display = "inline-flex";
        recordBtn.classList.remove("recording");
      };

      mediaRecorder.start();
      isRecording = true;
      recordText.textContent = "⏹️ Stop";
      statusSpan.textContent = "🎤 Recording... speak continuously";
      recordBtn.classList.add("recording");
      if (clearBtn) clearBtn.style.display = "none";
      if (waveDiv) waveDiv.style.display = "block";
      
    } catch (err) {
      console.error('Audio error:', err);
      alert("❌ Microphone access denied. Please allow permission and refresh.");
    }
  } else {
    if (mediaRecorder && mediaRecorder.state === "recording") {
      mediaRecorder.stop();
      mediaRecorder.stream.getTracks().forEach(t => t.stop());
    }
    isRecording = false;
    recordText.textContent = "🔴 Re-record";
    if (statusSpan) statusSpan.textContent = "Processing...";
    recordBtn.classList.remove("recording");
  }
}

function clearRecording() {
  const voiceInput = document.querySelector("#voiceInput");
  if (voiceInput) voiceInput.value = "";
  updateFileStatus('voiceStatus', null);
  
  const statusSpan = document.getElementById("recordStatus");
  const waveDiv = document.getElementById("recordWave");
  const audioElem = document.getElementById("recordedAudio");
  const clearBtn = document.getElementById("clearRecordBtn");
  const recordBtn = document.getElementById("recordBtn");
  const recordText = document.getElementById("recordText");

  if (statusSpan) statusSpan.textContent = 'Speak "Ahhhh" for 5-10 seconds';
  if (waveDiv) waveDiv.style.display = "none";
  if (audioElem) audioElem.style.display = "none";
  if (clearBtn) clearBtn.style.display = "none";
  if (recordBtn) recordBtn.classList.remove("recording");
  if (recordText) recordText.textContent = "🎙️ Start Recording";
}
