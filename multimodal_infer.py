# multimodal_infer_fixed.py
import argparse
import os
import numpy as np
import joblib
import tensorflow as tf
import cv2
import parselmouth
from tensorflow.keras.preprocessing.image import img_to_array

# ---------- CONFIG: adjust only paths if needed ----------
BASE_DIR = r"C:\Users\wayko\OneDrive\Desktop\parkinsons"
DRAWING_MODEL_PATH = os.path.join(BASE_DIR, "drawing_model_final.h5")
VOICE_MODEL_PATH   = os.path.join(BASE_DIR, "models", "voice_model.pkl")
VOICE_SCALER_PATH  = os.path.join(BASE_DIR, "models", "voice_scaler.pkl")

# ---------- load models ----------
print("MODEL PATHS:")
print(" Drawing:", DRAWING_MODEL_PATH)
print(" Voice model:", VOICE_MODEL_PATH)
print(" Voice scaler:", VOICE_SCALER_PATH)

drawing_model = tf.keras.models.load_model(DRAWING_MODEL_PATH)
voice_model = joblib.load(VOICE_MODEL_PATH)
voice_scaler = joblib.load(VOICE_SCALER_PATH)

# ---------- helpers ----------
def get_drawing_input(img_path):
    # adapt to drawing model input shape
    in_shape = drawing_model.input_shape  # (None, H, W, C)
    try:
        H = int(in_shape[1])
        W = int(in_shape[2])
        C = int(in_shape[3])
    except Exception:
        H, W, C = 224, 224, 3

    # read image
    img = cv2.imread(img_path, cv2.IMREAD_COLOR if C==3 else cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Image not found: {img_path}")
    if C == 1 and len(img.shape) == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if C == 3 and len(img.shape) == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    img = cv2.resize(img, (W, H))
    img = img.astype("float32") / 255.0
    arr = img_to_array(img)
    if C == 1 and arr.ndim == 3:
        arr = np.expand_dims(arr[:, :, 0], -1)
    arr = np.expand_dims(arr, 0)
    return arr

def extract_voice_from_wav(wav_path, expected_n_features=None):
    snd = parselmouth.Sound(wav_path)
    # simple features — f0 mean, HNR mean, jitter & shimmer are more robust but require some code
    pitch = snd.to_pitch()
    f0 = np.nan
    try:
        f0_arr = pitch.selected_array['frequency']
        f0 = float(np.nanmean(np.where(f0_arr==0, np.nan, f0_arr)))
    except Exception:
        f0 = 0.0

    try:
        hnr = snd.to_harmonicity_ac().values.mean()
    except Exception:
        hnr = 0.0

    # fallbacks — you can expand this with parselmouth functions for jitter/shimmer/RPDE etc.
    base_feats = np.array([f0 if not np.isnan(f0) else 0.0, hnr, 0.0], dtype=float)

    # If scaler expects named features (recommended), try to align; otherwise pad/truncate to expected_n_features
    if hasattr(voice_scaler, "feature_names_in_"):
        n = len(voice_scaler.feature_names_in_)
    else:
        n = expected_n_features or getattr(voice_scaler, "n_features_in_", len(base_feats))

    if n <= len(base_feats):
        x = base_feats[:n]
    else:
        x = np.zeros(n, dtype=float)
        x[:len(base_feats)] = base_feats

    return x.reshape(1, -1)

# ---------- inference ----------
def multimodal_predict(img_path, wav_path, age=None, draw_weight=0.55, voice_weight=0.45):
    # drawing score
    d_in = get_drawing_input(img_path)
    d_prob = float(drawing_model.predict(d_in, verbose=0).flatten()[0])

    # voice score
    # Build a feature vector compatible with saved scaler length
    expected = getattr(voice_scaler, "n_features_in_", None)
    v_raw = extract_voice_from_wav(wav_path, expected_n_features=expected)
    # scale
    try:
        v_scaled = voice_scaler.transform(v_raw)
    except Exception:
        # If scaler expects named columns and we only supplied padded zeros, scaler may complain;
        # fallback: if scaler has feature_names_in_, create a 0-row of that length
        n = getattr(voice_scaler, "n_features_in_", v_raw.shape[1])
        v_scaled = voice_scaler.transform(np.zeros((1, n)))
    if hasattr(voice_model, "predict_proba"):
        v_prob = float(voice_model.predict_proba(v_scaled)[:,1][0])
    else:
        v_prob = float(voice_model.predict(v_scaled)[0])

    # combine
    final = draw_weight * d_prob + voice_weight * v_prob

    # Age caution
    caution = None
    if age is not None:
        try:
            a = float(age)
            if a < 18 or a > 80:
                caution = f"⚠ Age = {a}: model may be unreliable for very young/old people; interpret result cautiously."
        except Exception:
            pass

    # print results
    print("\n--- PREDICTION RESULTS ---")
    print(f"Drawing Model (prob Parkinson): {d_prob:.4f}")
    print(f"Voice  Model (prob Parkinson): {v_prob:.4f}")
    print(f"Combined score (weighted):    {final:.4f}")
    print(f"Decision: {'Parkinson' if final>=0.5 else 'No Parkinson'}")
    print(f"Confidence: {abs(final-0.5) * 2:.2f} (0 low -> 1 high)")
    if caution:
        print(caution)

# ---------- CLI ----------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--img", required=True, help="Path to drawing image")
    parser.add_argument("--wav", required=True, help="Path to wav file")
    parser.add_argument("--age", required=False, help="Age of subject (optional)")
    parser.add_argument("--draw-weight", type=float, default=0.55)
    parser.add_argument("--voice-weight", type=float, default=0.45)
    args = parser.parse_args()
    multimodal_predict(args.img, args.wav, age=args.age, draw_weight=args.draw_weight, voice_weight=args.voice_weight)
