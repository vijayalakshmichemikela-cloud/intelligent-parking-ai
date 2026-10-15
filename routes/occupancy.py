"""
Occupancy Blueprint
Handles real-time facility occupancy monitoring, visual slot maps,
vehicle check-in, check-out, and active parking sessions.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from routes.auth import login_required
from services.occupancy_service import (
    get_occupancy_overview, check_in_vehicle, check_out_vehicle,
    get_active_sessions, get_occupancy_logs
)
from services.parking_service import list_slots, list_areas
from services.reservation_service import list_reservations

occupancy_bp = Blueprint('occupancy', __name__)

@occupancy_bp.route('/occupancy')
@login_required
def index():
    """Real-time occupancy monitoring dashboard and visual parking map."""
    search = request.args.get('search', '').strip()
    area_filter = request.args.get('area_id', '')

    overview = get_occupancy_overview()
    all_slots = list_slots(search=search, area_id=area_filter)
    areas = list_areas()
    active_sessions = get_active_sessions()
    recent_logs = get_occupancy_logs(limit=15)

    # Pending / reserved reservations ready for check-in
    checkin_ready = list_reservations(status='reserved', limit=20)

    return render_template(
        'occupancy.html',
        overview=overview,
        slots=all_slots,
        areas=areas,
        active_sessions=active_sessions,
        recent_logs=recent_logs,
        checkin_ready=checkin_ready,
        search=search,
        selected_area=area_filter
    )


@occupancy_bp.route('/occupancy/check-in', methods=['POST'])
@login_required
def check_in():
    """Handle vehicle check-in action."""
    reservation_id = request.form.get('reservation_id')
    if not reservation_id:
        flash('Please select or specify a reservation to check in.', 'danger')
        return redirect(url_for('occupancy.index'))

    result = check_in_vehicle(reservation_id)
    if result['success']:
        flash(result['message'], 'success')
    else:
        flash(result['error'], 'danger')

    return redirect(request.referrer or url_for('occupancy.index'))


@occupancy_bp.route('/occupancy/check-out', methods=['POST'])
@login_required
def check_out():
    """Handle vehicle check-out action."""
    reservation_id = request.form.get('reservation_id')
    if not reservation_id:
        flash('Please specify a valid reservation to check out.', 'danger')
        return redirect(url_for('occupancy.index'))

    result = check_out_vehicle(reservation_id)
    if result['success']:
        flash(f"{result['message']} Total Bill: ${result['final_amount']:.2f} ({result['actual_hours']} hrs)", 'success')
    else:
        flash(result['error'], 'danger')

    return redirect(request.referrer or url_for('occupancy.index'))


@occupancy_bp.route('/api/occupancy/live')
@login_required
def live_api():
    """Live occupancy JSON data for real-time polling."""
    overview = get_occupancy_overview()
    slots = list_slots()
    return jsonify({
        'overview': overview,
        'slots': [dict(s) for s in slots]
    })
