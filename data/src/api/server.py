import os
import sys
import tempfile
import shutil
import numpy as np
import pandas as pd
from flask import Flask, render_template, request, jsonify
from pydub import AudioSegment



# ---------- FFmpeg handling ----------
ffmpeg_path = shutil.which("ffmpeg")
if ffmpeg_path:
    AudioSegment.converter = ffmpeg_path



CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
sys.path.append(PARENT_DIR)



from multimodal_infer import *


app = Flask(
    __name__,
    template_folder=os.path.join(CURRENT_DIR, "templates"),
    static_folder=os.path.join(CURRENT_DIR, "static")
)



# ---------- GLOBAL STATS ----------
TOTAL_TESTS = 0
TOTAL_PARKINSON = 0
TOTAL_NO_PARKINSON = 0



def cleanup_files(paths):
    """Safe cleanup helper"""
    for path in paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass



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



@app.route('/report')
def report():
    # EXACT MATCH for report.html template variables
    prediction = request.args.get('prediction', 'Not available')
    conf_pct = request.args.get('conf', '0')           # Template: conf_pct
    combined = request.args.get('combined', '0.000')
    draw_pct = request.args.get('draw', 'N/A')         # Template: draw_pct
    voice_pct = request.args.get('voice', 'N/A')       # Template: voice_pct
    age = request.args.get('age', '')
    risk_text = request.args.get('risk_text', '')      # Template: risk_text
    severity = request.args.get('severity', '')
    caution = request.args.get('caution', '')
    total_tests = request.args.get('total_tests', '0')        # Template: total_tests
    total_parkinson = request.args.get('total_parkinson', '0') # Template: total_parkinson
    total_no_parkinson = request.args.get('total_no_parkinson', '0') # Template: total_no_parkinson
    
    return render_template('report.html',
                          prediction=prediction,
                          conf_pct=conf_pct,
                          combined=combined,
                          draw_pct=draw_pct,
                          voice_pct=voice_pct,
                          age=age,
                          risk_text=risk_text,
                          severity=severity,
                          caution=caution,
                          total_tests=total_tests,
                          total_parkinson=total_parkinson,
                          total_no_parkinson=total_no_parkinson)





