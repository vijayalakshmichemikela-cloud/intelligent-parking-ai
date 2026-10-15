/**
 * Dashboard Analytics and Real-Time Telemetry Script
 * Renders Chart.js charts and handles live asynchronous data refresh.
 */

let occupancyChart = null;
let trendsChart = null;
let revenueChart = null;

document.addEventListener('DOMContentLoaded', function () {
    initCharts();
    
    // Bind refresh button if present
    const refreshBtn = document.getElementById('btn-refresh-stats');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function () {
            refreshDashboardData(true);
        });
    }

    // Auto-refresh metrics every 30 seconds
    setInterval(function () {
        refreshDashboardData(false);
    }, 30000);
});

/**
 * Fetch chart datasets and initialize Chart.js instances
 */
function initCharts() {
    fetch('/api/dashboard/charts')
        .then(response => response.json())
        .then(data => {
            renderOccupancyDoughnut(data.doughnut);
            renderTrendsChart(data.trends);
            renderRevenueChart(data.trends);
        })
        .catch(err => {
            console.error('Failed to load chart metrics:', err);
        });
}

function renderOccupancyDoughnut(doughnutData) {
    const ctx = document.getElementById('occupancyDoughnutChart');
    if (!ctx) return;

    if (occupancyChart) occupancyChart.destroy();

    occupancyChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: doughnutData.labels,
            datasets: [{
                data: doughnutData.data,
                backgroundColor: doughnutData.colors,
                borderWidth: 2,
                borderColor: '#ffffff',
                hoverOffset: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        boxWidth: 12,
                        padding: 15,
                        font: { family: 'Inter', size: 12 }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            const val = context.parsed;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const pct = total > 0 ? ((val / total) * 100).toFixed(1) : 0;
                            return ` ${context.label}: ${val} slots (${pct}%)`;
                        }
                    }
                }
            },
            cutout: '70%'
        }
    });
}

function renderTrendsChart(trendsData) {
    const ctx = document.getElementById('reservationsTrendChart');
    if (!ctx) return;

    if (trendsChart) trendsChart.destroy();

    trendsChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: trendsData.labels,
            datasets: [{
                label: 'Bookings',
                data: trendsData.reservations,
                borderColor: '#2563eb',
                backgroundColor: 'rgba(37, 99, 235, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.35,
                pointBackgroundColor: '#2563eb',
                pointRadius: 4,
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { precision: 0, font: { family: 'Inter', size: 11 } },
                    grid: { color: '#f1f5f9' }
                },
                x: {
                    ticks: { font: { family: 'Inter', size: 11 } },
                    grid: { display: false }
                }
            }
        }
    });
}

function renderRevenueChart(trendsData) {
    const ctx = document.getElementById('revenueTrendChart');
    if (!ctx) return;

    if (revenueChart) revenueChart.destroy();

    revenueChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: trendsData.labels,
            datasets: [{
                label: 'Revenue ($)',
                data: trendsData.revenue,
                backgroundColor: '#10b981',
                borderRadius: 6,
                maxBarThickness: 32
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function (ctx) {
                            return ` Revenue: $${ctx.parsed.y.toFixed(2)}`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: val => `$${val}`,
                        font: { family: 'Inter', size: 11 }
                    },
                    grid: { color: '#f1f5f9' }
                },
                x: {
                    ticks: { font: { family: 'Inter', size: 11 } },
                    grid: { display: false }
                }
            }
        }
    });
}

/**
 * Fetch latest stats from backend and update dashboard cards smoothly
 */
function refreshDashboardData(showToast = false) {
    const refreshBtn = document.getElementById('btn-refresh-stats');
    if (refreshBtn) refreshBtn.classList.add('disabled');

    fetch('/api/dashboard/stats')
        .then(response => response.json())
        .then(stats => {
            // Update stat values in DOM
            updateText('val-total-spaces', stats.total_spaces);
            updateText('val-available-spaces', stats.available_spaces);
            updateText('val-reserved-spaces', stats.reserved_spaces);
            updateText('val-occupied-spaces', stats.occupied_spaces);
            updateText('val-occupancy-pct', `${stats.occupancy_percentage}%`);
            updateText('val-total-reservations', stats.total_reservations);
            updateText('val-total-revenue', `$${Number(stats.total_revenue).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);
            updateText('val-pending-amount', `$${Number(stats.pending_amount).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);

            // Re-fetch charts
            initCharts();

            if (showToast && window.bootstrap) {
                const toastEl = document.getElementById('liveToast');
                if (toastEl) {
                    const toast = new bootstrap.Toast(toastEl);
                    document.getElementById('toast-message').innerText = 'Dashboard metrics synchronized with database.';
                    toast.show();
                }
            }
        })
        .catch(err => {
            console.error('Failed to refresh stats:', err);
        })
        .finally(() => {
            if (refreshBtn) refreshBtn.classList.remove('disabled');
        });
}

function updateText(elementId, newText) {
    const el = document.getElementById(elementId);
    if (el) el.innerText = newText;
}
