"""
Reservations and Payments Blueprint
Handles: booking reservations, fee estimation, slot availability lookup,
         reservation cancellation, CSV export, simulated payment processing,
         payment receipts, and revenue reports.

Payment logic lives here because every payment is directly tied to a
reservation — they naturally belong together.
"""

import io
import csv
import uuid
import datetime
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, jsonify, Response)
from routes.auth import login_required
from services.reservation_service import (
    create_reservation, cancel_reservation, get_reservation_details,
    list_reservations, find_available_slots, calculate_fee
)
from services.parking_service import list_areas, list_slots
from database import query_db

reservations_bp = Blueprint('reservations', __name__)


# ═══════════════════════════════════════════════════════════════
#  PAYMENT SERVICE FUNCTIONS
#  (Formerly in services/payment_service.py)
# ═══════════════════════════════════════════════════════════════

def get_payment_by_id(payment_id):
    """Return full payment details including reservation, customer, and slot."""
    sql = """
        SELECT p.*,
               r.reservation_code, r.start_time, r.end_time, r.duration_hours, r.hourly_rate,
               r.status AS reservation_status,
               c.name  AS customer_name, c.email AS customer_email, c.phone AS customer_phone,
               v.plate_number, v.vehicle_type, v.vehicle_model,
               s.slot_number, s.slot_type, a.area_name, a.floor_level
        FROM payments p
        JOIN reservations  r ON p.reservation_id = r.id
        JOIN customers     c ON r.customer_id    = c.id
        JOIN vehicles      v ON r.vehicle_id     = v.id
        JOIN parking_slots s ON r.slot_id        = s.id
        JOIN parking_areas a ON s.area_id        = a.id
        WHERE p.id = %s
    """
    return query_db(sql, (payment_id,), fetch_one=True)


def list_payments(search=None, status=None, date_from=None, date_to=None, limit=100):
    """List payment transactions with search, status filter, and date range filter."""
    sql = """
        SELECT p.*, r.reservation_code, c.name AS customer_name,
               v.plate_number, s.slot_number
        FROM payments p
        JOIN reservations  r ON p.reservation_id = r.id
        JOIN customers     c ON r.customer_id    = c.id
        JOIN vehicles      v ON r.vehicle_id     = v.id
        JOIN parking_slots s ON r.slot_id        = s.id
        WHERE 1=1
    """
    params = []

    if status and status != 'all':
        sql += " AND p.status = %s"
        params.append(status)

    if search:
        like = f"%{search.strip()}%"
        sql += """ AND (
            p.payment_code LIKE %s OR p.transaction_ref LIKE %s OR
            r.reservation_code LIKE %s OR c.name LIKE %s OR v.plate_number LIKE %s
        )"""
        params.extend([like, like, like, like, like])

    if date_from:
        sql += " AND p.payment_date >= %s"
        params.append(f"{date_from} 00:00:00")

    if date_to:
        sql += " AND p.payment_date <= %s"
        params.append(f"{date_to} 23:59:59")

    sql += " ORDER BY p.payment_date DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"

    return query_db(sql, params, fetch_all=True)


def get_payment_summary():
    """Calculate total collected revenue and pending balances."""
    total = query_db("SELECT COALESCE(SUM(amount), 0) AS total FROM payments WHERE status = 'paid'",
                     fetch_one=True)
    pending = query_db("SELECT COALESCE(SUM(amount), 0) AS pending FROM payments WHERE status = 'pending'",
                       fetch_one=True)
    count = query_db("SELECT COUNT(*) AS count FROM payments WHERE status = 'paid'",
                     fetch_one=True)
    return {
        'total_revenue':          float(total['total']),
        'pending_amount':         float(pending['pending']),
        'paid_transactions_count': int(count['count'])
    }


def process_demo_payment(payment_id, payment_method='Credit Card (Demo)', simulate_status='paid'):
    """
    Simulate a payment gateway transaction.

    Args:
        payment_id (int): The payment record to process.
        payment_method (str): 'Credit Card (Demo)', 'UPI / QR (Demo)', or 'Cash'.
        simulate_status (str): 'paid' for approval, 'failed' for decline.

    Returns:
        dict: Success flag, transaction reference, and a status message.
    """
    payment = query_db("SELECT * FROM payments WHERE id = %s", (payment_id,), fetch_one=True)
    if not payment:
        return {'success': False, 'error': 'Payment record not found.'}

    if payment['status'] == 'paid':
        return {'success': False, 'error': 'This reservation has already been paid. Duplicate payment prevented.'}

    timestamp_str = datetime.datetime.now().strftime('%Y%m%d%H%M')
    txn_ref  = f"TXN-DEMO-{timestamp_str}-{uuid.uuid4().hex[:6].upper()}"
    now_str  = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    status   = 'paid' if simulate_status == 'paid' else 'failed'
    notes    = (f"Payment successfully simulated via {payment_method} at {now_str}"
                if status == 'paid' else
                f"Simulated gateway declined via {payment_method} at {now_str}")

    query_db(
        """UPDATE payments
           SET status = %s, payment_method = %s, transaction_ref = %s,
               payment_date = %s, notes = %s
           WHERE id = %s""",
        (status, payment_method, txn_ref, now_str, notes, payment_id),
        commit=True
    )

    return {
        'success':         status == 'paid',
        'payment_id':      payment_id,
        'status':          status,
        'transaction_ref': txn_ref,
        'message':         'Demo payment approved!' if status == 'paid' else 'Demo payment declined.'
    }


