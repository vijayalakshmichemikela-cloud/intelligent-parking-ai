"""
Reservation Service
Handles business logic for parking space reservations:
- Concurrency and double-booking overlap prevention
- Time validation (no past times, end > start)
- Price calculation based on slot hourly rate and duration
- Customer & vehicle auto-linking
- Reservation lifecycle management (create, cancel, details, list)
"""

import uuid
import datetime
from decimal import Decimal
from database import query_db, get_db_connection

def parse_datetime(dt_val):
    """Safely parse string or datetime object into datetime object."""
    if isinstance(dt_val, datetime.datetime):
        return dt_val
    if isinstance(dt_val, str):
        for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
            try:
                return datetime.datetime.strptime(dt_val, fmt)
            except ValueError:
                continue
    raise ValueError(f"Invalid datetime format: {dt_val}")


def is_slot_available(slot_id, start_time, end_time, exclude_res_id=None):
    """
    Check if a parking slot is free from overlapping reservations during [start_time, end_time].
    An overlap exists if: (existing.start < new.end) AND (existing.end > new.start)
    for any reservation in ('reserved', 'active').
    """
    st_dt = parse_datetime(start_time)
    et_dt = parse_datetime(end_time)
    st_str = st_dt.strftime('%Y-%m-%d %H:%M:%S')
    et_str = et_dt.strftime('%Y-%m-%d %H:%M:%S')

    # Exclude specific reservation if editing/updating
    sql = """
        SELECT id, reservation_code, start_time, end_time, status 
        FROM reservations
        WHERE slot_id = %s
          AND status IN ('reserved', 'active')
          AND (start_time < %s AND end_time > %s)
    """
    params = [slot_id, et_str, st_str]
    
    if exclude_res_id:
        sql += " AND id != %s"
        params.append(exclude_res_id)

    conflicts = query_db(sql, params, fetch_all=True)
    return len(conflicts) == 0, conflicts


def calculate_fee(slot_id, start_time, end_time):
    """
    Calculate duration (in hours) and estimated parking fee.
    Enforces minimum 1 hour billing.
    """
    st = parse_datetime(start_time)
    et = parse_datetime(end_time)
    
    if et <= st:
        raise ValueError("End time must be strictly after start time.")
    
    delta_seconds = (et - st).total_seconds()
    duration_hours = max(1.0, round(delta_seconds / 3600.0, 2))
    
    slot = query_db("SELECT id, slot_number, hourly_rate FROM parking_slots WHERE id = %s", (slot_id,), fetch_one=True)
    if not slot:
        raise ValueError(f"Parking slot ID {slot_id} does not exist.")
        
    hourly_rate = float(slot['hourly_rate'])
    estimated_amount = round(duration_hours * hourly_rate, 2)
    
    return {
        'slot': slot,
        'duration_hours': duration_hours,
        'hourly_rate': hourly_rate,
        'estimated_amount': estimated_amount
    }


def find_available_slots(start_time, end_time, area_id=None, slot_type=None):
    """Find all slots that have no conflicting reservations in the given time window."""
    st = parse_datetime(start_time)
    et = parse_datetime(end_time)
    st_str = st.strftime('%Y-%m-%d %H:%M:%S')
    et_str = et.strftime('%Y-%m-%d %H:%M:%S')
    
    sql = """
        SELECT s.*, a.area_name, a.floor_level 
        FROM parking_slots s
        JOIN parking_areas a ON s.area_id = a.id
        WHERE s.status != 'maintenance'
          AND s.id NOT IN (
              SELECT DISTINCT slot_id 
              FROM reservations 
              WHERE status IN ('reserved', 'active')
                AND (start_time < %s AND end_time > %s)
          )
    """
    params = [et_str, st_str]
    
    if area_id:
        sql += " AND s.area_id = %s"
        params.append(area_id)
        
    if slot_type:
        sql += " AND s.slot_type = %s"
        params.append(slot_type)
        
    sql += " ORDER BY a.floor_level, s.slot_number ASC"
    return query_db(sql, params, fetch_all=True)


