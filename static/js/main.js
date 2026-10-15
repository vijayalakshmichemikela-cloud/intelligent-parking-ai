/**
 * Smart Parking Management System — main.js
 *
 * This single file contains all client-side JavaScript for the application:
 *   1. Dashboard Analytics  — Chart.js charts and live metric refresh
 *   2. Reservation Form     — Live fee estimation and slot availability filter
 *   3. Parking Slot Modals  — Populate the edit-slot modal via API
 */


// ═══════════════════════════════════════════════════════════════
//  SECTION 1: DASHBOARD ANALYTICS
//  Renders Chart.js charts and auto-refreshes stats every 30 s.
// ═══════════════════════════════════════════════════════════════

let occupancyChart = null;
let trendsChart    = null;
let revenueChart   = null;

document.addEventListener('DOMContentLoaded', function () {
    // --- Dashboard charts -------------------------------------------------
    initCharts();

    const refreshBtn = document.getElementById('btn-refresh-stats');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function () {
            refreshDashboardData(true);
        });
    }

    // Auto-refresh dashboard metrics every 30 seconds
    setInterval(function () {
        refreshDashboardData(false);
    }, 30000);

    // --- Reservation form -------------------------------------------------
    initReservationFeeEstimator();

    // --- Parking slot edit modal ------------------------------------------
    initSlotEditModals();
});

/** Fetch chart data from the backend and render all three Chart.js charts. */
function initCharts() {
    fetch('/api/dashboard/charts')
        .then(response => response.json())
        .then(data => {
            renderOccupancyDoughnut(data.doughnut);
            renderTrendsChart(data.trends);
            renderRevenueChart(data.trends);
        })
        .catch(err => console.error('Failed to load chart metrics:', err));
}

function renderOccupancyDoughnut(doughnutData) {
    const ctx = document.getElementById('occupancyDoughnutChart');
    if (!ctx) return;

    if (occupancyChart) occupancyChart.destroy();

    occupancyChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels:   doughnutData.labels,
            datasets: [{
                data:            doughnutData.data,
                backgroundColor: doughnutData.colors,
                borderWidth:     2,
                borderColor:     '#ffffff',
                hoverOffset:     4
            }]
        },
        options: {
            responsive:          true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { boxWidth: 12, padding: 15, font: { family: 'Inter', size: 12 } }
                },
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            const val   = context.parsed;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const pct   = total > 0 ? ((val / total) * 100).toFixed(1) : 0;
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
            labels:   trendsData.labels,
            datasets: [{
                label:           'Bookings',
                data:            trendsData.reservations,
                borderColor:     '#2563eb',
                backgroundColor: 'rgba(37, 99, 235, 0.1)',
                borderWidth:     2,
                fill:            true,
                tension:         0.35,
                pointBackgroundColor: '#2563eb',
                pointRadius:     4,
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { beginAtZero: true, ticks: { precision: 0, font: { family: 'Inter', size: 11 } }, grid: { color: '#f1f5f9' } },
                x: { ticks: { font: { family: 'Inter', size: 11 } }, grid: { display: false } }
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
            labels:   trendsData.labels,
            datasets: [{
                label:           'Revenue ($)',
                data:            trendsData.revenue,
                backgroundColor: '#10b981',
                borderRadius:    6,
                maxBarThickness: 32
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: { label: ctx => ` Revenue: $${ctx.parsed.y.toFixed(2)}` }
                }
            },
            scales: {
                y: { beginAtZero: true, ticks: { callback: val => `$${val}`, font: { family: 'Inter', size: 11 } }, grid: { color: '#f1f5f9' } },
                x: { ticks: { font: { family: 'Inter', size: 11 } }, grid: { display: false } }
            }
        }
    });
}

