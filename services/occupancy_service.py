"""
Occupancy Service
Handles real-time parking occupancy, vehicle check-in, check-out,
parking session tracking, duration calculations, and occupancy logs.
"""

import datetime
from database import query_db, get_db_connection

def get_occupancy_overview():
    """
    Compute real-time parking capacity, counts, and occupancy percentage.
    Formula: Occupancy Percentage = (Occupied Spaces / Total Parking Spaces) * 100
    """
    total_row = query_db("SELECT COUNT(*) as total FROM parking_slots WHERE status != 'maintenance'", fetch_one=True)
    all_slots_row = query_db("SELECT COUNT(*) as total FROM parking_slots", fetch_one=True)
    
    status_counts = query_db("""
        SELECT status, COUNT(*) as count 
        FROM parking_slots 
        GROUP BY status
    """, fetch_all=True)

    counts = {'available': 0, 'reserved': 0, 'occupied': 0, 'maintenance': 0}
    for row in status_counts:
        counts[row['status']] = row['count']

    total_capacity = all_slots_row['total'] or 0
    operational_capacity = total_row['total'] or 0
    occupied = counts['occupied']
    available = counts['available']
    reserved = counts['reserved']
    maintenance = counts['maintenance']

    occupancy_pct = round((occupied / operational_capacity * 100), 1) if operational_capacity > 0 else 0.0

    return {
        'total_capacity': total_capacity,
        'operational_capacity': operational_capacity,
        'occupied': occupied,
        'available': available,
        'reserved': reserved,
        'maintenance': maintenance,
        'occupancy_percentage': occupancy_pct
    }


def check_in_vehicle(reservation_id):
    """
    Perform vehicle check-in for a reservation.
    1. Verify reservation exists & eligible (reserved/pending).
    2. Verify slot is not occupied.
    3. Update reservation to 'active'.
    4. Mark slot as 'occupied'.
    5. Record check_in_time in parking_sessions.
    6. Record event in occupancy_logs.
    """
    res = query_db("""
        SELECT r.*, v.plate_number, s.slot_number, s.status as slot_status 
        FROM reservations r
        JOIN vehicles v ON r.vehicle_id = v.id
        JOIN parking_slots s ON r.slot_id = s.id
        WHERE r.id = %s
    """, (reservation_id,), fetch_one=True)

    if not res:
        return {'success': False, 'error': 'Reservation not found.'}

    if res['status'] == 'active':
        return {'success': False, 'error': 'Vehicle is already checked in.'}

    if res['status'] in ('completed', 'cancelled'):
        return {'success': False, 'error': f'Cannot check in. Reservation is already {res["status"]}.'}

    # Verify slot is not occupied by another vehicle
    slot_id = res['slot_id']
    active_session_on_slot = query_db(
        "SELECT id, vehicle_plate FROM parking_sessions WHERE slot_id = %s AND status = 'active'",
        (slot_id,),
        fetch_one=True
    )
    if active_session_on_slot:
        return {
            'success': False, 
            'error': f'Slot {res["slot_number"]} is currently occupied by vehicle {active_session_on_slot["vehicle_plate"]}.'
        }

    now = datetime.datetime.now()
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')

    conn, engine = get_db_connection()
    try:
        cur = conn.cursor()

        # Update reservation to 'active'
        upd_res_sql = "UPDATE reservations SET status = 'active' WHERE id = %s" if engine == 'mysql' else "UPDATE reservations SET status = 'active' WHERE id = ?"
        cur.execute(upd_res_sql, (reservation_id,))

        # Update slot to 'occupied'
        upd_slot_sql = "UPDATE parking_slots SET status = 'occupied' WHERE id = %s" if engine == 'mysql' else "UPDATE parking_slots SET status = 'occupied' WHERE id = ?"
        cur.execute(upd_slot_sql, (slot_id,))

        # Create or update parking session
        ins_sess_sql = (
            """INSERT INTO parking_sessions 
               (reservation_id, slot_id, vehicle_plate, check_in_time, status) 
               VALUES (%s, %s, %s, %s, 'active')"""
            if engine == 'mysql' else
            """INSERT INTO parking_sessions 
               (reservation_id, slot_id, vehicle_plate, check_in_time, status) 
               VALUES (?, ?, ?, ?, 'active')"""
        )
        cur.execute(ins_sess_sql, (reservation_id, slot_id, res['plate_number'], now_str))

        # Log occupancy event
        log_notes = f"Vehicle {res['plate_number']} checked in for {res['reservation_code']}"
        ins_log_sql = (
            "INSERT INTO occupancy_logs (slot_id, event_type, timestamp, notes) VALUES (%s, 'check_in', %s, %s)"
            if engine == 'mysql' else
            "INSERT INTO occupancy_logs (slot_id, event_type, timestamp, notes) VALUES (?, 'check_in', ?, ?)"
        )
        cur.execute(ins_log_sql, (slot_id, now_str, log_notes))

        conn.commit()
        cur.close()
        conn.close()

        return {
            'success': True,
            'message': f'Vehicle {res["plate_number"]} checked in to slot {res["slot_number"]}.',
            'check_in_time': now_str
        }

    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        return {'success': False, 'error': f'Check-in failed: {str(e)}'}