def create_reservation(customer_name, vehicle_plate, slot_id, start_time, end_time, 
                       customer_email=None, customer_phone=None, vehicle_type='Sedan', 
                       vehicle_model=None, notes=None):
    """
    Atomically validate and create a new reservation.
    Performs server-side validation, overlap prevention, customer/vehicle linkage.
    """
    st = parse_datetime(start_time)
    et = parse_datetime(end_time)
    now = datetime.datetime.now()

    # Rule 1: End time must be later than start time
    if et <= st:
        return {'success': False, 'error': 'End time must be later than start time.'}

    # Rule 6: Reject invalid or past start times (allowing 10 min grace period for submission latency)
    if st < (now - datetime.timedelta(minutes=10)):
        return {'success': False, 'error': 'Reservation start time cannot be in the past.'}

    # Clean inputs
    customer_name = customer_name.strip()
    vehicle_plate = vehicle_plate.strip().upper()
    if not customer_name:
        return {'success': False, 'error': 'Customer name is required.'}
    if not vehicle_plate:
        return {'success': False, 'error': 'Vehicle plate number is required.'}

    # Check slot existence and active status
    slot = query_db("SELECT * FROM parking_slots WHERE id = %s", (slot_id,), fetch_one=True)
    if not slot:
        return {'success': False, 'error': 'Selected parking slot does not exist.'}
    if slot['status'] == 'maintenance':
        return {'success': False, 'error': 'Selected slot is currently out of service (Maintenance).'}

    # Rule 2 & 4: Double check availability on backend
    available, conflicts = is_slot_available(slot_id, st, et)
    if not available:
        conflict_code = conflicts[0].get('reservation_code', 'existing booking')
        return {
            'success': False, 
            'error': f'Slot {slot["slot_number"]} is already booked ({conflict_code}) during this timeframe.'
        }

    # Calculate fee
    fee_info = calculate_fee(slot_id, st, et)
    duration_hours = fee_info['duration_hours']
    hourly_rate = fee_info['hourly_rate']
    estimated_amount = fee_info['estimated_amount']

    # Database transaction via direct connection
    conn, engine = get_db_connection()
    try:
        cur = conn.cursor()
        
        # 1. Customer: find existing by name/phone or create
        cust_row = None
        if customer_phone:
            find_cust_sql = "SELECT id FROM customers WHERE phone = %s" if engine == 'mysql' else "SELECT id FROM customers WHERE phone = ?"
            cur.execute(find_cust_sql, (customer_phone,))
            cust_row = cur.fetchone()
        
        if not cust_row and customer_email:
            find_cust_sql = "SELECT id FROM customers WHERE email = %s" if engine == 'mysql' else "SELECT id FROM customers WHERE email = ?"
            cur.execute(find_cust_sql, (customer_email,))
            cust_row = cur.fetchone()

        if cust_row:
            customer_id = cust_row[0] if isinstance(cust_row, tuple) else cust_row['id']
        else:
            ins_cust_sql = (
                "INSERT INTO customers (name, email, phone) VALUES (%s, %s, %s)" 
                if engine == 'mysql' else 
                "INSERT INTO customers (name, email, phone) VALUES (?, ?, ?)"
            )
            cur.execute(ins_cust_sql, (customer_name, customer_email, customer_phone))
            customer_id = cur.lastrowid

        # 2. Vehicle: find existing by plate or create
        find_veh_sql = "SELECT id FROM vehicles WHERE plate_number = %s" if engine == 'mysql' else "SELECT id FROM vehicles WHERE plate_number = ?"
        cur.execute(find_veh_sql, (vehicle_plate,))
        veh_row = cur.fetchone()
        
        if veh_row:
            vehicle_id = veh_row[0] if isinstance(veh_row, tuple) else veh_row['id']
        else:
            ins_veh_sql = (
                "INSERT INTO vehicles (customer_id, plate_number, vehicle_type, vehicle_model) VALUES (%s, %s, %s, %s)" 
                if engine == 'mysql' else 
                "INSERT INTO vehicles (customer_id, plate_number, vehicle_type, vehicle_model) VALUES (?, ?, ?, ?)"
            )
            cur.execute(ins_veh_sql, (customer_id, vehicle_plate, vehicle_type, vehicle_model))
            vehicle_id = cur.lastrowid

        # 3. Generate unique reservation code
        res_code = f"RES-{datetime.datetime.now().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"

        # 4. Insert Reservation
        st_str = st.strftime('%Y-%m-%d %H:%M:%S')
        et_str = et.strftime('%Y-%m-%d %H:%M:%S')

        ins_res_sql = (
            """INSERT INTO reservations 
               (reservation_code, customer_id, vehicle_id, slot_id, start_time, end_time, 
                duration_hours, hourly_rate, estimated_amount, status, notes) 
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'reserved', %s)"""
            if engine == 'mysql' else
            """INSERT INTO reservations 
               (reservation_code, customer_id, vehicle_id, slot_id, start_time, end_time, 
                duration_hours, hourly_rate, estimated_amount, status, notes) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'reserved', ?)"""
        )
        cur.execute(ins_res_sql, (
            res_code, customer_id, vehicle_id, slot_id, st_str, et_str,
            duration_hours, hourly_rate, estimated_amount, notes
        ))
        res_id = cur.lastrowid

        # 5. Create associated Pending Payment record
        pay_code = f"PAY-{datetime.datetime.now().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"
        txn_ref = f"TXN-PENDING-{uuid.uuid4().hex[:8].upper()}"
        
        ins_pay_sql = (
            """INSERT INTO payments 
               (payment_code, reservation_id, amount, payment_method, transaction_ref, status, notes) 
               VALUES (%s, %s, %s, 'demo_gateway', %s, 'pending', 'Initial reservation charge')"""
            if engine == 'mysql' else
            """INSERT INTO payments 
               (payment_code, reservation_id, amount, payment_method, transaction_ref, status, notes) 
               VALUES (?, ?, ?, 'demo_gateway', ?, 'pending', 'Initial reservation charge')"""
        )
        cur.execute(ins_pay_sql, (pay_code, res_id, estimated_amount, txn_ref))

        # 6. Update slot status to 'reserved' if starting within 1 hour and currently available
        if (st - now).total_seconds() <= 3600 and slot['status'] == 'available':
            upd_slot_sql = "UPDATE parking_slots SET status = 'reserved' WHERE id = %s" if engine == 'mysql' else "UPDATE parking_slots SET status = 'reserved' WHERE id = ?"
            cur.execute(upd_slot_sql, (slot_id,))

        conn.commit()
        cur.close()
        conn.close()

        return {
            'success': True,
            'reservation_id': res_id,
            'reservation_code': res_code,
            'estimated_amount': estimated_amount,
            'message': f'Reservation {res_code} confirmed successfully!'
        }

    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        return {'success': False, 'error': f'Failed to create reservation: {str(e)}'}


