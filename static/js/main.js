/**
 * Smart Online Learning System — Main JavaScript
 * General UI utilities, auto-dismiss alerts, and common interactions.
 */

document.addEventListener('DOMContentLoaded', function () {

    // ── Auto-dismiss flash alerts after 5 seconds ──
    const alerts = document.querySelectorAll('.glass-alert');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) bsAlert.close();
        }, 5000);
    });

    // ── Staggered fade-in for dashboard cards ──
    const cards = document.querySelectorAll('.fade-in-card');
    cards.forEach(function (card, index) {
        card.style.opacity = '0';
        card.style.transform = 'translateY(15px)';
        setTimeout(function () {
            card.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, 80 * index);
    });

    // ── Confirm before destructive actions ──
    document.querySelectorAll('[data-confirm]').forEach(function (el) {
        el.addEventListener('click', function (e) {
            if (!confirm(this.dataset.confirm)) {
                e.preventDefault();
            }
        });
    });

    // ── Tooltip initialisation (Bootstrap) ──
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltipTriggerList.forEach(function (el) {
        new bootstrap.Tooltip(el);
    });

    // ── Active nav link highlighting ──
    const currentPath = window.location.pathname;
    document.querySelectorAll('#main-navbar .nav-link').forEach(function (link) {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        }
    });

});