# ═══════════════════════════════════════════════════════════════
#  RESERVATION ROUTES
#  (Formerly routes/reservations.py)
# ═══════════════════════════════════════════════════════════════

@reservations_bp.route('/reservations')
@login_required
def reservations_index():
    """List all reservations with search and status filters."""
    search    = request.args.get('search', '').strip()
    status    = request.args.get('status', '')
    date_from = request.args.get('date_from', '')
    date_to   = request.args.get('date_to', '')

    return render_template(
        'reservations.html',
        reservations=list_reservations(search=search, status=status,
                                       date_from=date_from, date_to=date_to),
        search=search,
        selected_status=status,
        date_from=date_from,
        date_to=date_to
    )


@reservations_bp.route('/reservations/new', methods=['GET'])
@login_required
def new_reservation():
    """Show the new reservation booking form."""
    now = datetime.datetime.now()
    return render_template(
        'reservation_form.html',
        areas=list_areas(),
        all_slots=list_slots(),
        preselected_slot_id=request.args.get('slot_id', ''),
        default_start=(now + datetime.timedelta(minutes=15)).strftime('%Y-%m-%dT%H:%M'),
        default_end=(now + datetime.timedelta(hours=2, minutes=15)).strftime('%Y-%m-%dT%H:%M')
    )


@reservations_bp.route('/reservations/create', methods=['POST'])
@login_required
def handle_create():
    """Process the reservation booking form with backend validation."""
    customer_name  = request.form.get('customer_name', '').strip()
    customer_email = request.form.get('customer_email', '').strip()
    customer_phone = request.form.get('customer_phone', '').strip()
    vehicle_plate  = request.form.get('vehicle_plate', '').strip()
    vehicle_type   = request.form.get('vehicle_type', 'Sedan')
    vehicle_model  = request.form.get('vehicle_model', '').strip()
    slot_id        = request.form.get('slot_id')
    start_time     = request.form.get('start_time')
    end_time       = request.form.get('end_time')
    notes          = request.form.get('notes', '').strip()

    if not customer_name or not vehicle_plate or not slot_id or not start_time or not end_time:
        flash('Please fill in all required fields.', 'danger')
        return redirect(url_for('reservations.new_reservation'))

    result = create_reservation(
        customer_name=customer_name, vehicle_plate=vehicle_plate,
        slot_id=slot_id, start_time=start_time, end_time=end_time,
        customer_email=customer_email, customer_phone=customer_phone,
        vehicle_type=vehicle_type, vehicle_model=vehicle_model, notes=notes
    )

    if result['success']:
        flash(f"{result['message']} Estimated fee: ${result['estimated_amount']:.2f}", 'success')
        return redirect(url_for('reservations.reservation_details', res_id=result['reservation_id']))
    else:
        flash(result['error'], 'danger')
        return redirect(url_for('reservations.new_reservation'))


@reservations_bp.route('/reservations/<int:res_id>')
@login_required
def reservation_details(res_id):
    """View the details of a single reservation."""
    res = get_reservation_details(res_id)
    if not res:
        flash('Reservation not found.', 'danger')
        return redirect(url_for('reservations.reservations_index'))
    return render_template('reservation_details.html', res=res)


@reservations_bp.route('/reservations/<int:res_id>/cancel', methods=['POST'])
@login_required
def cancel(res_id):
    """Cancel a reservation if eligible."""
    reason = request.form.get('reason', 'Cancelled by administrator')
    result = cancel_reservation(res_id, reason=reason)
    flash(result['message'] if result['success'] else result['error'],
          'success' if result['success'] else 'danger')
    return redirect(url_for('reservations.reservations_index'))