def cancel_reservation(reservation_id, reason="Customer cancelled"):
    """
    Cancel an existing reservation if eligible (status is 'reserved' or 'pending').
    Active reservations cannot be cancelled directly; they must undergo check-out.
    Releases slot if reserved.
    """
    res = query_db("SELECT * FROM reservations WHERE id = %s", (reservation_id,), fetch_one=True)
    if not res:
        return {'success': False, 'error': 'Reservation not found.'}
        
    if res['status'] in ('completed', 'cancelled'):
        return {'success': False, 'error': f'Reservation is already {res["status"]}.'}
        
    if res['status'] == 'active':
        return {'success': False, 'error': 'Cannot cancel an active vehicle session. Please perform Check-Out.'}

    # Update status to cancelled
    query_db(
        "UPDATE reservations SET status = 'cancelled', notes = CONCAT(COALESCE(notes, ''), ' [Cancelled: ', %s, ']') WHERE id = %s",
        (reason, reservation_id),
        commit=True
    )

    # Check if slot should be returned to available
    slot_id = res['slot_id']
    # If no other active or upcoming reservation on this slot right now
    active_conflicts = query_db(
        "SELECT id FROM reservations WHERE slot_id = %s AND status IN ('reserved', 'active') AND id != %s",
        (slot_id, reservation_id),
        fetch_all=True
    )
    if len(active_conflicts) == 0:
        query_db("UPDATE parking_slots SET status = 'available' WHERE id = %s AND status = 'reserved'", (slot_id,), commit=True)

    return {'success': True, 'message': f'Reservation {res["reservation_code"]} has been cancelled.'}


def get_reservation_details(reservation_id):
    """Retrieve full details of a reservation including customer, vehicle, slot, payment."""
    sql = """
        SELECT r.*, 
               c.name as customer_name, c.email as customer_email, c.phone as customer_phone,
               v.plate_number, v.vehicle_type, v.vehicle_model,
               s.slot_number, s.slot_type, a.area_name, a.floor_level,
               p.id as payment_id, p.payment_code, p.status as payment_status, 
               p.payment_method, p.transaction_ref, p.amount as payment_amount, p.payment_date,
               ps.id as session_id, ps.check_in_time, ps.check_out_time, ps.status as session_status
        FROM reservations r
        JOIN customers c ON r.customer_id = c.id
        JOIN vehicles v ON r.vehicle_id = v.id
        JOIN parking_slots s ON r.slot_id = s.id
        JOIN parking_areas a ON s.area_id = a.id
        LEFT JOIN payments p ON r.id = p.reservation_id
        LEFT JOIN parking_sessions ps ON r.id = ps.reservation_id
        WHERE r.id = %s
    """
    return query_db(sql, (reservation_id,), fetch_one=True)


def list_reservations(search=None, status=None, date_from=None, date_to=None, slot_id=None, limit=100):
    """List reservations with rich search, status filtering, and sorting."""
    sql = """
        SELECT r.*, 
               c.name as customer_name, c.phone as customer_phone,
               v.plate_number,
               s.slot_number, a.area_name,
               p.status as payment_status, p.payment_code
        FROM reservations r
        JOIN customers c ON r.customer_id = c.id
        JOIN vehicles v ON r.vehicle_id = v.id
        JOIN parking_slots s ON r.slot_id = s.id
        JOIN parking_areas a ON s.area_id = a.id
        LEFT JOIN payments p ON r.id = p.reservation_id
        WHERE 1=1
    """
    params = []

    if status and status != 'all':
        sql += " AND r.status = %s"
        params.append(status)

    if search:
        search_like = f"%{search.strip()}%"
        sql += """ AND (
            r.reservation_code LIKE %s OR 
            c.name LIKE %s OR 
            v.plate_number LIKE %s OR 
            s.slot_number LIKE %s
        )"""
        params.extend([search_like, search_like, search_like, search_like])

    if slot_id:
        sql += " AND r.slot_id = %s"
        params.append(slot_id)

    if date_from:
        sql += " AND r.start_time >= %s"
        params.append(f"{date_from} 00:00:00")

    if date_to:
        sql += " AND r.start_time <= %s"
        params.append(f"{date_to} 23:59:59")

    sql += " ORDER BY r.created_at DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"

    return query_db(sql, params, fetch_all=True)
