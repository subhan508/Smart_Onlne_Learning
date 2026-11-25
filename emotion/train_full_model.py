"""
Train High-Accuracy Emotion Classifier on FULL FER2013 Dataset (35,800+ images)
with Data Augmentation (Horizontal Flips = 71,000+ samples) and Multi-Region HOG Features.

Outputs:
    models/emotion_model.joblib
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

# Multi-region HOG Descriptors
hog_full = cv2.HOGDescriptor((48, 48), (16, 16), (8, 8), (8, 8), 9)
hog_region = cv2.HOGDescriptor((48, 24), (16, 16), (8, 8), (8, 8), 9)


def extract_features(gray48):
    """
    Extract 1684-dimensional feature vector:
      - Full face HOG: 900
      - Upper face (eyes & brows) HOG: 324
      - Lower face (mouth & chin) HOG: 324
      - 8x8 spatial intensity grid: 64
    """
    if gray48 is None:
        return None
    if gray48.shape != (48, 48):
        gray48 = cv2.resize(gray48, (48, 48))
        
    f_full = hog_full.compute(gray48).flatten()
    f_upper = hog_region.compute(gray48[0:24, :]).flatten()
    f_lower = hog_region.compute(gray48[24:48, :]).flatten()
    small = cv2.resize(gray48, (8, 8)).flatten().astype(np.float32) / 255.0
    
    return np.hstack([f_full, f_upper, f_lower, small])


def load_all_data(data_dir, augment_flip=True):
    X, y = [], []
    class_counts = {}
    t0 = time.time()
    
    folders = sorted(os.listdir(data_dir))
    for folder in folders:
        folder_path = os.path.join(data_dir, folder)
        if not os.path.isdir(folder_path):
            continue
        label = LABEL_MAP.get(folder.lower())
        if label is None:
            continue
            
        files = os.listdir(folder_path)
        loaded = 0
        
        for fname in files:
            img_path = os.path.join(folder_path, fname)
            img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
            if img is not None:
                feat = extract_features(img)
                if feat is not None:
                    X.append(feat)
                    y.append(label)
                    class_counts[label] = class_counts.get(label, 0) + 1
                    loaded += 1
                    
                    # Horizontal flip data augmentation
                    if augment_flip:
                        flipped = cv2.flip(img, 1)
                        f_feat = extract_features(flipped)
                        if f_feat is not None:
                            X.append(f_feat)
                            y.append(label)
                            class_counts[label] += 1
                            loaded += 1
                            
                    # For Bored (disgust), add additional vertical/lighting variation since original only has 436 samples
                    if label == 'Bored' and augment_flip:
                        bright = cv2.convertScaleAbs(img, alpha=1.1, beta=10)
                        b_feat = extract_features(bright)
                        if b_feat is not None:
                            X.append(b_feat)
                            y.append(label)
                            class_counts[label] += 1
                            loaded += 1

        print(f"  [Data] Folder '{folder}' -> '{label}': {loaded} samples (Total {label}: {class_counts[label]})", flush=True)

    print(f"[Data] Loaded total {len(X)} samples in {time.time()-t0:.1f}s", flush=True)
    return np.array(X, dtype=np.float32), np.array(y)


def main():
    print(f"=== Training Emotion Model on Full Dataset ===", flush=True)
    print(f"Loading training images from {TRAIN_DIR} ...", flush=True)
    X_train, y_train = load_all_data(TRAIN_DIR, augment_flip=True)
    
    print(f"Loading test images from {TEST_DIR} ...", flush=True)
    X_test, y_test = load_all_data(TEST_DIR, augment_flip=False)
    
    print(f"Training dataset: {len(X_train)} samples, feature dimension: {X_train.shape[1]}", flush=True)
    print(f"Test dataset:     {len(X_test)} samples", flush=True)

    print("\nTraining StandardScaler + MLPClassifier pipeline...", flush=True)
    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('mlp', MLPClassifier(
            hidden_layer_sizes=(384, 192),
            activation='relu',
            solver='adam',
            alpha=0.002,
            batch_size=256,
            max_iter=30,
            early_stopping=True,
            validation_fraction=0.1,
            n_iter_no_change=5,
            random_state=42,
            verbose=True,
        )),
    ])

    t0 = time.time()
    pipeline.fit(X_train, y_train)
    print(f"Training finished in {time.time()-t0:.1f}s", flush=True)

    print("\nEvaluating on unseen test set...", flush=True)
    y_pred = pipeline.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"Test Accuracy: {acc:.4f}", flush=True)
    print(classification_report(y_test, y_pred, target_names=sorted(list(set(y_test)))), flush=True)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    joblib.dump({'pipeline': pipeline, 'classes': list(pipeline.classes_)}, OUTPUT_PATH)
    size_mb = os.path.getsize(OUTPUT_PATH) / 1024 / 1024
    print(f"\nModel saved to {OUTPUT_PATH} ({size_mb:.2f} MB)", flush=True)


if __name__ == '__main__':
    main()

