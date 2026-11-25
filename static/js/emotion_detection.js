/**
 * Smart Online Learning System — Webcam Emotion Detection Client
 * ==============================================================
 * Handles webcam access, frame capture, and communication with the
 * Flask API for real-time emotion detection.
 *
 * Privacy: No raw video is stored — only AI-estimated emotion labels
 * are sent to and stored on the server.
 */

let webcamStream = null;
let detectionInterval = null;
let isDetecting = false;

// Detection interval in milliseconds (matches config.py EMOTION_DETECTION_INTERVAL)
const DETECTION_INTERVAL_MS = 3000;

/**
 * Start the webcam and begin emotion detection.
 */
async function startEmotionDetection() {
    const video = document.getElementById('webcamVideo');
    const container = document.getElementById('webcamContainer');
    const placeholder = document.getElementById('webcamPlaceholder');
    const startBtn = document.getElementById('startDetectionBtn');
    const stopBtn = document.getElementById('stopDetectionBtn');
    const errorDiv = document.getElementById('webcamError');

    // Hide previous errors
    errorDiv.style.display = 'none';

    try {
        // Request webcam permission
        webcamStream = await navigator.mediaDevices.getUserMedia({
            video: {
                width: { ideal: 320 },
                height: { ideal: 240 },
                facingMode: 'user'
            },
            audio: false
        });

        // Display webcam feed
        video.srcObject = webcamStream;
        container.style.display = 'block';
        placeholder.style.display = 'none';
        startBtn.style.display = 'none';
        stopBtn.style.display = '';

        isDetecting = true;

        // Remember that detection is active across page navigations
        sessionStorage.setItem('emotionDetectionActive', 'true');

        // Start periodic detection
        detectionInterval = setInterval(captureAndDetect, DETECTION_INTERVAL_MS);

        // Also run immediately
        setTimeout(captureAndDetect, 500);

    } catch (error) {
        let errorMsg = 'Unable to access webcam.';

        if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
            errorMsg = 'Camera permission denied. Please allow camera access in your browser settings and refresh the page.';
        } else if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
            errorMsg = 'No camera found. Please connect a webcam and try again.';
        } else if (error.name === 'NotReadableError') {
            errorMsg = 'Camera is in use by another application. Please close it and try again.';
        } else if (error.name === 'OverconstrainedError') {
            errorMsg = 'Camera does not meet the required specifications.';
        }

        showWebcamError(errorMsg);
        console.error('[Emotion] Webcam error:', error);
    }
}

/**
 * Stop the webcam and emotion detection.
 */
function stopEmotionDetection() {
    const video = document.getElementById('webcamVideo');
    const container = document.getElementById('webcamContainer');
    const placeholder = document.getElementById('webcamPlaceholder');
    const startBtn = document.getElementById('startDetectionBtn');
    const stopBtn = document.getElementById('stopDetectionBtn');

    isDetecting = false;

    // Clear the session flag — user explicitly stopped
    sessionStorage.removeItem('emotionDetectionActive');

    // Stop the detection interval
    if (detectionInterval) {
        clearInterval(detectionInterval);
        detectionInterval = null;
    }

    // Stop the webcam stream
    if (webcamStream) {
        webcamStream.getTracks().forEach(track => track.stop());
        webcamStream = null;
    }

    video.srcObject = null;
    container.style.display = 'none';
    placeholder.style.display = '';
    startBtn.style.display = '';
    stopBtn.style.display = 'none';

    // Reset emotion display
    updateEmotionDisplay('Stopped', 0, 'neutral');
    updateRecommendation(null);
}

/**
 * Capture a frame from the webcam and send it to the server for emotion detection.
 */
async function captureAndDetect() {
    if (!isDetecting || !webcamStream) return;

    const video = document.getElementById('webcamVideo');
    const canvas = document.getElementById('webcamCanvas');

    if (!video.videoWidth || !video.videoHeight) return;

    // Set canvas size to match video
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    // Draw current video frame to canvas
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    // Convert to base64 JPEG (compressed to reduce payload size)
    const imageData = canvas.toDataURL('image/jpeg', 0.7);

    try {
        // Get lesson context from the page
        const context = window.LESSON_CONTEXT || {};

        const response = await fetch(context.apiUrl || '/api/detect_emotion', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                image: imageData,
                course_id: context.courseId || null,
                lesson_id: context.lessonId || null
            })
        });

        const result = await response.json();

        if (result.success) {
            // Update the UI
            updateEmotionDisplay(result.emotion, result.confidence, result.emotion.toLowerCase());
            updateRecommendation(result.recommendation);
            updateEngagement(result.engagement);

            // Show warning if multiple faces
            if (result.warning) {
                showWebcamWarning(result.warning);
            }

            // Show fallback notice
            if (result.is_fallback) {
                showFallbackNotice();
            }
        } else {
            // Handle detection errors (no face, etc.)
            updateEmotionDisplay(result.error || 'No face', 0, 'neutral');
            if (result.face_status === 'no_face') {
                // Don't show error alert for no face — just update display
                const badge = document.getElementById('emotionBadge');
                if (badge) badge.className = 'emotion-badge neutral';
            }
        }

    } catch (error) {
        console.error('[Emotion] API request failed:', error);
        updateEmotionDisplay('Connection error', 0, 'neutral');
    }
}