@reservations_bp.route('/api/reservations/estimate-fee', methods=['POST'])
@login_required
def estimate_fee_api():
    """JSON: live fee calculation for the booking form."""
    data       = request.get_json() or {}
    slot_id    = data.get('slot_id')
    start_time = data.get('start_time')
    end_time   = data.get('end_time')

    if not slot_id or not start_time or not end_time:
        return jsonify({'success': False, 'error': 'Missing parameters'}), 400

    try:
        fee = calculate_fee(slot_id, start_time, end_time)
        return jsonify({
            'success':          True,
            'duration_hours':   fee['duration_hours'],
            'hourly_rate':      fee['hourly_rate'],
            'estimated_amount': fee['estimated_amount']
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@reservations_bp.route('/api/reservations/available-slots')
@login_required
def available_slots_api():
    """JSON: find slots available for a given time window."""
    start_time = request.args.get('start_time')
    end_time   = request.args.get('end_time')
    area_id    = request.args.get('area_id')
    slot_type  = request.args.get('slot_type')

    if not start_time or not end_time:
        return jsonify({'success': False, 'error': 'start_time and end_time required'}), 400

    try:
        slots = find_available_slots(start_time, end_time, area_id=area_id, slot_type=slot_type)
        return jsonify({'success': True, 'slots': slots})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@reservations_bp.route('/reservations/export/csv')
@login_required
def export_reservations_csv():
    """Download reservation history as a CSV file."""
    reservations = list_reservations(limit=1000)
    output       = io.StringIO()
    writer       = csv.writer(output)
    writer.writerow([
        'Reservation Code', 'Customer Name', 'Phone', 'Plate Number',
        'Slot Number', 'Area', 'Start Time', 'End Time', 'Duration (Hours)',
        'Rate ($/hr)', 'Total ($)', 'Status', 'Payment Status', 'Created At'
    ])
    for r in reservations:
        writer.writerow([
            r['reservation_code'], r['customer_name'], r.get('customer_phone', ''),
            r['plate_number'], r['slot_number'], r['area_name'],
            r['start_time'], r['end_time'], r['duration_hours'],
            r['hourly_rate'], r['estimated_amount'], r['status'],
            r.get('payment_status', 'pending'), r['created_at']
        ])

    filename = f"reservations_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment;filename={filename}"})


# ═══════════════════════════════════════════════════════════════
#  PAYMENT ROUTES
#  (Formerly routes/payments.py)
# ═══════════════════════════════════════════════════════════════

@reservations_bp.route('/payments')
@login_required
def payments_index():
    """Payment management: revenue metrics and filterable transaction list."""
    search    = request.args.get('search', '').strip()
    status    = request.args.get('status', '')
    date_from = request.args.get('date_from', '')
    date_to   = request.args.get('date_to', '')

    return render_template(
        'payments.html',
        payments=list_payments(search=search, status=status,
                               date_from=date_from, date_to=date_to),
        summary=get_payment_summary(),
        search=search,
        selected_status=status,
        date_from=date_from,
        date_to=date_to
    )


@reservations_bp.route('/payments/<int:payment_id>/process-demo', methods=['POST'])
@login_required
def process_demo(payment_id):
    """Simulate a gateway payment (approve or decline)."""
    result = process_demo_payment(
        payment_id,
        payment_method=request.form.get('payment_method', 'Credit Card (Demo)'),
        simulate_status=request.form.get('simulate_status', 'paid')
    )
    if result['success']:
        flash(f"{result['message']} Transaction Reference: {result['transaction_ref']}", 'success')
    else:
        flash(result.get('error', result.get('message')), 'danger')
    return redirect(request.referrer or url_for('reservations.payments_index'))


@reservations_bp.route('/payments/<int:payment_id>/receipt')
@login_required
def payment_receipt(payment_id):
    """Show a printable receipt for a completed payment."""
    payment = get_payment_by_id(payment_id)
    if not payment:
        flash('Payment transaction not found.', 'danger')
        return redirect(url_for('reservations.payments_index'))
    return render_template('receipt.html', p=payment)


@reservations_bp.route('/payments/export/csv')
@login_required
def export_payments_csv():
    """Download payment transactions as a CSV file."""
    payments = list_payments(limit=1000)
    output   = io.StringIO()
    writer   = csv.writer(output)
    writer.writerow([
        'Payment Code', 'Reservation Code', 'Customer Name', 'Plate Number',
        'Amount ($)', 'Payment Method', 'Transaction Ref', 'Status', 'Date'
    ])
    for p in payments:
        writer.writerow([
            p['payment_code'], p['reservation_code'], p['customer_name'],
            p['plate_number'], p['amount'], p['payment_method'],
            p['transaction_ref'], p['status'], p['payment_date']
        ])

    filename = f"payments_revenue_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment;filename={filename}"})
