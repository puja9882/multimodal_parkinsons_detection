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

// ========== PREDICT FUNCTION ==========
// ========== PREDICT FUNCTION ==========
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

  // ✅ FIX: SIMPLE LOADING STATE (NO predClass USED HERE)
  resDiv.innerHTML = `
    <div style="text-align:center; padding:30px;">
      <div style="font-size:48px;">🤖</div>
      <div style="margin-top:10px; font-weight:600;">AI Processing...</div>
      <div style="font-size:13px; opacity:0.7; margin-top:6px;">
        Analyzing spiral + voice
      </div>
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
    
    // ✅ SAFE PARSING FIX (ONLY CHANGE)
    const text = await resp.text();
    
    let data;
    try {
      data = JSON.parse(text);
    } catch (err) {
      console.error("❌ Server returned HTML instead of JSON:", text);
    
      resDiv.innerHTML = `<div style="color:#f87171; padding:24px; text-align:center; background:rgba(239,68,68,0.2); border-radius:12px;">
        ❌ Server Error<br>
        <small>Check backend terminal</small>
      </div>`;
      
      return;
    }


    const confPct = (data.confidence * 100).toFixed(0);
    const predClass = data.prediction === "Parkinson" ? "result-risk" : "result-ok";
    const friendlyNote = data.risk_text || "✅ Analysis completed!!";

    const params = new URLSearchParams({
      name:name,
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

    // ✅ ORIGINAL RESULT BLOCK (UNCHANGED)
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
  if (window.isAnalyzing) return;  // 🔒 Block during analysis
  e.preventDefault();
  if (!ctx) return;
  const pos = getPos(e);
  isDrawing = true;
  lastX = pos.x;
  lastY = pos.y;
}

function handlePointerMove(e) {
  if (!isDrawing || !ctx || window.isAnalyzing) return;  // 🔒 Block during analysis
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
  if (!isDrawing || window.isAnalyzing) return;  // 🔒 Block during analysis
  e?.preventDefault();
  isDrawing = false;
}

function clearCanvas() {
  if (window.isAnalyzing) return;  // 🔒 Block during analysis
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

function useCanvasAsImage() {
  if (window.isAnalyzing) return;  // 🔒 Block during analysis
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

// ========== FIXED AUDIO RECORDING - NO WEBM VISIBLE ==========
let mediaRecorder, audioChunks = [], isRecording = false;
let recordedAudioPreview = null;

async function toggleRecording() {
  if (window.isAnalyzing) return;  // 🔒 Block during analysis
  const recordBtn = document.getElementById("recordBtn");
  const recordText = document.getElementById("recordText");
  const statusSpan = document.getElementById("recordStatus");
  const clearBtn = document.getElementById("clearRecordBtn");
  const audioElem = document.getElementById("recordedAudio");

  if (!recordBtn || !recordText || !statusSpan) return;

  if (!isRecording) {
    // START RECORDING
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream);
      audioChunks = [];

      mediaRecorder.ondataavailable = e => {
        if (e.data.size > 0) audioChunks.push(e.data);
      };

      mediaRecorder.onstop = () => {
        if (audioChunks.length === 0) return;
        
        // ✅ CREATE AUDIO PREVIEW (WebM format for playback)
        const blob = new Blob(audioChunks, { type: "audio/webm" });
        const previewUrl = URL.createObjectURL(blob);
        
        // ✅ HIDE WEBM: Shows "voice.wav" instead of "voice_recorded.webm"
        const file = new File([blob], "voice.wav", { type: "audio/webm" });
        const voiceInput = document.querySelector("#voiceInput");
        if (voiceInput) {
          const dt = new DataTransfer();
          dt.items.add(file);
          voiceInput.files = dt.files;
          updateFileStatus('voiceStatus', file);  // ✅ Shows "voice.wav (136KB)"
        }

        // ✅ SHOW AUDIO PLAYER PREVIEW
        if (audioElem) {
          audioElem.src = previewUrl;
          audioElem.style.display = "block";
          recordedAudioPreview = previewUrl;
        }
        
        // ✅ UPDATE STATUS
        if (statusSpan) statusSpan.innerHTML = `✅ Recorded <strong>${Math.round(blob.size/1024)}KB</strong> <span style="color:#10b981;">(Click ▶️ to preview)</span>`;
        if (clearBtn) clearBtn.style.display = "inline-flex";
        recordBtn.classList.remove("recording");
        stream.getTracks().forEach(t => t.stop());
      };

      mediaRecorder.start();
      isRecording = true;
      recordText.textContent = "⏹️ Stop";
      statusSpan.textContent = "🎤 Recording... speak \"Ahhhh\" continuously";
      recordBtn.classList.add("recording");
      if (clearBtn) clearBtn.style.display = "none";
    } catch (err) {
      console.error('Audio error:', err);
      alert("❌ Microphone access denied. Please allow permission and refresh.");
    }
  } else {
    // STOP RECORDING
    if (mediaRecorder && mediaRecorder.state === "recording") {
      mediaRecorder.stop();
    }
    isRecording = false;
    recordText.textContent = "🔴 Re-record";
    if (statusSpan) statusSpan.textContent = "Processing recording...";
    recordBtn.classList.remove("recording");
  }
}

function clearRecording() {
  if (window.isAnalyzing) return;  // 🔒 Block during analysis
  const voiceInput = document.querySelector("#voiceInput");
  if (voiceInput) voiceInput.value = "";
  updateFileStatus('voiceStatus', null);
  
  // Clear preview audio
  const audioElem = document.getElementById("recordedAudio");
  if (audioElem) {
    audioElem.src = "";
    audioElem.style.display = "none";
    if (recordedAudioPreview) {
      URL.revokeObjectURL(recordedAudioPreview);
      recordedAudioPreview = null;
    }
  }
  
  const statusSpan = document.getElementById("recordStatus");
  const clearBtn = document.getElementById("clearRecordBtn");
  const recordBtn = document.getElementById("recordBtn");
  const recordText = document.getElementById("recordText");

  if (statusSpan) statusSpan.textContent = 'Speak "Ahhhh" for 5-10 seconds';
  if (clearBtn) clearBtn.style.display = "none";
  if (recordBtn) recordBtn.classList.remove("recording");
  if (recordText) recordText.textContent = "🎙️ Start Recording";
}
