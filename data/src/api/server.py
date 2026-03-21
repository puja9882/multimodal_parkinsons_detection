import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'

import sys
import tempfile
import shutil
from flask.helpers import url_for
import numpy as np
import pandas as pd
from flask import Flask, render_template, request, jsonify, redirect, session
import sqlite3
import psycopg2
import tensorflow as tf
import joblib
from collections import Counter
from pydub import AudioSegment
from werkzeug.security import generate_password_hash, check_password_hash
from tensorflow.keras.layers import InputLayer
from tensorflow.keras.mixed_precision import Policy

class FixedInputLayer(InputLayer):
    def __init__(self, batch_shape=None, **kwargs):
        if batch_shape is not None:
            kwargs["batch_input_shape"] = batch_shape
        super().__init__(**kwargs)

custom_objects = {
    "InputLayer": FixedInputLayer,
    "DTypePolicy": Policy
}

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
from flask_cors import CORS
CORS(app)

app.secret_key = "simple_secret_key"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(BASE_DIR)

DRAWING_MODEL_PATH = os.path.join(SRC_DIR, "models", "drawing_model_fixed.keras")
VOICE_MODEL_PATH = os.path.join(SRC_DIR, "models", "voice_model.pkl")
VOICE_SCALER_PATH = os.path.join(SRC_DIR, "models", "voice_scaler.pkl")

# ===== Lazy loading placeholders =====
drawing_model = None
voice_model = None
voice_scaler = None

print("Server started. Models will load when prediction runs.")

# ---------- DATABASE ----------
from urllib.parse import urlparse

DB_TYPE = "sqlite"

def get_db():
    global DB_TYPE

    DATABASE_URL = os.environ.get("DATABASE_URL")

    if DATABASE_URL:
        DB_TYPE = "postgres"
        url = urlparse(DATABASE_URL)

        conn = psycopg2.connect(
            dbname=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        return conn
    else:
        DB_TYPE = "sqlite"
        return sqlite3.connect(os.path.join(CURRENT_DIR, "database.db"))

# ---------- DATABASE INIT ----------
def init_db():

    db = get_db()
    cur = db.cursor()

    if DB_TYPE == "postgres":

        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            name TEXT,
            age TEXT,
            prediction TEXT,
            combined_score FLOAT,
            confidence FLOAT,
            drawing_prob FLOAT,
            voice_prob FLOAT,
            risk_text TEXT,
            severity TEXT,
            caution TEXT,
            test_date TIMESTAMP
        )
        """)

    else:

        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            age TEXT,
            prediction TEXT,
            combined_score REAL,
            confidence REAL,
            drawing_prob REAL,
            voice_prob REAL,
            risk_text TEXT,
            severity TEXT,
            caution TEXT,
            test_date TIMESTAMP
        )
        """)

    db.commit()
    db.close()
    
# ---------- GLOBAL STATS ----------
TOTAL_TESTS = 0
TOTAL_PARKINSON = 0
TOTAL_NO_PARKINSON = 0


def cleanup_files(paths):
    for path in paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass


# ================= LOGIN =================
@app.route("/", methods=["GET", "POST"])
def login():

    error = None

    if request.method == "POST":

        if "guest" in request.form:
            session.clear()
            session["user"] = "guest"
            return redirect("/home")

        username = request.form["username"].strip()
        password = request.form["password"].strip()

        db = get_db()
        cur = db.cursor()

        placeholder = "%s" if DB_TYPE == "postgres" else "?"

        cur.execute(f"SELECT id, password FROM users WHERE username={placeholder}", (username,))
        user = cur.fetchone()

        if user:
            if check_password_hash(user[1], password):
                session.clear()
                session["user_id"] = user[0]
                session["username"] = username
                db.close()
                return redirect("/home")
            else:
                error = "Incorrect password."

        else:

            hashed_pw = generate_password_hash(password)

            try:
                cur.execute(
                    f"INSERT INTO users (username, password) VALUES ({placeholder}, {placeholder})",
                    (username, hashed_pw)
                )

                db.commit()

                cur.execute(f"SELECT id FROM users WHERE username={placeholder}", (username,))
                new_user = cur.fetchone()

                session.clear()
                session["user_id"] = new_user[0]
                session["username"] = username

                db.close()

                return redirect("/home")

            except sqlite3.IntegrityError:
                error = "Username already exists."
                db.close()

    return render_template("login.html", error=error)


# ================= HOME =================
@app.route("/home")
def home():

    if "user_id" not in session and session.get("user") != "guest":
        return redirect("/")

    return render_template("home.html")


# ================= SCREENING =================
@app.route("/screening")
def screening():

    if "user_id" not in session and session.get("user") != "guest":
        return redirect("/")

    return render_template("screening.html")


# ================= ABOUT =================
@app.route("/about")
def about():
    return render_template("about.html")


# ================= REPORT =================
@app.route("/report")
def report():

    prediction = request.args.get("prediction", "Not available")
    conf_pct = int(float(request.args.get("conf", 0)))
    combined = request.args.get("combined", "0.000")
    draw_pct = request.args.get("draw", "0")
    voice_pct = request.args.get("voice", "0")

    name = request.args.get("name", "Not provided")
    age = request.args.get("age", "Not provided")

    combined_float = float(combined)

    if prediction == "Parkinson":
        risk_text = "The AI detected motor and/or voice patterns associated with Parkinson-like characteristics. Further neurological evaluation is recommended."
    else:
        risk_text = "The AI did not detect significant Parkinson-like patterns in this screening session."

    if combined_float < 0.30:
        severity = "Low Risk"
    elif combined_float < 0.60:
        severity = "Moderate Risk"
    else:
        severity = "High Risk"

    return render_template(
        "report.html",
        prediction=prediction,
        conf_pct=conf_pct,
        combined=combined,
        draw_pct=draw_pct,
        voice_pct=voice_pct,
        name=name,
        age=age,
        severity=severity,
        risk_text=risk_text
    )


