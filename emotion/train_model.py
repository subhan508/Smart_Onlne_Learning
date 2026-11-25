"""
CNN Emotion Model Training Pipeline
====================================
Complete pipeline for training a CNN-based facial emotion classifier
on the FER2013 dataset.

Dataset: FER2013 (https://www.kaggle.com/datasets/msambare/fer2013)
    - 35,887 grayscale 48x48 images
    - 7 emotion categories: Angry, Disgust, Fear, Happy, Sad, Surprise, Neutral

Usage:
    python -m emotion.train_model --data_path path/to/fer2013.csv --epochs 50

The trained model is saved to models/emotion_model.h5

NOTE: Training requires TensorFlow and a GPU is recommended (training on CPU
may take several hours). For development, use the pre-provided model or the
fallback prediction mode.
"""

import os
import argparse
import numpy as np


def load_fer2013(csv_path):
    """
    Load and parse the FER2013 CSV dataset.
    
    The CSV has columns: emotion, pixels, Usage
    - emotion: integer 0-6
    - pixels: space-separated pixel values (48*48 = 2304 values)
    - Usage: 'Training', 'PublicTest', or 'PrivateTest'
    """
    import pandas as pd

    print(f'[Train] Loading dataset from {csv_path}...')
    df = pd.read_csv(csv_path)

    # Parse pixel strings into numpy arrays
    pixels = df['pixels'].apply(lambda x: np.fromstring(x, sep=' ', dtype=np.float32))
    X = np.stack(pixels.values)
    X = X.reshape(-1, 48, 48, 1)  # Reshape to (N, 48, 48, 1)
    X = X / 255.0  # Normalise to [0, 1]

    y = df['emotion'].values

    # Split by Usage column
    train_mask = df['Usage'] == 'Training'
    test_mask = df['Usage'] != 'Training'

    X_train, y_train = X[train_mask], y[train_mask]
    X_test, y_test = X[test_mask], y[test_mask]

    print(f'[Train] Loaded {len(X_train)} training and {len(X_test)} test images.')
    return X_train, y_train, X_test, y_test


def build_cnn_model(num_classes=7, input_shape=(48, 48, 1)):
    """
    Build a CNN architecture for facial emotion classification.
    
    Architecture:
        - 3 Convolutional blocks (Conv2D → BatchNorm → ReLU → MaxPool → Dropout)
        - 2 Dense layers with dropout
        - Softmax output
    """
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import (
        Conv2D, MaxPooling2D, Dense, Dropout, Flatten,
        BatchNormalization, Input
    )

    model = Sequential([
        Input(shape=input_shape),

        # Block 1
        Conv2D(64, (3, 3), padding='same', activation='relu'),
        BatchNormalization(),
        Conv2D(64, (3, 3), padding='same', activation='relu'),
        BatchNormalization(),
        MaxPooling2D(pool_size=(2, 2)),
        Dropout(0.25),

        # Block 2
        Conv2D(128, (3, 3), padding='same', activation='relu'),
        BatchNormalization(),
        Conv2D(128, (3, 3), padding='same', activation='relu'),
        BatchNormalization(),
        MaxPooling2D(pool_size=(2, 2)),
        Dropout(0.25),

        # Block 3
        Conv2D(256, (3, 3), padding='same', activation='relu'),
        BatchNormalization(),
        Conv2D(256, (3, 3), padding='same', activation='relu'),
        BatchNormalization(),
        MaxPooling2D(pool_size=(2, 2)),
        Dropout(0.25),

        # Fully Connected
        Flatten(),
        Dense(512, activation='relu'),
        BatchNormalization(),
        Dropout(0.5),
        Dense(256, activation='relu'),
        BatchNormalization(),
        Dropout(0.5),

        # Output
        Dense(num_classes, activation='softmax')
    ])

    model.compile(
        optimizer='adam',
        loss='sparse_categorical_crossentropy',
        metrics=['accuracy']
    )

    return model


def train_model(X_train, y_train, X_test, y_test, epochs=50, batch_size=64, save_path='models/emotion_model.h5'):
    """
    Train the CNN model with callbacks for early stopping and learning rate reduction.
    """
    from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau, ModelCheckpoint
    from tensorflow.keras.preprocessing.image import ImageDataGenerator

    model = build_cnn_model()
    model.summary()

    # Data augmentation for training
    datagen = ImageDataGenerator(
        rotation_range=15,
        width_shift_range=0.1,
        height_shift_range=0.1,
        horizontal_flip=True,
        zoom_range=0.1
    )
    datagen.fit(X_train)

    # Callbacks
    callbacks = [
        EarlyStopping(monitor='val_accuracy', patience=10, restore_best_weights=True, verbose=1),
        ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=5, min_lr=1e-6, verbose=1),
        ModelCheckpoint(save_path, monitor='val_accuracy', save_best_only=True, verbose=1)
    ]

    # Ensure save directory exists
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    # Train
    print(f'\n[Train] Starting training for {epochs} epochs...\n')
    history = model.fit(
        datagen.flow(X_train, y_train, batch_size=batch_size),
        validation_data=(X_test, y_test),
        epochs=epochs,
        callbacks=callbacks,
        verbose=1
    )

    return model, history


def evaluate_model(model, X_test, y_test):
    """
    Evaluate the model and compute accuracy, precision, recall, and F1-score.
    """
    from sklearn.metrics import classification_report, confusion_matrix, accuracy_score

    # Predict
    y_pred_probs = model.predict(X_test, verbose=0)
    y_pred = np.argmax(y_pred_probs, axis=1)

    # Metrics
    accuracy = accuracy_score(y_test, y_pred)
    print(f'\n[Eval] Overall Accuracy: {accuracy:.4f} ({accuracy * 100:.2f}%)\n')

    # Per-class report
    labels = ['Angry', 'Disgust', 'Fear', 'Happy', 'Sad', 'Surprise', 'Neutral']
    report = classification_report(y_test, y_pred, target_names=labels, digits=4)
    print('[Eval] Classification Report:')
    print(report)

    # Confusion matrix
    cm = confusion_matrix(y_test, y_pred)
    print('[Eval] Confusion Matrix:')
    print(cm)

    return {
        'accuracy': accuracy,
        'report': report,
        'confusion_matrix': cm
    }


def main():
    parser = argparse.ArgumentParser(description='Train CNN Emotion Classification Model')
    parser.add_argument('--data_path', type=str, required=True,
                        help='Path to FER2013 CSV file')
    parser.add_argument('--epochs', type=int, default=50,
                        help='Number of training epochs (default: 50)')
    parser.add_argument('--batch_size', type=int, default=64,
                        help='Batch size (default: 64)')
    parser.add_argument('--save_path', type=str, default='models/emotion_model.h5',
                        help='Path to save the trained model')
    args = parser.parse_args()

    # Load data
    X_train, y_train, X_test, y_test = load_fer2013(args.data_path)

    # Train
    model, history = train_model(
        X_train, y_train, X_test, y_test,
        epochs=args.epochs,
        batch_size=args.batch_size,
        save_path=args.save_path
    )

    # Evaluate
    results = evaluate_model(model, X_test, y_test)

    print(f'\n[Done] Model saved to {args.save_path}')
    print(f'[Done] Final accuracy: {results["accuracy"]:.4f}')


if __name__ == '__main__':
    main()
