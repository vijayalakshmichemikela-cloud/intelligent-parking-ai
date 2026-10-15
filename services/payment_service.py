"""
Payment Service
Handles simulated payment gateway processing, transaction references,
receipt generation, revenue calculations, and duplicate charge prevention.
"""

import uuid
import datetime
from database import query_db

def get_payment_by_id(payment_id):
    """Retrieve payment details with full reservation, customer, and slot info."""
    sql = """
        SELECT p.*, 
               r.reservation_code, r.start_time, r.end_time, r.duration_hours, r.hourly_rate,
               r.status as reservation_status,
               c.name as customer_name, c.email as customer_email, c.phone as customer_phone,
               v.plate_number, v.vehicle_type, v.vehicle_model,
               s.slot_number, s.slot_type, a.area_name, a.floor_level
        FROM payments p
        JOIN reservations r ON p.reservation_id = r.id
        JOIN customers c ON r.customer_id = c.id
        JOIN vehicles v ON r.vehicle_id = v.id
        JOIN parking_slots s ON r.slot_id = s.id
        JOIN parking_areas a ON s.area_id = a.id
        WHERE p.id = %s
    """
    return query_db(sql, (payment_id,), fetch_one=True)


def get_payment_by_reservation(reservation_id):
    """Get the primary payment record for a reservation."""
    sql = "SELECT * FROM payments WHERE reservation_id = %s ORDER BY id DESC"
    return query_db(sql, (reservation_id,), fetch_one=True)


def process_demo_payment(payment_id, payment_method='Credit Card (Demo)', simulate_status='paid'):
    """
    Process a simulated payment through the demo gateway.
    
    Args:
        payment_id (int): Existing payment ID
        payment_method (str): 'Credit Card (Demo)', 'UPI / QR (Demo)', 'Cash'
        simulate_status (str): 'paid' (success) or 'failed' (declined)
    
    Returns:
        dict: Result with updated transaction reference and status
    """
    payment = query_db("SELECT * FROM payments WHERE id = %s", (payment_id,), fetch_one=True)
    if not payment:
        return {'success': False, 'error': 'Payment record not found.'}
        
    if payment['status'] == 'paid':
        return {'success': False, 'error': 'This reservation has already been paid for. Duplicate payment prevented.'}

    # Generate unique transaction reference
    timestamp_str = datetime.datetime.now().strftime('%Y%m%d%H%M')
    txn_ref = f"TXN-DEMO-{timestamp_str}-{uuid.uuid4().hex[:6].upper()}"
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if simulate_status == 'paid':
        status = 'paid'
        notes = f"Payment successfully simulated via {payment_method} at {now_str}"
    else:
        status = 'failed'
        notes = f"Simulated gateway declined transaction via {payment_method} at {now_str} (Insufficient demo funds / test decline)"

    query_db(
        """UPDATE payments 
           SET status = %s, payment_method = %s, transaction_ref = %s, 
               payment_date = %s, notes = %s 
           WHERE id = %s""",
        (status, payment_method, txn_ref, now_str, notes, payment_id),
        commit=True
    )

    return {
        'success': (status == 'paid'),
        'payment_id': payment_id,
        'status': status,
        'transaction_ref': txn_ref,
        'message': 'Demo payment approved and processed!' if status == 'paid' else 'Demo payment transaction declined.'
    }


def list_payments(search=None, status=None, date_from=None, date_to=None, limit=100):
    """List payments with search and filtering for audit and revenue tracking."""
    sql = """
        SELECT p.*, 
               r.reservation_code,
               c.name as customer_name,
               v.plate_number,
               s.slot_number
        FROM payments p
        JOIN reservations r ON p.reservation_id = r.id
        JOIN customers c ON r.customer_id = c.id
        JOIN vehicles v ON r.vehicle_id = v.id
        JOIN parking_slots s ON r.slot_id = s.id
        WHERE 1=1
    """
    params = []

    if status and status != 'all':
        sql += " AND p.status = %s"
        params.append(status)

    if search:
        search_like = f"%{search.strip()}%"
        sql += """ AND (
            p.payment_code LIKE %s OR 
            p.transaction_ref LIKE %s OR 
            r.reservation_code LIKE %s OR 
            c.name LIKE %s OR 
            v.plate_number LIKE %s
        )"""
        params.extend([search_like, search_like, search_like, search_like, search_like])

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
    total_rev_row = query_db(
        "SELECT COALESCE(SUM(amount), 0) as total FROM payments WHERE status = 'paid'", 
        fetch_one=True
    )
    pending_row = query_db(
        "SELECT COALESCE(SUM(amount), 0) as pending FROM payments WHERE status = 'pending'", 
        fetch_one=True
    )
    paid_count_row = query_db(
        "SELECT COUNT(*) as count FROM payments WHERE status = 'paid'", 
        fetch_one=True
    )

    return {
        'total_revenue': float(total_rev_row['total']),
        'pending_amount': float(pending_row['pending']),
        'paid_transactions_count': int(paid_count_row['count'])
    }
