/**
 * Smart Online Learning System — Chart.js Analytics
 * ==================================================
 * Reusable chart creation functions for emotion distribution,
 * quiz performance, and engagement trends.
 */

// Emotion color palette matching CSS variables
const EMOTION_COLORS = {
    'Happy':    '#22C55E',
    'Sad':      '#3B82F6',
    'Neutral':  '#94A3B8',
    'Confused': '#F59E0B',
    'Bored':    '#EF4444',
    'Focused':  '#6C63FF'
};

const EMOTION_BG_COLORS = {
    'Happy':    'rgba(34, 197, 94, 0.2)',
    'Sad':      'rgba(59, 130, 246, 0.2)',
    'Neutral':  'rgba(148, 163, 184, 0.2)',
    'Confused': 'rgba(245, 158, 11, 0.2)',
    'Bored':    'rgba(239, 68, 68, 0.2)',
    'Focused':  'rgba(108, 99, 255, 0.2)'
};

/**
 * Create an emotion distribution pie/doughnut chart.
 */
function createEmotionPieChart(canvasId, labels, data) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    const colors = labels.map(l => EMOTION_COLORS[l] || '#94A3B8');
    const bgColors = labels.map(l => EMOTION_BG_COLORS[l] || 'rgba(148,163,184,0.2)');

    return new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: colors,
                borderColor: 'rgba(15, 14, 23, 0.8)',
                borderWidth: 2,
                hoverBorderColor: '#fff',
                hoverBorderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            cutout: '60%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#94A3B8',
                        font: { family: 'Inter', size: 11 },
                        padding: 12,
                        usePointStyle: true,
                        pointStyleWidth: 10
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(22, 33, 62, 0.9)',
                    titleColor: '#E2E8F0',
                    bodyColor: '#94A3B8',
                    borderColor: 'rgba(108, 99, 255, 0.3)',
                    borderWidth: 1,
                    cornerRadius: 8,
                    padding: 10,
                    callbacks: {
                        label: function(context) {
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const pct = ((context.parsed / total) * 100).toFixed(1);
                            return ` ${context.label}: ${context.parsed} (${pct}%)`;
                        }
                    }
                }
            }
        }
    });
}

/**
 * Create a quiz score bar chart.
 */
function createQuizBarChart(canvasId, labels, scores, totals) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    const percentages = scores.map((s, i) => totals[i] > 0 ? Math.round(s / totals[i] * 100) : 0);
    const barColors = percentages.map(p => {
        if (p >= 70) return '#22C55E';
        if (p >= 40) return '#F59E0B';
        return '#EF4444';
    });

    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Score (%)',
                data: percentages,
                backgroundColor: barColors.map(c => c + '40'),
                borderColor: barColors,
                borderWidth: 1,
                borderRadius: 6,
                borderSkipped: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    grid: { color: 'rgba(148, 163, 184, 0.08)' },
                    ticks: { color: '#94A3B8', font: { family: 'Inter', size: 11 } }
                },
                x: {
                    grid: { display: false },
                    ticks: {
                        color: '#94A3B8',
                        font: { family: 'Inter', size: 10 },
                        maxRotation: 45
                    }
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(22, 33, 62, 0.9)',
                    titleColor: '#E2E8F0',
                    bodyColor: '#94A3B8',
                    borderColor: 'rgba(108, 99, 255, 0.3)',
                    borderWidth: 1,
                    cornerRadius: 8,
                    callbacks: {
                        label: function(context) {
                            const idx = context.dataIndex;
                            return ` Score: ${scores[idx]}/${totals[idx]} (${context.parsed.y}%)`;
                        }
                    }
                }
            }
        }
    });
}

/**
 * Create an emotion timeline line chart.
 */
function createEmotionTimelineChart(canvasId, timestamps, emotions) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    // Map emotions to numeric values for the chart
    const emotionValues = {
        'Focused': 5, 'Happy': 4, 'Neutral': 3, 'Confused': 2, 'Sad': 1, 'Bored': 0
    };

    const values = emotions.map(e => emotionValues[e] !== undefined ? emotionValues[e] : 3);
    const pointColors = emotions.map(e => EMOTION_COLORS[e] || '#94A3B8');

    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: timestamps,
            datasets: [{
                label: 'Emotion Level',
                data: values,
                borderColor: '#6C63FF',
                backgroundColor: 'rgba(108, 99, 255, 0.1)',
                pointBackgroundColor: pointColors,
                pointBorderColor: pointColors,
                pointRadius: 5,
                pointHoverRadius: 7,
                tension: 0.3,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: {
                y: {
                    min: -0.5,
                    max: 5.5,
                    grid: { color: 'rgba(148, 163, 184, 0.08)' },
                    ticks: {
                        color: '#94A3B8',
                        font: { family: 'Inter', size: 10 },
                        stepSize: 1,
                        callback: function(value) {
                            const labels = ['Bored', 'Sad', 'Confused', 'Neutral', 'Happy', 'Focused'];
                            return labels[value] || '';
                        }
                    }
                },
                x: {
                    grid: { display: false },
                    ticks: {
                        color: '#94A3B8',
                        font: { family: 'Inter', size: 9 },
                        maxRotation: 45,
                        maxTicksLimit: 10
                    }
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(22, 33, 62, 0.9)',
                    titleColor: '#E2E8F0',
                    bodyColor: '#94A3B8',
                    borderColor: 'rgba(108, 99, 255, 0.3)',
                    borderWidth: 1,
                    cornerRadius: 8,
                    callbacks: {
                        label: function(context) {
                            return ` Emotion: ${emotions[context.dataIndex]}`;
                        }
                    }
                }
            }
        }
    });
}
