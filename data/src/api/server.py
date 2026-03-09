import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'

import sys
import tempfile
import shutil
import numpy as np
import pandas as pd
import sqlite3
import psycopg2
import tensorflow as tf
import joblib

from urllib.parse import urlparse
from collections import Counter
from pydub import AudioSegment
from flask import Flask, render_template, request, jsonify, redirect, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash

# ---------- FFmpeg ----------
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

app.secret_key = "simple_secret_key"

# ---------- MODEL PATHS ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DRAWING_MODEL_PATH = os.path.join(BASE_DIR, "models", "drawing_model_final.h5")
VOICE_MODEL_PATH = os.path.join(BASE_DIR, "models", "voice_model.pkl")
VOICE_SCALER_PATH = os.path.join(BASE_DIR, "models", "voice_scaler.pkl")

# ---------- SAFE MODEL LOADING ----------
drawing_model = None
voice_model = None
voice_scaler = None


def load_models():
    global drawing_model, voice_model, voice_scaler

    if drawing_model is None:
        print("Loading AI models...")

        drawing_model = tf.keras.models.load_model(
            DRAWING_MODEL_PATH, compile=False
        )

        voice_model = joblib.load(VOICE_MODEL_PATH)
        voice_scaler = joblib.load(VOICE_SCALER_PATH)

        print("Models loaded successfully.")


# ---------- DATABASE ----------
def get_db():

    DATABASE_URL = os.environ.get("DATABASE_URL")

    if DATABASE_URL:  # PostgreSQL on Render
        url = urlparse(DATABASE_URL)

        conn = psycopg2.connect(
            dbname=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        return conn

    else:  # Local SQLite
        return sqlite3.connect(os.path.join(CURRENT_DIR, "database.db"))


def sql(q):
    if os.environ.get("DATABASE_URL"):
        return q.replace("?", "%s")
    return q


# ---------- CLEANUP ----------
def cleanup_files(paths):
    for path in paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except:
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

        cur.execute(sql(
            "SELECT id, password FROM users WHERE username=?"
        ), (username,))

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

                cur.execute(sql(
                    "INSERT INTO users (username,password) VALUES (?,?)"
                ), (username, hashed_pw))

                db.commit()

                cur.execute(sql(
                    "SELECT id FROM users WHERE username=?"
                ), (username,))

                new_user = cur.fetchone()

                session.clear()
                session["user_id"] = new_user[0]
                session["username"] = username

                db.close()
                return redirect("/home")

            except:
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
        risk_text = "Patterns associated with Parkinson-like characteristics detected."
    else:
        risk_text = "No significant Parkinson-like patterns detected."

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


# ================= PREDICT =================
@app.route("/predict", methods=["POST"])
def predict():

    if "user_id" not in session and session.get("user") != "guest":
        return jsonify({"error": "User not logged in"}), 401

    load_models()

    temp_files = []

    try:

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

        d_prob = float(
            drawing_model.predict(
                get_drawing_input(spiral_path),
                verbose=0
            ).flatten()[0]
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

        return jsonify({
            "prediction": prediction,
            "combined_score": final_score,
            "confidence": confidence,
            "drawing_prob": d_prob,
            "voice_prob": v_prob,
            "age": age
        })

    finally:
        cleanup_files(temp_files)


# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ================= RUN =================
if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
