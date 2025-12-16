import os
import sys
import tempfile
import shutil

from flask import Flask, render_template, request, jsonify
from pydub import AudioSegment  # for webm -> wav conversion

# ---------- FFmpeg handling (Windows + Render safe) ----------
# On Windows: use ffmpeg if available in PATH
# On Render (Linux): ffmpeg is already available system-wide
if os.name == "nt":
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        AudioSegment.converter = ffmpeg_path
# Do NOT set hardcoded paths

# ---------- add parent directory (src) to path ----------
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))     # ...\parkinsons\data\src\api
PARENT_DIR = os.path.dirname(CURRENT_DIR)                    # ...\parkinsons\data\src
sys.path.append(PARENT_DIR)

from multimodal_infer import (
    drawing_model,
    voice_model,
    voice_scaler,
    get_drawing_input,
    extract_voice_from_wav,
)

app = Flask(__name__)

# ---------- PAGE ROUTES ----------
@app.route("/")
def home():
    return render_template("home.html")


@app.route("/screening")
def screening():
    return render_template("screening.html")


@app.route("/about")
def about():
    return render_template("about.html")


# ---------- API ROUTE ----------
@app.route("/predict", methods=["POST"])
def predict():
    age = request.form.get("age")

    # ------------ IMAGE ------------
    spiral_file = request.files.get("spiral_img")
    if not spiral_file:
        return jsonify({"error": "spiral_img is required"}), 400

    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_img:
        spiral_path = tmp_img.name
        spiral_file.save(spiral_path)

    # ------------ VOICE (wav OR webm) ------------
    voice_file = request.files.get("voice_wav")
    if not voice_file:
        try:
            os.remove(spiral_path)
        except Exception:
            pass
        return jsonify({"error": "voice_wav is required"}), 400

    original_name = voice_file.filename or "voice_input"
    ext = os.path.splitext(original_name)[1].lower()

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_voice:
        raw_voice_path = tmp_voice.name
        voice_file.save(raw_voice_path)

    if ext == ".webm":
        wav_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        wav_temp.close()
        wav_path = wav_temp.name

        try:
            audio = AudioSegment.from_file(raw_voice_path, format="webm")
            audio.export(wav_path, format="wav")
        except Exception as e:
            try:
                os.remove(spiral_path)
            except Exception:
                pass
            try:
                os.remove(raw_voice_path)
            except Exception:
                pass
            return jsonify({"error": f"Failed to convert webm to wav: {e}"}), 500

        final_voice_path = wav_path
    else:
        final_voice_path = raw_voice_path

    # ------------ MULTIMODAL INFERENCE ------------
    d_in = get_drawing_input(spiral_path)
    d_prob = float(drawing_model.predict(d_in, verbose=0).flatten()[0])

    expected = getattr(voice_scaler, "n_features_in_", None)
    v_raw = extract_voice_from_wav(final_voice_path, expected_n_features=expected)

    try:
        v_scaled = voice_scaler.transform(v_raw)
    except Exception:
        n = getattr(voice_scaler, "n_features_in_", v_raw.shape[1])
        v_scaled = voice_scaler.transform([[0.0] * n])

    if hasattr(voice_model, "predict_proba"):
        v_prob = float(voice_model.predict_proba(v_scaled)[:, 1][0])
    else:
        v_prob = float(voice_model.predict(v_scaled)[0])

    draw_weight = 0.55
    voice_weight = 0.45
    final = draw_weight * d_prob + voice_weight * v_prob
    confidence = abs(final - 0.5) * 2
    prediction = "Parkinson" if final >= 0.5 else "No Parkinson"

    caution = None
    if age is not None:
        try:
            a = float(age)
            if a < 11 or a > 75:
                caution = (
                    f"⚠ Age = {a}: model may be unreliable for kids under 11 or elders over 75; "
                    f"interpret result cautiously."
                )
        except Exception:
            pass

    # ------------ CLEAN UP TEMP FILES ------------
    for p in [spiral_path, raw_voice_path]:
        try:
            os.remove(p)
        except Exception:
            pass

    if final_voice_path != raw_voice_path:
        try:
            os.remove(final_voice_path)
        except Exception:
            pass

    return jsonify({
        "prediction": prediction,
        "combined_score": final,
        "confidence": confidence,
        "drawing_prob": d_prob,
        "voice_prob": v_prob,
        "caution": caution,
        "extracted_voice_features": v_raw.flatten().tolist()
    })


# ---------- ENTRY POINT ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
