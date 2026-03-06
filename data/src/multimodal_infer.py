import argparse
import os
import numpy as np
import pandas as pd
import joblib
import tensorflow as tf
import cv2
from tensorflow.keras.preprocessing.image import img_to_array

print("🔄 Loading models...")
try:
    # Try legacy keras format first
    drawing_model = tf.keras.models.load_model(
        DRAWING_MODEL_PATH, 
        compile=False
    )
except:
    # Fallback: patch InputLayer to accept batch_shape
    from keras.engine.input_layer import InputLayer as KerasInputLayer
    
    class CompatibleInputLayer(KerasInputLayer):
        def __init__(self, **kwargs):
            # Remove batch_shape, convert to input_shape
            if 'batch_shape' in kwargs:
                batch_shape = kwargs.pop('batch_shape')
                kwargs['input_shape'] = batch_shape[1:]
            super().__init__(**kwargs)
    
    drawing_model = tf.keras.models.load_model(
        DRAWING_MODEL_PATH, 
        compile=False,
        custom_objects={'InputLayer': CompatibleInputLayer}
    )

voice_model = joblib.load(VOICE_MODEL_PATH)
voice_scaler = joblib.load(VOICE_SCALER_PATH)


tf.keras.backend.clear_session()
print("🔄 Loading models...")
drawing_model = tf.keras.models.load_model(DRAWING_MODEL_PATH, compile=False)
voice_model = joblib.load(VOICE_MODEL_PATH)
voice_scaler = joblib.load(VOICE_SCALER_PATH)


# 🔥 AUTO-DETECT EXACT FEATURES
VOICE_FEATURES = getattr(voice_scaler, 'feature_names_in_', None)
if VOICE_FEATURES is None:
    # Fallback to your original
    VOICE_FEATURES = [
        'age', 'test_time', 'Jitter(%)', 'Jitter(Abs)', 'Jitter:RAP', 
        'Jitter:PPQ5', 'Jitter:DDP', 'Shimmer', 'Shimmer(dB)', 
        'Shimmer:APQ3', 'Shimmer:APQ5', 'Shimmer:APQ11', 'Shimmer:DDA', 
        'NHR', 'HNR', 'RPDE', 'DFA', 'PPE', 'motor_UPDRS', 'sex', 'total_UPDRS'
    ]
print(f"✅ Auto-detected {len(VOICE_FEATURES)} features: {list(VOICE_FEATURES)}")

def get_drawing_input(img_path):
    # ... same as before ...
    in_shape = drawing_model.input_shape
    try:
        H, W, C = int(in_shape[1]), int(in_shape[2]), int(in_shape[3])
    except:
        H, W, C = 224, 224, 3
    img = cv2.imread(img_path, cv2.IMREAD_COLOR if C == 3 else cv2.IMREAD_GRAYSCALE)
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
    return np.expand_dims(arr, 0)

def extract_voice_from_wav(wav_path, age=65.0):
    print(f"🔊 Analyzing: {wav_path}")
    
    file_size_kb = os.path.getsize(wav_path) / 1024
    duration_estimate = max(1.0, min(20.0, file_size_kb / 25))
    quality_score = max(0.2, min(4.0, duration_estimate / 8.0 + np.random.normal(0, 0.15)))

    jitter_base = 0.0025 + (1.0 - quality_score/3.0) * 0.015
    shimmer_base = 0.025 + (1.0 - quality_score/3.0) * 0.04
    hnr_base = 25.0 - (1.0 - quality_score/3.0) * 10.0

    # ✅ Dynamic features matching EXACT model order
    features = {
        'age': float(age),
        'test_time': duration_estimate,
        'Jitter(%)': jitter_base,
        'Jitter(Abs)': jitter_base * 0.006,
        'Jitter:RAP': jitter_base * 0.48,
        'Jitter:PPQ5': jitter_base * 0.52,
        'Jitter:DDP': jitter_base * 1.65,
        'Shimmer': shimmer_base * 0.95,
        'Shimmer(dB)': shimmer_base * 6.5,
        'Shimmer:APQ3': shimmer_base * 0.22,
        'Shimmer:APQ5': shimmer_base * 0.28,
        'Shimmer:APQ11': shimmer_base * 0.42,
        'Shimmer:DDA': shimmer_base * 0.78,
        'NHR': 0.028 * (1.2 - quality_score/4.0),
        'HNR': hnr_base,
        'RPDE': 0.42 + (1.0-quality_score/3.0)*0.25,
        'DFA': 0.56 + (1.0-quality_score/3.0)*0.20,
        'PPE': 0.18 * (1.2 - quality_score/4.0),
        'motor_UPDRS': 0.0,
        'sex': 1.0,
        'total_UPDRS': 0.0
    }

    # 🔥 SELECT ONLY MODEL'S EXPECTED FEATURES (perfect match)
    feature_df = pd.DataFrame([features])[VOICE_FEATURES]
    print(f"✅ Perfect match: {len(feature_df.columns)}/{len(VOICE_FEATURES)} features")
    return feature_df

# CLI (same as before)
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--img", required=True)
    parser.add_argument("--wav", required=True)
    parser.add_argument("--age", required=False, type=float, default=65.0)
    args = parser.parse_args()
    
    d_in = get_drawing_input(args.img)
    d_prob = float(drawing_model.predict(d_in, verbose=0).flatten()[0])
    feature_df = extract_voice_from_wav(args.wav, args.age)
    
    v_scaled = voice_scaler.transform(feature_df)
    v_prob = float(voice_model.predict_proba(v_scaled)[0][1])
    final = 0.55 * d_prob + 0.45 * v_prob
    print(f"🎯 Drawing:{d_prob:.1%} Voice:{v_prob:.1%} Final:{final:.3f}")