/** Pull latest stats from the backend and update the dashboard cards. */
function refreshDashboardData(showToast = false) {
    const refreshBtn = document.getElementById('btn-refresh-stats');
    if (refreshBtn) refreshBtn.classList.add('disabled');

    fetch('/api/dashboard/stats')
        .then(response => response.json())
        .then(stats => {
            updateText('val-total-spaces',      stats.total_spaces);
            updateText('val-available-spaces',  stats.available_spaces);
            updateText('val-reserved-spaces',   stats.reserved_spaces);
            updateText('val-occupied-spaces',   stats.occupied_spaces);
            updateText('val-occupancy-pct',     `${stats.occupancy_percentage}%`);
            updateText('val-total-reservations', stats.total_reservations);
            updateText('val-total-revenue',
                `$${Number(stats.total_revenue).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);
            updateText('val-pending-amount',
                `$${Number(stats.pending_amount).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);

            initCharts();  // Redraw charts with fresh data

            if (showToast && window.bootstrap) {
                const toastEl = document.getElementById('liveToast');
                if (toastEl) {
                    document.getElementById('toast-message').innerText =
                        'Dashboard metrics synchronized with database.';
                    new bootstrap.Toast(toastEl).show();
                }
            }
        })
        .catch(err => console.error('Failed to refresh stats:', err))
        .finally(() => {
            if (refreshBtn) refreshBtn.classList.remove('disabled');
        });
}

/** Helper: set the text content of an element by ID. */
function updateText(elementId, newText) {
    const el = document.getElementById(elementId);
    if (el) el.innerText = newText;
}


// ═══════════════════════════════════════════════════════════════
//  SECTION 2: RESERVATION FORM — LIVE FEE ESTIMATOR
//  Calculates the parking fee in real-time as the user fills in
//  the slot, start time, and end time fields.
// ═══════════════════════════════════════════════════════════════

function initReservationFeeEstimator() {
    const slotSelect    = document.getElementById('slot_id');
    const startTimeInput = document.getElementById('start_time');
    const endTimeInput   = document.getElementById('end_time');
    const btnCheckAvail  = document.getElementById('btn-check-available');

    // Only run on pages that have these form elements
    if (!slotSelect || !startTimeInput || !endTimeInput) return;

    function triggerEstimate() {
        const slotId    = slotSelect.value;
        const startTime = startTimeInput.value;
        const endTime   = endTimeInput.value;

        if (!slotId || !startTime || !endTime) return;

        const errEl = document.getElementById('estimate-error');

        if (new Date(endTime) <= new Date(startTime)) {
            if (errEl) errEl.innerText = 'End time must be after start time.';
            return;
        }
        if (errEl) errEl.innerText = '';

        fetch('/api/reservations/estimate-fee', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ slot_id: slotId, start_time: startTime, end_time: endTime })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                const durEl   = document.getElementById('est-duration');
                const rateEl  = document.getElementById('est-rate');
                const totalEl = document.getElementById('est-total');
                if (durEl)   durEl.innerText   = `${data.duration_hours} hrs`;
                if (rateEl)  rateEl.innerText  = `$${Number(data.hourly_rate).toFixed(2)}/hr`;
                if (totalEl) totalEl.innerText = `$${Number(data.estimated_amount).toFixed(2)}`;
            } else {
                if (errEl) errEl.innerText = data.error || 'Calculation failed';
            }
        })
        .catch(err => console.error('Error estimating fee:', err));
    }

    slotSelect.addEventListener('change', triggerEstimate);
    startTimeInput.addEventListener('change', triggerEstimate);
    endTimeInput.addEventListener('change', triggerEstimate);

    // Trigger immediately if the form is pre-filled (e.g., back-navigation)
    if (slotSelect.value && startTimeInput.value && endTimeInput.value) {
        triggerEstimate();
    }

    // "Filter Available Slots" button: rebuilds the slot dropdown to show
    // only slots that are free for the selected time window.
    if (btnCheckAvail) {
        btnCheckAvail.addEventListener('click', function () {
            const startTime = startTimeInput.value;
            const endTime   = endTimeInput.value;

            if (!startTime || !endTime) {
                alert('Please pick both start and end times first.');
                return;
            }

            btnCheckAvail.disabled   = true;
            btnCheckAvail.innerHTML  = '<span class="spinner-border spinner-border-sm me-1"></span> Checking...';

            fetch(`/api/reservations/available-slots?start_time=${encodeURIComponent(startTime)}&end_time=${encodeURIComponent(endTime)}`)
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        const currentVal = slotSelect.value;
                        slotSelect.innerHTML = '<option value="">-- Choose an Available Slot --</option>';

                        data.slots.forEach(s => {
                            const opt = document.createElement('option');
                            opt.value = s.id;
                            opt.text  = `${s.slot_number} (${s.area_name} — ${s.slot_type.toUpperCase()} @ $${Number(s.hourly_rate).toFixed(2)}/hr)`;
                            if (s.id == currentVal) opt.selected = true;
                            slotSelect.appendChild(opt);
                        });

                        const msgEl = document.getElementById('avail-slots-count');
                        if (msgEl) {
                            msgEl.innerText   = `${data.slots.length} slots available for this period.`;
                            msgEl.className = 'text-success small mt-1';
                        }
                    } else {
                        alert(data.error || 'Failed to check availability.');
                    }
                })
                .catch(err => console.error('Availability check failed:', err))
                .finally(() => {
                    btnCheckAvail.disabled  = false;
                    btnCheckAvail.innerHTML = '<i class="bi bi-funnel me-1"></i> Filter Available Slots';
                });
        });
    }
}


// ═══════════════════════════════════════════════════════════════
//  SECTION 3: PARKING SLOT EDIT MODAL
//  Loads current slot data via the API whenever the edit modal
//  is opened, so the form is always pre-filled correctly.
// ═══════════════════════════════════════════════════════════════

function initSlotEditModals() {
    const editModal = document.getElementById('editSlotModal');
    if (!editModal) return;

    editModal.addEventListener('show.bs.modal', function (event) {
        const button = event.relatedTarget;
        if (!button) return;

        const slotId = button.getAttribute('data-slot-id');
        const form   = document.getElementById('editSlotForm');
        form.action  = `/parking-slots/${slotId}/edit`;

        fetch(`/api/parking-slots/${slotId}`)
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    const s = data.slot;
                    document.getElementById('edit_slot_number').value = s.slot_number;
                    document.getElementById('edit_area_id').value     = s.area_id;
                    document.getElementById('edit_slot_type').value   = s.slot_type;
                    document.getElementById('edit_hourly_rate').value = s.hourly_rate;
                    document.getElementById('edit_status').value      = s.status;
                }
            })
            .catch(err => console.error('Error fetching slot details:', err));
    });
}
