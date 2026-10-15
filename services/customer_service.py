"""
Customer Service
Handles customer listings, vehicle lookup, customer profile details,
and comprehensive customer reservation/payment histories.
"""

from database import query_db

def list_customers(search=None, limit=100):
    """List customers with aggregated vehicle and reservation statistics."""
    sql = """
        SELECT c.*, 
               COUNT(DISTINCT v.id) as vehicles_count,
               COUNT(DISTINCT r.id) as reservations_count,
               COALESCE(SUM(CASE WHEN p.status = 'paid' THEN p.amount ELSE 0 END), 0) as total_spent,
               GROUP_CONCAT(DISTINCT v.plate_number) as plates_list
        FROM customers c
        LEFT JOIN vehicles v ON c.id = v.customer_id
        LEFT JOIN reservations r ON c.id = r.customer_id
        LEFT JOIN payments p ON r.id = p.reservation_id
        WHERE 1=1
    """
    params = []

    if search:
        search_like = f"%{search.strip()}%"
        sql += """ AND (
            c.name LIKE %s OR 
            c.email LIKE %s OR 
            c.phone LIKE %s OR 
            v.plate_number LIKE %s
        )"""
        params.extend([search_like, search_like, search_like, search_like])

    sql += " GROUP BY c.id ORDER BY c.created_at DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"

    return query_db(sql, params, fetch_all=True)


def get_customer_details(customer_id):
    """Retrieve full customer profile with their vehicles, reservations, and payment records."""
    customer = query_db("SELECT * FROM customers WHERE id = %s", (customer_id,), fetch_one=True)
    if not customer:
        return None

    vehicles = query_db("SELECT * FROM vehicles WHERE customer_id = %s ORDER BY created_at DESC", (customer_id,), fetch_all=True)

    reservations = query_db("""
        SELECT r.*, v.plate_number, s.slot_number, a.area_name, p.status as payment_status
        FROM reservations r
        JOIN vehicles v ON r.vehicle_id = v.id
        JOIN parking_slots s ON r.slot_id = s.id
        JOIN parking_areas a ON s.area_id = a.id
        LEFT JOIN payments p ON r.id = p.reservation_id
        WHERE r.customer_id = %s
        ORDER BY r.created_at DESC
    """, (customer_id,), fetch_all=True)

    payments = query_db("""
        SELECT p.*, r.reservation_code
        FROM payments p
        JOIN reservations r ON p.reservation_id = r.id
        WHERE r.customer_id = %s
        ORDER BY p.payment_date DESC
    """, (customer_id,), fetch_all=True)

    return {
        'customer': customer,
        'vehicles': vehicles,
        'reservations': reservations,
        'payments': payments
    }
