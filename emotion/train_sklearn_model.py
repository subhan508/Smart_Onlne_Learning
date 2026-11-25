"""
Train a scikit-learn emotion classifier on FER2013 (image folder version).
Uses HOG features + spatial intensity + MLPClassifier.
Fast training, high accuracy, and low latency inference.

Usage:
    python -m emotion.train_sklearn_model
"""

import os
import sys
import time
import cv2
import numpy as np
import joblib
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, accuracy_score

# Paths
TRAIN_DIR = os.environ.get(
    'FER2013_TRAIN',
    os.path.join(os.path.expanduser('~'),
                 '.cache', 'kagglehub', 'datasets', 'msambare',
                 'fer2013', 'versions', '1', 'train'))
TEST_DIR = os.environ.get(
    'FER2013_TEST',
    os.path.join(os.path.expanduser('~'),
                 '.cache', 'kagglehub', 'datasets', 'msambare',
                 'fer2013', 'versions', '1', 'test'))
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'models', 'emotion_model.joblib')

# FER2013 folder names → project labels
LABEL_MAP = {
    'happy': 'Happy',
    'sad': 'Sad',
    'neutral': 'Neutral',
    'angry': 'Focused',
    'disgust': 'Bored',
    'fear': 'Confused',
    'surprise': 'Confused',
}

CLASSES = ['Happy', 'Sad', 'Neutral', 'Confused', 'Bored', 'Focused']

# ── HOG Descriptor (48×48 input) ──
_hog = cv2.HOGDescriptor((48, 48), (16, 16), (8, 8), (8, 8), 9)


def extract_features(gray48):
    """Return HOG + downsampled-pixel feature vector for a 48×48 grayscale image."""
    if gray48 is None:
        return None
    if gray48.shape != (48, 48):
        gray48 = cv2.resize(gray48, (48, 48))
    hog_feat = _hog.compute(gray48).flatten()
    small = cv2.resize(gray48, (8, 8)).flatten().astype(np.float32) / 255.0
    return np.hstack([hog_feat, small])


def load_dataset(data_dir, max_per_class=1500):
    """
    Load images from FER2013 folder structure.
    Balances classes up to max_per_class and augments small classes with horizontal flip.
    """
    X, y = [], []
    class_counts = {}
    
    for folder in sorted(os.listdir(data_dir)):
        folder_path = os.path.join(data_dir, folder)
        if not os.path.isdir(folder_path):
            continue
        label = LABEL_MAP.get(folder.lower())
        if label is None:
            continue
            
        files = os.listdir(folder_path)
        loaded_for_folder = 0
        
        for fname in files:
            if class_counts.get(label, 0) >= max_per_class:
                break
            img_path = os.path.join(folder_path, fname)
            img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
            if img is not None:
                feat = extract_features(img)
                if feat is not None:
                    X.append(feat)
                    y.append(label)
                    class_counts[label] = class_counts.get(label, 0) + 1
                    loaded_for_folder += 1
                    
                    # Augment 'Bored' (disgust) with horizontal flip since it has fewer samples
                    if label == 'Bored' and class_counts[label] < max_per_class:
                        flipped = cv2.flip(img, 1)
                        f_feat = extract_features(flipped)
                        if f_feat is not None:
                            X.append(f_feat)
                            y.append(label)
                            class_counts[label] += 1
                            loaded_for_folder += 1

        print(f"  [Data] Folder '{folder}' -> Label '{label}': loaded {loaded_for_folder} (Total {label}: {class_counts[label]})", flush=True)

    return np.array(X, dtype=np.float32), np.array(y)


def main():
    if not os.path.isdir(TRAIN_DIR):
        print(f'[ERROR] Training directory not found: {TRAIN_DIR}', flush=True)
        sys.exit(1)

    print(f'[Train] Loading training data from {TRAIN_DIR} ...', flush=True)
    t0 = time.time()
    X_train, y_train = load_dataset(TRAIN_DIR, max_per_class=1500)
    print(f'[Train] Loaded {len(X_train)} training samples, feature dim {X_train.shape[1]} in {time.time()-t0:.1f}s', flush=True)

    X_test, y_test = None, None
    if os.path.isdir(TEST_DIR):
        print(f'[Train] Loading test data from {TEST_DIR} ...', flush=True)
        t0 = time.time()
        X_test, y_test = load_dataset(TEST_DIR, max_per_class=300)
        print(f'[Train] Loaded {len(X_test)} test samples in {time.time()-t0:.1f}s', flush=True)

    print('[Train] Training StandardScaler + MLPClassifier pipeline ...', flush=True)
    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('mlp', MLPClassifier(
            hidden_layer_sizes=(256, 128),
            activation='relu',
            solver='adam',
            alpha=0.001,
            batch_size=128,
            max_iter=35,
            early_stopping=True,
            validation_fraction=0.1,
            n_iter_no_change=5,
            random_state=42,
            verbose=True,
        )),
    ])

    t0 = time.time()
    pipeline.fit(X_train, y_train)
    elapsed = time.time() - t0
    print(f'[Train] Training completed in {elapsed:.1f}s', flush=True)

    if X_test is not None:
        y_pred = pipeline.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        print(f'\n[Eval] Test Accuracy: {acc:.4f}', flush=True)
        print(classification_report(y_test, y_pred, target_names=sorted(list(set(y_test)))), flush=True)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    joblib.dump({'pipeline': pipeline, 'classes': list(pipeline.classes_)}, OUTPUT_PATH)
    size_mb = os.path.getsize(OUTPUT_PATH) / 1024 / 1024
    print(f'[Train] Model successfully saved to {OUTPUT_PATH} ({size_mb:.2f} MB)', flush=True)


if __name__ == '__main__':
    main()
