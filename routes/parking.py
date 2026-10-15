"""
Parking and Occupancy Blueprint
Handles: parking slot management (add/edit/delete/list),
         real-time occupancy monitoring, vehicle check-in/check-out,
         active sessions, and the live occupancy JSON API.

These two topics are combined because they both work with the same
physical parking slots — it makes sense to read them together.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from routes.auth import login_required
from services.parking_service import (
    list_slots, get_slot_by_id, create_slot, update_slot, delete_slot, list_areas
)
from services.occupancy_service import (
    get_occupancy_overview, check_in_vehicle, check_out_vehicle,
    get_active_sessions, get_occupancy_logs
)
from services.reservation_service import list_reservations

parking_bp = Blueprint('parking', __name__)


# ═══════════════════════════════════════════════════════════════
#  PARKING SLOT MANAGEMENT
#  (Formerly routes/parking.py)
# ═══════════════════════════════════════════════════════════════

@parking_bp.route('/parking-slots')
@login_required
def slots_list():
    """Main parking spaces management page with filters and status badges."""
    search    = request.args.get('search', '').strip()
    area_id   = request.args.get('area_id', '')
    slot_type = request.args.get('slot_type', '')
    status    = request.args.get('status', '')

    slots = list_slots(search=search, area_id=area_id, slot_type=slot_type, status=status)
    areas = list_areas()

    return render_template(
        'parking_slots.html',
        slots=slots,
        areas=areas,
        search=search,
        selected_area=area_id,
        selected_type=slot_type,
        selected_status=status,
        counts={
            'total':     len(slots),
            'available': sum(1 for s in slots if s['status'] == 'available'),
            'reserved':  sum(1 for s in slots if s['status'] == 'reserved'),
            'occupied':  sum(1 for s in slots if s['status'] == 'occupied'),
        }
    )


@parking_bp.route('/parking-slots/add', methods=['POST'])
@login_required
def add_slot():
    """Create a new parking slot."""
    slot_number = request.form.get('slot_number', '').strip()
    area_id     = request.form.get('area_id')
    slot_type   = request.form.get('slot_type', 'regular')
    hourly_rate = request.form.get('hourly_rate', 5.00)
    status      = request.form.get('status', 'available')

    if not slot_number or not area_id:
        flash('Slot number and parking area are required.', 'danger')
        return redirect(url_for('parking.slots_list'))

    result = create_slot(slot_number, area_id, slot_type, hourly_rate, status)
    flash(result['message'] if result['success'] else result['error'],
          'success' if result['success'] else 'danger')
    return redirect(url_for('parking.slots_list'))


@parking_bp.route('/parking-slots/<int:slot_id>/edit', methods=['POST'])
@login_required
def edit_slot(slot_id):
    """Update details of an existing parking slot."""
    result = update_slot(
        slot_id,
        request.form.get('slot_number', '').strip(),
        request.form.get('area_id'),
        request.form.get('slot_type'),
        request.form.get('hourly_rate'),
        request.form.get('status')
    )
    flash(result['message'] if result['success'] else result['error'],
          'success' if result['success'] else 'danger')
    return redirect(url_for('parking.slots_list'))


@parking_bp.route('/parking-slots/<int:slot_id>/delete', methods=['POST'])
@login_required
def remove_slot(slot_id):
    """Delete a parking slot (only allowed when not occupied or reserved)."""
    result = delete_slot(slot_id)
    flash(result['message'] if result['success'] else result['error'],
          'success' if result['success'] else 'danger')
    return redirect(url_for('parking.slots_list'))


@parking_bp.route('/api/parking-slots/<int:slot_id>')
@login_required
def get_slot_json(slot_id):
    """JSON API: fetch slot details for the edit modal."""
    slot = get_slot_by_id(slot_id)
    if not slot:
        return jsonify({'success': False, 'error': 'Slot not found'}), 404
    return jsonify({'success': True, 'slot': dict(slot)})


# ═══════════════════════════════════════════════════════════════
#  OCCUPANCY MONITORING
#  (Formerly routes/occupancy.py)
# ═══════════════════════════════════════════════════════════════

@parking_bp.route('/occupancy')
@login_required
def occupancy_index():
    """Real-time occupancy dashboard, visual slot map, and active sessions."""
    search      = request.args.get('search', '').strip()
    area_filter = request.args.get('area_id', '')

    return render_template(
        'occupancy.html',
        overview=get_occupancy_overview(),
        slots=list_slots(search=search, area_id=area_filter),
        areas=list_areas(),
        active_sessions=get_active_sessions(),
        recent_logs=get_occupancy_logs(limit=15),
        checkin_ready=list_reservations(status='reserved', limit=20),
        search=search,
        selected_area=area_filter
    )


@parking_bp.route('/occupancy/check-in', methods=['POST'])
@login_required
def check_in():
    """Handle vehicle check-in."""
    reservation_id = request.form.get('reservation_id')
    if not reservation_id:
        flash('Please select a reservation to check in.', 'danger')
        return redirect(url_for('parking.occupancy_index'))

    result = check_in_vehicle(reservation_id)
    flash(result['message'] if result['success'] else result['error'],
          'success' if result['success'] else 'danger')
    return redirect(request.referrer or url_for('parking.occupancy_index'))


@parking_bp.route('/occupancy/check-out', methods=['POST'])
@login_required
def check_out():
    """Handle vehicle check-out."""
    reservation_id = request.form.get('reservation_id')
    if not reservation_id:
        flash('Please specify a reservation to check out.', 'danger')
        return redirect(url_for('parking.occupancy_index'))

    result = check_out_vehicle(reservation_id)
    if result['success']:
        flash(
            f"{result['message']} Total Bill: ${result['final_amount']:.2f} ({result['actual_hours']} hrs)",
            'success'
        )
    else:
        flash(result['error'], 'danger')
    return redirect(request.referrer or url_for('parking.occupancy_index'))


@parking_bp.route('/api/occupancy/live')
@login_required
def occupancy_live_api():
    """Live JSON occupancy data for real-time polling."""
    return jsonify({
        'overview': get_occupancy_overview(),
        'slots':    [dict(s) for s in list_slots()]
    })