# ---------- API ROUTE ----------
@app.route("/predict", methods=["POST"])
def predict():
    global TOTAL_TESTS, TOTAL_PARKINSON, TOTAL_NO_PARKINSON


    age = request.form.get("age")
    temp_files = []


    try:
        # ------------ IMAGE ------------
        spiral_file = request.files.get("spiral_img")
        if not spiral_file:
            return jsonify({"error": "spiral_img is required"}), 400


        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_img:
            spiral_path = tmp_img.name
            temp_files.append(spiral_path)
            spiral_file.save(spiral_path)


        # ------------ VOICE (SIMPLE & BULLETPROOF) ------------
        voice_file = request.files.get("voice_wav")
        if not voice_file:
            cleanup_files(temp_files)
            return jsonify({"error": "voice_wav is required"}), 400


        original_name = voice_file.filename or "voice_input"
        ext = os.path.splitext(original_name)[1].lower()


        print(f"🎤 Received: {original_name} ({voice_file.content_length} bytes)")


        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_voice:
            raw_voice_path = tmp_voice.name
            temp_files.append(raw_voice_path)
            voice_file.save(raw_voice_path)


        # Simple WAV conversion (your multimodal_infer.py handles validation)
        final_voice_path = raw_voice_path
        if ext == ".webm":
            wav_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            wav_path = wav_temp.name
            temp_files.append(wav_path)
            wav_temp.close()
           
            try:
                audio = AudioSegment.from_file(raw_voice_path, format="webm")
                if len(audio) < 1000:
                    cleanup_files(temp_files)
                    return jsonify({"error": "Audio too short (<1s)"}), 400
                audio.export(wav_path, format="wav")
                final_voice_path = wav_path
                print(f"✅ WebM → WAV: {len(audio)}ms")
            except Exception as e:
                cleanup_files(temp_files)
                return jsonify({"error": f"Audio conversion failed: {str(e)}"}), 500


        # ------------ DRAWING INFERENCE ------------
        print("🎨 Processing drawing...")
        d_in = get_drawing_input(spiral_path)
        d_prob = float(drawing_model.predict(d_in, verbose=0).flatten()[0])


        # ------------ VOICE INFERENCE ------------
        print("🎤 Processing voice...")
        age_val = float(age) if age else 65.0
        feature_df = extract_voice_from_wav(final_voice_path, age_val)
       
        print("\n=== 🔥 ALL 19 VOICE FEATURES (age=" + str(age_val) + ") ===")
        for col in feature_df.columns:
            val = feature_df[col].iloc[0]
            print(f"{col:12}: {val:8.4f}")
        print("================================\n")


        v_scaled = voice_scaler.transform(feature_df)
        if hasattr(voice_model, "predict_proba"):
            v_prob_raw = float(voice_model.predict_proba(v_scaled)[0][1])
        else:
            v_prob_raw = float(voice_model.predict(v_scaled)[0])


        print(f"🎤 Model raw prediction: {v_prob_raw:.3f}")


        # ------------ FIXED 2-TIER CALIBRATION (RPDE <0.55 = Healthy) ------------
        jitter_pct = float(feature_df["Jitter(%)"].iloc[0])
        hnr = float(feature_df["HNR"].iloc[0])
        rpde = float(feature_df["RPDE"].iloc[0])


        # Simple quality (0-1 scale)
        audio_duration = len(AudioSegment.from_file(final_voice_path)) / 1000.0
        quality = min(1.0, audio_duration / 10.0)


        print(f"🎤 Quality: {quality:.2f} | Jitter:{jitter_pct:.4f} | HNR:{hnr:.1f} | RPDE:{rpde:.3f}")


        # HEALTHY: RPDE <0.55 (UCI standard for healthy)
        if jitter_pct < 0.015 and hnr > 17 and rpde < 0.61:
            v_prob_calibrated = max(0.15, v_prob_raw * 0.25)  # Cap at 25% max
            print(f"✅ HEALTHY: {v_prob_calibrated:.1%} (was {v_prob_raw:.1%})")
        else:
            v_prob_calibrated = v_prob_raw  # PD-like - trust model
            print(f"🔴 PD-like: {v_prob_calibrated:.1%}")


        v_prob_display = v_prob_calibrated


        # ------------ 55/45 WEIGHTING ------------
        draw_weight = 0.55
        voice_weight = 0.45
        final = draw_weight * d_prob + voice_weight * v_prob_calibrated
       
        confidence = abs(final - 0.5) * 2
        prediction_raw = "Parkinson" if final >= 0.48 else "No Parkinson"


        # ------------ RISK TEXT ------------
        if prediction_raw == "Parkinson":
            if final < 0.55:
                risk_text = "Mild Parkinson-like patterns detected. Consult neurologist."
                severity_label = "Low-Moderate risk"
            elif final < 0.70:
                risk_text = "Moderate Parkinson patterns detected. Medical evaluation recommended."
                severity_label = "Moderate risk"
            else:
                risk_text = "Strong Parkinson-like patterns. Urgent consultation needed."
                severity_label = "High risk"
        else:
            if final < 0.30:
                risk_text = "Very low chance of Parkinson features. Continue monitoring."
                severity_label = "Very low risk"
            elif final < 0.45:
                risk_text = "No significant Parkinson patterns. Healthy result."
                severity_label = "Low risk"
            else:
                risk_text = "Low Parkinson-like features. Monitor if symptoms appear."
                severity_label = "Low risk"


        # Update stats
        TOTAL_TESTS += 1
        if prediction_raw == "Parkinson":
            TOTAL_PARKINSON += 1
        else:
            TOTAL_NO_PARKINSON += 1


        # Age caution
        caution = None
        if age:
            try:
                a = float(age)
                if a < 11 or a > 75:
                    caution = f"Age {a}: Model less accurate outside 11-75 years."
            except:
                pass


        print("=== FINAL RESULT ===")
        print(f"Drawing: {d_prob:.1%} | Voice: {v_prob_display:.1%} | Final: {final:.3f}")
        print("====================")


        return jsonify({
            "prediction": prediction_raw,
            "combined_score": final,
            "confidence": confidence,
            "drawing_prob": d_prob,
            "voice_prob": v_prob_display,
            "caution": caution,
            "risk_text": risk_text,
            "severity_label": severity_label,
            "age": age or "",
            "total_tests": TOTAL_TESTS,
            "total_parkinson": TOTAL_PARKINSON,
            "total_no_parkinson": TOTAL_NO_PARKINSON,
            "voice_features_sample": {
                "Jitter(%)": jitter_pct,
                "HNR": hnr,
                "RPDE": rpde,
                "Quality": quality
            }
        })


    except Exception as e:
        print(f"❌ ERROR: {e}")
        cleanup_files(temp_files)
        return jsonify({"error": f"Prediction failed: {str(e)}"}), 500


    finally:
        cleanup_files(temp_files)



if __name__ == "__main__":

    app.run(host="0.0.0.0", port=10000, debug=True)
