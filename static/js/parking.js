/**
 * Parking and Reservation Form Interactive Scripts
 * Handles dynamic fee calculations, available slot filtering, and modal prep.
 */

document.addEventListener('DOMContentLoaded', function () {
    initReservationFeeEstimator();
    initSlotEditModals();
});

/**
 * Live Fee Calculation & Slot Availability Filter for Reservation Form
 */
function initReservationFeeEstimator() {
    const slotSelect = document.getElementById('slot_id');
    const startTimeInput = document.getElementById('start_time');
    const endTimeInput = document.getElementById('end_time');
    const btnCheckAvail = document.getElementById('btn-check-available');

    if (!slotSelect || !startTimeInput || !endTimeInput) return;

    function triggerEstimate() {
        const slotId = slotSelect.value;
        const startTime = startTimeInput.value;
        const endTime = endTimeInput.value;

        if (!slotId || !startTime || !endTime) return;

        // Ensure end > start before requesting
        if (new Date(endTime) <= new Date(startTime)) {
            const errEl = document.getElementById('estimate-error');
            if (errEl) errEl.innerText = 'End time must be after start time.';
            return;
        }

        const errEl = document.getElementById('estimate-error');
        if (errEl) errEl.innerText = '';

        fetch('/api/reservations/estimate-fee', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                slot_id: slotId,
                start_time: startTime,
                end_time: endTime
            })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                const durEl = document.getElementById('est-duration');
                const rateEl = document.getElementById('est-rate');
                const totalEl = document.getElementById('est-total');

                if (durEl) durEl.innerText = `${data.duration_hours} hrs`;
                if (rateEl) rateEl.innerText = `$${Number(data.hourly_rate).toFixed(2)}/hr`;
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

    // Initial trigger if values present
    if (slotSelect.value && startTimeInput.value && endTimeInput.value) {
        triggerEstimate();
    }

    // Filter available slots button
    if (btnCheckAvail) {
        btnCheckAvail.addEventListener('click', function () {
            const startTime = startTimeInput.value;
            const endTime = endTimeInput.value;

            if (!startTime || !endTime) {
                alert('Please pick both start and end times first.');
                return;
            }

            btnCheckAvail.disabled = true;
            btnCheckAvail.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Checking...';

            fetch(`/api/reservations/available-slots?start_time=${encodeURIComponent(startTime)}&end_time=${encodeURIComponent(endTime)}`)
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        const currentVal = slotSelect.value;
                        slotSelect.innerHTML = '<option value="">-- Choose an Available Slot --</option>';
                        
                        data.slots.forEach(s => {
                            const opt = document.createElement('option');
                            opt.value = s.id;
                            opt.text = `${s.slot_number} (${s.area_name} - ${s.slot_type.toUpperCase()} @ $${Number(s.hourly_rate).toFixed(2)}/hr)`;
                            if (s.id == currentVal) opt.selected = true;
                            slotSelect.appendChild(opt);
                        });

                        const msgEl = document.getElementById('avail-slots-count');
                        if (msgEl) {
                            msgEl.innerText = `${data.slots.length} slots available for this period.`;
                            msgEl.className = 'text-success small mt-1';
                        }
                    } else {
                        alert(data.error || 'Failed to check availability.');
                    }
                })
                .catch(err => console.error('Availability check failed:', err))
                .finally(() => {
                    btnCheckAvail.disabled = false;
                    btnCheckAvail.innerHTML = '<i class="bi bi-funnel me-1"></i> Filter Available Slots';
                });
        });
    }
}

/**
 * Setup Edit Modal population on Parking Slots management page
 */
function initSlotEditModals() {
    const editModal = document.getElementById('editSlotModal');
    if (!editModal) return;

    editModal.addEventListener('show.bs.modal', function (event) {
        const button = event.relatedTarget;
        if (!button) return;

        const slotId = button.getAttribute('data-slot-id');
        const form = document.getElementById('editSlotForm');
        form.action = `/parking-slots/${slotId}/edit`;

        // Fetch current details
        fetch(`/api/parking-slots/${slotId}`)
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    const s = data.slot;
                    document.getElementById('edit_slot_number').value = s.slot_number;
                    document.getElementById('edit_area_id').value = s.area_id;
                    document.getElementById('edit_slot_type').value = s.slot_type;
                    document.getElementById('edit_hourly_rate').value = s.hourly_rate;
                    document.getElementById('edit_status').value = s.status;
                }
            })
            .catch(err => console.error('Error fetching slot details:', err));
    });
}
