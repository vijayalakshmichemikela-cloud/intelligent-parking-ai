"""
Parking Service
Handles parking slot CRUD, areas/floors management, and slot safety validation.
"""

from database import query_db

def list_areas():
    """Retrieve all parking areas / floors."""
    return query_db("SELECT * FROM parking_areas ORDER BY floor_level, area_name ASC", fetch_all=True)


def get_area_by_id(area_id):
    """Retrieve a single parking area by ID."""
    return query_db("SELECT * FROM parking_areas WHERE id = %s", (area_id,), fetch_one=True)


def list_slots(search=None, area_id=None, slot_type=None, status=None):
    """
    List parking slots with search by slot number, filtering by area, type, and status.
    Returns list of slot dicts with joined area details.
    """
    sql = """
        SELECT s.*, a.area_name, a.floor_level 
        FROM parking_slots s
        JOIN parking_areas a ON s.area_id = a.id
        WHERE 1=1
    """
    params = []

    if search:
        sql += " AND s.slot_number LIKE %s"
        params.append(f"%{search.strip()}%")

    if area_id and area_id != 'all':
        sql += " AND s.area_id = %s"
        params.append(area_id)

    if slot_type and slot_type != 'all':
        sql += " AND s.slot_type = %s"
        params.append(slot_type)

    if status and status != 'all':
        sql += " AND s.status = %s"
        params.append(status)

    sql += " ORDER BY a.floor_level ASC, s.slot_number ASC"
    return query_db(sql, params, fetch_all=True)


def get_slot_by_id(slot_id):
    """Get single slot with area details."""
    sql = """
        SELECT s.*, a.area_name, a.floor_level 
        FROM parking_slots s
        JOIN parking_areas a ON s.area_id = a.id
        WHERE s.id = %s
    """
    return query_db(sql, (slot_id,), fetch_one=True)


def create_slot(slot_number, area_id, slot_type='regular', hourly_rate=5.00, status='available'):
    """
    Create a new parking slot.
    Validates duplicate slot number within the same parking area.
    """
    slot_number = slot_number.strip().upper()
    if not slot_number:
        return {'success': False, 'error': 'Slot number cannot be empty.'}

    try:
        hourly_rate = float(hourly_rate)
        if hourly_rate < 0:
            return {'success': False, 'error': 'Hourly rate cannot be negative.'}
    except ValueError:
        return {'success': False, 'error': 'Hourly rate must be a valid number.'}

    # Verify area exists
    area = get_area_by_id(area_id)
    if not area:
        return {'success': False, 'error': 'Selected parking area does not exist.'}

    # Check for duplicate slot number in this area
    existing = query_db(
        "SELECT id FROM parking_slots WHERE slot_number = %s AND area_id = %s",
        (slot_number, area_id),
        fetch_one=True
    )
    if existing:
        return {'success': False, 'error': f'Slot "{slot_number}" already exists in {area["area_name"]}.'}

    try:
        new_id = query_db(
            """INSERT INTO parking_slots (slot_number, area_id, slot_type, hourly_rate, status) 
               VALUES (%s, %s, %s, %s, %s)""",
            (slot_number, area_id, slot_type, hourly_rate, status),
            commit=True
        )
        return {'success': True, 'slot_id': new_id, 'message': f'Slot {slot_number} created successfully.'}
    except Exception as e:
        return {'success': False, 'error': f'Failed to create slot: {str(e)}'}


def update_slot(slot_id, slot_number, area_id, slot_type, hourly_rate, status):
    """Update details of an existing parking slot."""
    slot = get_slot_by_id(slot_id)
    if not slot:
        return {'success': False, 'error': 'Parking slot not found.'}

    slot_number = slot_number.strip().upper()
    if not slot_number:
        return {'success': False, 'error': 'Slot number cannot be empty.'}

    try:
        hourly_rate = float(hourly_rate)
        if hourly_rate < 0:
            return {'success': False, 'error': 'Hourly rate cannot be negative.'}
    except ValueError:
        return {'success': False, 'error': 'Hourly rate must be a valid number.'}

    # If slot is currently occupied, don't allow changing status to available without checkout
    if slot['status'] == 'occupied' and status != 'occupied':
        return {'success': False, 'error': 'Slot is currently occupied by a parked vehicle. Check out the vehicle first.'}

    # Check duplicate slot number in same area (excluding itself)
    existing = query_db(
        "SELECT id FROM parking_slots WHERE slot_number = %s AND area_id = %s AND id != %s",
        (slot_number, area_id, slot_id),
        fetch_one=True
    )
    if existing:
        return {'success': False, 'error': f'Another slot with number "{slot_number}" already exists in this area.'}

    try:
        query_db(
            """UPDATE parking_slots 
               SET slot_number = %s, area_id = %s, slot_type = %s, hourly_rate = %s, status = %s 
               WHERE id = %s""",
            (slot_number, area_id, slot_type, hourly_rate, status, slot_id),
            commit=True
        )
        return {'success': True, 'message': f'Slot {slot_number} updated successfully.'}
    except Exception as e:
        return {'success': False, 'error': f'Failed to update slot: {str(e)}'}


def delete_slot(slot_id):
    """
    Delete a parking slot only if it has NO active reservation or occupancy.
    Strict business rule requirement.
    """
    slot = get_slot_by_id(slot_id)
    if not slot:
        return {'success': False, 'error': 'Parking slot not found.'}

    if slot['status'] in ('occupied', 'reserved'):
        return {
            'success': False, 
            'error': f'Cannot delete slot {slot["slot_number"]}: Current status is "{slot["status"]}".'
        }

    # Check for active reservations
    active_res = query_db(
        "SELECT id, reservation_code, status FROM reservations WHERE slot_id = %s AND status IN ('active', 'reserved')",
        (slot_id,),
        fetch_one=True
    )
    if active_res:
        return {
            'success': False,
            'error': f'Cannot delete slot {slot["slot_number"]}: Bound to active reservation {active_res["reservation_code"]}.'
        }

    # Check for active sessions
    active_sess = query_db(
        "SELECT id FROM parking_sessions WHERE slot_id = %s AND status = 'active'",
        (slot_id,),
        fetch_one=True
    )
    if active_sess:
        return {
            'success': False,
            'error': f'Cannot delete slot {slot["slot_number"]}: There is an active vehicle session parked in this slot.'
        }

    try:
        # Delete associated logs and slot
        query_db("DELETE FROM occupancy_logs WHERE slot_id = %s", (slot_id,), commit=True)
        query_db("DELETE FROM parking_slots WHERE id = %s", (slot_id,), commit=True)
        return {'success': True, 'message': f'Slot {slot["slot_number"]} deleted successfully.'}
    except Exception as e:
        return {'success': False, 'error': f'Failed to delete slot: {str(e)}'}
