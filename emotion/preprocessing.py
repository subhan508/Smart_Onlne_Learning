"""
Image Preprocessing Module
==========================
Prepares face images for CNN emotion classification.
Handles resizing, normalisation, and reshaping for model input.
"""

import numpy as np
import cv2


def preprocess_face(face_image, target_size=(48, 48)):
    """
    Preprocess a face image for CNN emotion classification.

    Pipeline:
        1. Ensure grayscale
        2. Resize to target_size (48x48 for FER2013-trained models)
        3. Normalise pixel values to [0, 1]
        4. Reshape to (1, 48, 48, 1) for model input

    Args:
        face_image: Numpy array of the face (grayscale or BGR).
        target_size: Tuple (width, height) expected by the model.

    Returns:
        Preprocessed numpy array ready for model.predict(),
        or None if the input is invalid.
    """
    if face_image is None or face_image.size == 0:
        return None

    # Convert to grayscale if needed
    if len(face_image.shape) == 3:
        face_image = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)

    # Resize
    face_resized = cv2.resize(face_image, target_size, interpolation=cv2.INTER_AREA)

    # Normalise pixel values from [0, 255] to [0, 1]
    face_normalised = face_resized.astype('float32') / 255.0

    # Reshape to (batch_size, height, width, channels) = (1, 48, 48, 1)
    face_reshaped = np.reshape(face_normalised, (1, target_size[1], target_size[0], 1))

    return face_reshaped


def decode_image_from_base64(base64_string):
    """
    Decode a base64-encoded image string into a numpy array.

    Used to convert webcam frames sent from the browser (via canvas.toDataURL)
    into OpenCV-compatible images.

    Args:
        base64_string: Base64-encoded image string (may include data URI prefix).

    Returns:
        BGR numpy array, or None if decoding fails.
    """
    import base64

    try:
        # Remove data URI prefix if present (e.g. "data:image/jpeg;base64,...")
        if ',' in base64_string:
            base64_string = base64_string.split(',')[1]

        # Decode base64 to bytes
        img_bytes = base64.b64decode(base64_string)

        # Convert to numpy array
        np_arr = np.frombuffer(img_bytes, np.uint8)

        # Decode image
        image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        return image

    except Exception as e:
        print(f'[Preprocessing] Error decoding base64 image: {e}')
        return None