# ================= PREDICTION =================
@app.route("/predict", methods=["POST"])
def predict():

    global TOTAL_TESTS, TOTAL_PARKINSON, TOTAL_NO_PARKINSON
    global drawing_model, voice_model, voice_scaler

    # ===== Lazy load models here =====
    if drawing_model is None:
        drawing_model = tf.keras.models.load_model(
            DRAWING_MODEL_PATH,
            compile=False        
        )

    if voice_model is None:
        voice_model = joblib.load(VOICE_MODEL_PATH)

    if voice_scaler is None:
        voice_scaler = joblib.load(VOICE_SCALER_PATH)

    if "user_id" not in session and session.get("user") != "guest":
        return jsonify({"error": "User not logged in"}), 401

    temp_files = []

    try:
        print("Prediction request received")

        spiral_file = request.files.get("spiral_img")
        voice_file = request.files.get("voice_wav")
        name = request.form.get("name", "Not provided")
        age = request.form.get("age", "Not provided")

        if not spiral_file or not voice_file:
            return jsonify({"error": "Missing input"}), 400

        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as img:
            spiral_path = img.name
            spiral_file.save(spiral_path)
            temp_files.append(spiral_path)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as wav:
            voice_path = wav.name
            voice_file.save(voice_path)
            temp_files.append(voice_path)

        drawing_input = get_drawing_input(spiral_path, drawing_model)
        d_prob = float(
            drawing_model.predict(drawing_input, verbose=0).flatten()[0]
        )

        feature_df = extract_voice_from_wav(voice_path, 65.0)

        v_prob = float(
            voice_model.predict_proba(
                voice_scaler.transform(feature_df)
            )[0][1]
        )

        final_score = 0.55 * d_prob + 0.45 * v_prob
        confidence = abs(final_score - 0.5) * 2
        prediction = "Parkinson" if final_score >= 0.48 else "No Parkinson"

        TOTAL_TESTS += 1
        TOTAL_PARKINSON += prediction == "Parkinson"
        TOTAL_NO_PARKINSON += prediction == "No Parkinson"

        confidence_text = (
            "Low confidence" if confidence < 0.33 else
            "Moderate confidence" if confidence < 0.66 else
            "High confidence"
        )

        return jsonify({
            "prediction": prediction,
            "combined_score": final_score,
            "confidence": confidence,
            "confidence_text": confidence_text,
            "drawing_prob": d_prob,
            "voice_prob": v_prob,
            "age": age
        })

    except Exception as e:
        import traceback  # ✅ FIXED POSITION
        print("🔥🔥 FULL ERROR BELOW 🔥🔥")
        traceback.print_exc()

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

    finally:
        cleanup_files(temp_files)



# ================= HISTORY =================
@app.route("/history")
def history():

    if "user_id" not in session:
        return redirect("/")

    db = get_db()
    cur = db.cursor()

    placeholder = "%s" if DB_TYPE == "postgres" else "?"

    cur.execute(f"""
        SELECT id, test_date, name, age, prediction,
               combined_score, confidence,
               drawing_prob, voice_prob, severity
        FROM reports
        WHERE user_id = {placeholder}
        ORDER BY id DESC
    """, (session["user_id"],))

    reports = cur.fetchall()
    db.close()

    return render_template("history.html", reports=reports)


# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor()

    placeholder = "%s" if DB_TYPE == "postgres" else "?"

    user_id = session["user_id"]

    cur.execute(f"SELECT COUNT(*) FROM reports WHERE user_id={placeholder}", (user_id,))
    total = cur.fetchone()[0]

    cur.execute(f"SELECT COUNT(*) FROM reports WHERE user_id={placeholder} AND prediction='Parkinson'", (user_id,))
    parkinson_count = cur.fetchone()[0]

    cur.execute(f"SELECT COUNT(*) FROM reports WHERE user_id={placeholder} AND prediction='No Parkinson'", (user_id,))
    normal_count = cur.fetchone()[0]

    cur.execute(f"SELECT AVG(combined_score) FROM reports WHERE user_id={placeholder}", (user_id,))
    avg_score = cur.fetchone()[0]
    avg_score = round(avg_score, 3) if avg_score else 0

    cur.execute(f"""
        SELECT severity, COUNT(*)
        FROM reports
        WHERE user_id={placeholder}
        GROUP BY severity
    """, (user_id,))

    risk_data = cur.fetchall()

    conn.close()

    risk_labels = [row[0] for row in risk_data]
    risk_counts = [row[1] for row in risk_data]

    trend_dates = []
    trend_values = []

    return render_template(
        "dashboard.html",
        total=total,
        parkinson_count=parkinson_count,
        normal_count=normal_count,
        avg_score=avg_score,
        risk_labels=risk_labels,
        risk_counts=risk_counts,
        trend_dates=trend_dates,
        trend_values=trend_values
    )


# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

init_db()

# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