def check_out_vehicle(reservation_id):
    """
    Perform vehicle check-out for an active reservation.
    1. Verify reservation is active.
    2. Record checkout time.
    3. Calculate actual duration and final fee if actual duration billing is enabled.
    4. Mark reservation 'completed', session 'completed'.
    5. Release parking slot if no conflicting active booking.
    6. Record event in occupancy_logs.
    """
    res = query_db("""
        SELECT r.*, v.plate_number, s.slot_number, s.hourly_rate as slot_rate 
        FROM reservations r
        JOIN vehicles v ON r.vehicle_id = v.id
        JOIN parking_slots s ON r.slot_id = s.id
        WHERE r.id = %s
    """, (reservation_id,), fetch_one=True)

    if not res:
        return {'success': False, 'error': 'Reservation not found.'}

    if res['status'] != 'active':
        return {'success': False, 'error': f'Vehicle is not currently checked in (Status: {res["status"]}).'}

    # Get active session
    session = query_db(
        "SELECT * FROM parking_sessions WHERE reservation_id = %s AND status = 'active' ORDER BY id DESC",
        (reservation_id,),
        fetch_one=True
    )
    if not session:
        return {'success': False, 'error': 'No active parking session found for this reservation.'}

    now = datetime.datetime.now()
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')

    # Calculate actual duration
    check_in_time = session['check_in_time']
    if isinstance(check_in_time, str):
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M'):
            try:
                check_in_time = datetime.datetime.strptime(check_in_time, fmt)
                break
            except ValueError:
                continue

    if isinstance(check_in_time, datetime.datetime):
        duration_seconds = max(0, (now - check_in_time).total_seconds())
        actual_hours = max(1.0, round(duration_seconds / 3600.0, 2))
    else:
        actual_hours = float(res['duration_hours'])

    rate = float(res['hourly_rate'])
    final_amount = round(actual_hours * rate, 2)

    slot_id = res['slot_id']
    conn, engine = get_db_connection()
    try:
        cur = conn.cursor()

        # Update parking session
        upd_sess_sql = (
            """UPDATE parking_sessions 
               SET check_out_time = %s, actual_duration_hours = %s, final_amount = %s, status = 'completed' 
               WHERE id = %s"""
            if engine == 'mysql' else
            """UPDATE parking_sessions 
               SET check_out_time = ?, actual_duration_hours = ?, final_amount = ?, status = 'completed' 
               WHERE id = ?"""
        )
        cur.execute(upd_sess_sql, (now_str, actual_hours, final_amount, session['id']))

        # Update reservation status to completed
        upd_res_sql = "UPDATE reservations SET status = 'completed' WHERE id = %s" if engine == 'mysql' else "UPDATE reservations SET status = 'completed' WHERE id = ?"
        cur.execute(upd_res_sql, (reservation_id,))

        # Release slot: Check if there is another upcoming reservation currently active
        find_next_sql = (
            """SELECT id FROM reservations 
               WHERE slot_id = %s AND status = 'reserved' 
                 AND start_time <= %s AND end_time >= %s"""
            if engine == 'mysql' else
            """SELECT id FROM reservations 
               WHERE slot_id = ? AND status = 'reserved' 
                 AND start_time <= ? AND end_time >= ?"""
        )
        cur.execute(find_next_sql, (slot_id, now_str, now_str))
        next_res = cur.fetchone()

        new_slot_status = 'reserved' if next_res else 'available'
        upd_slot_sql = "UPDATE parking_slots SET status = %s WHERE id = %s" if engine == 'mysql' else "UPDATE parking_slots SET status = ? WHERE id = ?"
        cur.execute(upd_slot_sql, (new_slot_status, slot_id))

        # Log occupancy checkout event
        log_notes = f"Vehicle {res['plate_number']} checked out. Slot {res['slot_number']} released to {new_slot_status}."
        ins_log_sql = (
            "INSERT INTO occupancy_logs (slot_id, event_type, timestamp, notes) VALUES (%s, 'check_out', %s, %s)"
            if engine == 'mysql' else
            "INSERT INTO occupancy_logs (slot_id, event_type, timestamp, notes) VALUES (?, 'check_out', ?, ?)"
        )
        cur.execute(ins_log_sql, (slot_id, now_str, log_notes))

        conn.commit()
        cur.close()
        conn.close()

        return {
            'success': True,
            'message': f'Vehicle {res["plate_number"]} checked out from slot {res["slot_number"]}.',
            'check_out_time': now_str,
            'actual_hours': actual_hours,
            'final_amount': final_amount
        }

    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        return {'success': False, 'error': f'Check-out failed: {str(e)}'}


def get_active_sessions(limit=50):
    """Retrieve list of all vehicles currently parked in the facility."""
    sql = """
        SELECT ps.*, 
               r.reservation_code, r.start_time, r.end_time,
               c.name as customer_name, c.phone as customer_phone,
               s.slot_number, s.slot_type, a.area_name, a.floor_level
        FROM parking_sessions ps
        JOIN reservations r ON ps.reservation_id = r.id
        JOIN customers c ON r.customer_id = c.id
        JOIN parking_slots s ON ps.slot_id = s.id
        JOIN parking_areas a ON s.area_id = a.id
        WHERE ps.status = 'active'
        ORDER BY ps.check_in_time DESC
        LIMIT %s
    """
    return query_db(sql, (limit,), fetch_all=True)


def get_occupancy_logs(limit=50):
    """Retrieve recent check-in/check-out logs."""
    sql = """
        SELECT l.*, s.slot_number, a.area_name
        FROM occupancy_logs l
        JOIN parking_slots s ON l.slot_id = s.id
        JOIN parking_areas a ON s.area_id = a.id
        ORDER BY l.timestamp DESC
        LIMIT %s
    """
    return query_db(sql, (limit,), fetch_all=True)