/**
 * Update the emotion display in the UI.
 */
function updateEmotionDisplay(emotion, confidence, cssClass) {
    const label = document.getElementById('emotionLabel');
    const badge = document.getElementById('emotionBadge');
    const dot = document.getElementById('emotionDot');
    const confDisplay = document.getElementById('confidenceValue');

    if (label) label.textContent = emotion;
    if (badge) badge.className = `emotion-badge ${cssClass}`;
    if (dot) dot.className = `emotion-dot ${cssClass}`;
    if (confDisplay) {
        const pct = Math.round(confidence * 100);
        confDisplay.textContent = pct > 0 ? `${pct}% confidence` : '—';
    }
}

/**
 * Update the recommendation panel.
 */
function updateRecommendation(rec) {
    const panel = document.getElementById('recommendationContent');
    if (!panel) return;

    if (!rec) {
        panel.innerHTML = `
            <div class="text-center text-muted py-2">
                <i class="bi bi-robot" style="font-size: 1.5rem; opacity: 0.3;"></i>
                <p class="small mt-2 mb-0">Start emotion detection to receive recommendations.</p>
            </div>`;
        return;
    }

    const urgencyColors = {
        'low': 'var(--primary)',
        'medium': 'var(--warning)',
        'high': 'var(--danger)'
    };

    const color = urgencyColors[rec.urgency] || 'var(--primary)';

    panel.innerHTML = `
        <div class="d-flex gap-3 align-items-start">
            <div class="rec-icon" style="background: rgba(108,99,255,0.15);">
                <i class="bi bi-${rec.icon}" style="color: ${color};"></i>
            </div>
            <div>
                <div class="small fw-semibold mb-1" style="color: ${color};">
                    ${rec.emotion} Detected
                    ${rec.urgency !== 'low' ? `<span class="badge bg-${rec.urgency === 'high' ? 'danger' : 'warning'} bg-opacity-25 ms-1" style="font-size: 0.6rem;">
                        ${rec.urgency} priority
                    </span>` : ''}
                </div>
                <div class="text-muted small">${rec.message}</div>
            </div>
        </div>`;
}

/**
 * Update engagement indicator.
 */
function updateEngagement(engagement) {
    if (!engagement) return;

    // Could update an engagement meter in the UI if one exists
    const engEl = document.getElementById('engagementLevel');
    if (engEl) {
        const colors = { 'high': 'var(--success)', 'medium': 'var(--warning)', 'low': 'var(--danger)' };
        engEl.textContent = `${engagement.level} (${engagement.score}%)`;
        engEl.style.color = colors[engagement.level] || 'var(--text-muted)';
    }
}

/**
 * Show webcam error message.
 */
function showWebcamError(msg) {
    const errorDiv = document.getElementById('webcamError');
    const errorMsg = document.getElementById('webcamErrorMsg');
    if (errorDiv && errorMsg) {
        errorMsg.textContent = msg;
        errorDiv.style.display = 'block';
    }
}

/**
 * Show warning (non-fatal).
 */
function showWebcamWarning(msg) {
    console.warn('[Emotion]', msg);
}

/**
 * Show fallback mode notice.
 */
let fallbackNoticeShown = false;
function showFallbackNotice() {
    if (fallbackNoticeShown) return;
    fallbackNoticeShown = true;

    const panel = document.getElementById('recommendationPanel');
    if (panel) {
        const notice = document.createElement('div');
        notice.className = 'mt-2 small text-muted';
        notice.style.fontSize = '0.7rem';
        notice.innerHTML = '<i class="bi bi-info-circle me-1"></i>Running in demo mode (no trained model loaded). Predictions are approximate.';
        panel.appendChild(notice);
    }
}

// Clean up on page unload — stop tracks but keep session flag
// so the camera auto-restarts on the next lesson page.
window.addEventListener('beforeunload', function () {
    if (webcamStream) {
        webcamStream.getTracks().forEach(track => track.stop());
    }
});

// ── Auto-restart camera if it was active before page navigation ──
document.addEventListener('DOMContentLoaded', function () {
    // Only auto-start if the start button exists (i.e. we're on a lesson page)
    const startBtn = document.getElementById('startDetectionBtn');
    if (startBtn && sessionStorage.getItem('emotionDetectionActive') === 'true') {
        // Small delay to let the video element initialise
        setTimeout(startEmotionDetection, 600);
    }
});
