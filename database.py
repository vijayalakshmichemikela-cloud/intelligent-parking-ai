"""
Database management module for Smart Parking Management System.
Supports MySQL as primary database via mysql-connector-python.
Provides automatic SQLite fallback if MySQL server is offline, ensuring
the application can be demonstrated and tested without manual DB server setup.
"""

import os
import sqlite3
import datetime
import logging
from config import Config

logger = logging.getLogger(__name__)

# Track active database backend
_ACTIVE_ENGINE = None
_MYSQL_AVAILABLE = False

try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
    _MYSQL_MODULE_LOADED = True
except ImportError:
    _MYSQL_MODULE_LOADED = False
    MySQLError = Exception


def test_mysql_connection():
    """Attempt a test connection to MySQL using configured credentials."""
    if not _MYSQL_MODULE_LOADED:
        return False, "mysql-connector-python not installed"
    
    try:
        conn = mysql.connector.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            connection_timeout=2
        )
        if conn.is_connected():
            conn.close()
            return True, "Connected successfully"
    except MySQLError as err:
        return False, str(err)
    except Exception as e:
        return False, str(e)
    return False, "Unknown connection error"


def get_active_engine():
    """Return the active engine: 'mysql' or 'sqlite'."""
    global _ACTIVE_ENGINE
    if _ACTIVE_ENGINE is not None:
        return _ACTIVE_ENGINE

    if Config.DB_ENGINE == 'mysql':
        success, msg = test_mysql_connection()
        if success:
            _ACTIVE_ENGINE = 'mysql'
            logger.info("Using MySQL database: %s@%s:%s", Config.DB_NAME, Config.DB_HOST, Config.DB_PORT)
        else:
            logger.warning(
                "MySQL connection to '%s' at %s:%s failed: %s. "
                "Switching automatically to SQLite fallback (%s) for demonstration and testing.",
                Config.DB_NAME, Config.DB_HOST, Config.DB_PORT, msg, Config.SQLITE_PATH
            )
            _ACTIVE_ENGINE = 'sqlite'
    else:
        _ACTIVE_ENGINE = 'sqlite'

    return _ACTIVE_ENGINE


def get_db_connection():
    """
    Get a new connection to the active database.
    Returns: (connection, engine_type)
    """
    engine = get_active_engine()
    
    if engine == 'mysql':
        try:
            conn = mysql.connector.connect(
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                database=Config.DB_NAME,
                autocommit=False
            )
            return conn, 'mysql'
        except Exception as e:
            logger.error("MySQL connection lost: %s. Falling back to SQLite.", e)
            return get_sqlite_connection(), 'sqlite'
    else:
        return get_sqlite_connection(), 'sqlite'


def get_sqlite_connection():
    """Return an SQLite connection configured with Row factory."""
    conn = sqlite3.connect(Config.SQLITE_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys in SQLite
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def query_db(sql, params=None, fetch_all=True, fetch_one=False, commit=False):
    """
    Execute a parameterized SQL query with automatic cursor management and dict-like results.
    
    Args:
        sql (str): SQL query with %s placeholders
        params (tuple or list): Parameters for the query
        fetch_all (bool): Return all rows as a list of dicts
        fetch_one (bool): Return a single row as a dict
        commit (bool): Commit the transaction
    
    Returns:
        list of dicts, single dict, or lastrowid / affected rows
    """
    conn, engine = get_db_connection()
    params = params or ()
    
    # If SQLite, convert %s to ?
    formatted_sql = sql
    if engine == 'sqlite':
        formatted_sql = sql.replace('%s', '?')
        # Adapt MySQL specific intervals or functions if present in queries
        # (our services use Python datetime calculations so this is minimal)

    try:
        if engine == 'mysql':
            cursor = conn.cursor(dictionary=True)
            cursor.execute(formatted_sql, params)
            
            if commit:
                conn.commit()
                last_id = cursor.lastrowid
                row_count = cursor.rowcount
                cursor.close()
                conn.close()
                return last_id if last_id else row_count
            
            if fetch_one:
                row = cursor.fetchone()
                cursor.close()
                conn.close()
                return row
            
            if fetch_all:
                rows = cursor.fetchall()
                cursor.close()
                conn.close()
                return rows
            
            cursor.close()
            conn.close()
            return True
            
        else: # sqlite
            cursor = conn.cursor()
            cursor.execute(formatted_sql, params)
            
            if commit:
                conn.commit()
                last_id = cursor.lastrowid
                row_count = cursor.rowcount
                cursor.close()
                conn.close()
                return last_id if last_id else row_count
            
            if fetch_one:
                row = cursor.fetchone()
                result = dict(row) if row else None
                cursor.close()
                conn.close()
                return result
            
            if fetch_all:
                rows = cursor.fetchall()
                result = [dict(r) for r in rows]
                cursor.close()
                conn.close()
                return result
            
            cursor.close()
            conn.close()
            return True

    except Exception as e:
        if commit and conn:
            try:
                conn.rollback()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        logger.error("Database query error: %s | Query: %s | Params: %s", e, formatted_sql, params)
        raise e


def get_db_info():
    """Return status information about database connection for dashboard."""
    engine = get_active_engine()
    if engine == 'mysql':
        return {
            'engine': 'MySQL',
            'is_fallback': False,
            'host': Config.DB_HOST,
            'port': Config.DB_PORT,
            'database': Config.DB_NAME,
            'status': 'Connected (MySQL Server)'
        }
    else:
        is_fallback = (Config.DB_ENGINE == 'mysql')
        return {
            'engine': 'SQLite',
            'is_fallback': is_fallback,
            'host': 'localhost',
            'port': '-',
            'database': os.path.basename(Config.SQLITE_PATH),
            'status': 'Active (Demo Fallback)' if is_fallback else 'Active (SQLite Mode)'
        }


def init_sqlite_db():
    """Initialize SQLite database with schema and sample seeds matching schema.sql."""
    conn = get_sqlite_connection()
    cur = conn.cursor()
    
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'admin',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP NULL
    );

    CREATE TABLE IF NOT EXISTS parking_areas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        area_name TEXT NOT NULL UNIQUE,
        floor_level TEXT NOT NULL,
        total_capacity INTEGER NOT NULL DEFAULT 0,
        description TEXT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS parking_slots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slot_number TEXT NOT NULL,
        area_id INTEGER NOT NULL,
        slot_type TEXT NOT NULL DEFAULT 'regular',
        hourly_rate REAL NOT NULL DEFAULT 5.00,
        status TEXT NOT NULL DEFAULT 'available',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (slot_number, area_id),
        FOREIGN KEY (area_id) REFERENCES parking_areas(id) ON DELETE RESTRICT
    );

    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NULL,
        phone TEXT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS vehicles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        plate_number TEXT NOT NULL UNIQUE,
        vehicle_type TEXT NOT NULL DEFAULT 'Sedan',
        vehicle_model TEXT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS reservations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reservation_code TEXT NOT NULL UNIQUE,
        customer_id INTEGER NOT NULL,
        vehicle_id INTEGER NOT NULL,
        slot_id INTEGER NOT NULL,
        start_time TIMESTAMP NOT NULL,
        end_time TIMESTAMP NOT NULL,
        duration_hours REAL NOT NULL,
        hourly_rate REAL NOT NULL,
        estimated_amount REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'reserved',
        notes TEXT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id),
        FOREIGN KEY (vehicle_id) REFERENCES vehicles(id),
        FOREIGN KEY (slot_id) REFERENCES parking_slots(id)
    );

    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        payment_code TEXT NOT NULL UNIQUE,
        reservation_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        payment_method TEXT NOT NULL DEFAULT 'demo_gateway',
        transaction_ref TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL DEFAULT 'pending',
        payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        notes TEXT NULL,
        FOREIGN KEY (reservation_id) REFERENCES reservations(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS parking_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reservation_id INTEGER NOT NULL,
        slot_id INTEGER NOT NULL,
        vehicle_plate TEXT NOT NULL,
        check_in_time TIMESTAMP NOT NULL,
        check_out_time TIMESTAMP NULL,
        actual_duration_hours REAL NULL,
        final_amount REAL NULL,
        status TEXT NOT NULL DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (reservation_id) REFERENCES reservations(id),
        FOREIGN KEY (slot_id) REFERENCES parking_slots(id)
    );

    CREATE TABLE IF NOT EXISTS occupancy_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slot_id INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        notes TEXT NULL,
        FOREIGN KEY (slot_id) REFERENCES parking_slots(id) ON DELETE CASCADE
    );
    """)
    conn.commit()

    # Check if admins exist; if not, seed data
    cur.execute("SELECT COUNT(*) as cnt FROM admins;")
    row = cur.fetchone()
    if row['cnt'] == 0:
        now = datetime.datetime.now()
        
        # 1. Admin
        cur.execute("""
            INSERT INTO admins (username, email, password_hash, full_name, role)
            VALUES (?, ?, ?, ?, ?)
        """, (
            'admin',
            'admin@smartparking.local',
            'scrypt:32768:8:1$z2xQYYZgk1USECNL$b69d6157b38a4ca04d84722e511aab43b6a7c1265a68f49bff4d7ea1bbfe6236324cd7c94770586ac7a0ec18b8b45505ec5af856bda31623b9a5b975f7585cc5',
            'System Administrator',
            'admin'
        ))


        # 2. Areas
        areas = [
            (1, 'Zone A - Ground Level', 'Ground', 8, 'Closest to main entrance, mixed standard and accessible slots'),
            (2, 'Zone B - 1st Floor', '1st Floor', 6, 'Spacious standard and compact parking with wide ramps'),
            (3, 'Zone C - 2nd Floor', '2nd Floor', 4, 'Long-term parking and economical hourly rates'),
            (4, 'Zone EV - Green Hub', 'Ground', 3, 'Dedicated high-speed electric vehicle charging stations')
        ]
        cur.executemany("""
            INSERT INTO parking_areas (id, area_name, floor_level, total_capacity, description)
            VALUES (?, ?, ?, ?, ?)
        """, areas)

        # 3. Slots
        slots = [
            (1, 'A-101', 1, 'accessible', 4.00, 'available'),
            (2, 'A-102', 1, 'accessible', 4.00, 'available'),
            (3, 'A-103', 1, 'regular', 5.00, 'occupied'),
            (4, 'A-104', 1, 'regular', 5.00, 'reserved'),
            (5, 'A-105', 1, 'compact', 4.50, 'available'),
            (6, 'A-106', 1, 'regular', 5.00, 'available'),
            (7, 'A-107', 1, 'regular', 5.00, 'available'),
            (8, 'A-108', 1, 'regular', 5.00, 'available'),
            (9, 'B-201', 2, 'regular', 4.50, 'available'),
            (10, 'B-202', 2, 'regular', 4.50, 'available'),
            (11, 'B-203', 2, 'compact', 4.00, 'occupied'),
            (12, 'B-204', 2, 'compact', 4.00, 'available'),
            (13, 'B-205', 2, 'regular', 4.50, 'available'),
            (14, 'B-206', 2, 'regular', 4.50, 'available'),
            (15, 'C-301', 3, 'regular', 3.50, 'available'),
            (16, 'C-302', 3, 'compact', 3.00, 'available'),
            (17, 'C-303', 3, 'regular', 3.50, 'available'),
            (18, 'C-304', 3, 'regular', 3.50, 'available'),
            (19, 'EV-01', 4, 'ev_charging', 8.00, 'occupied'),
            (20, 'EV-02', 4, 'ev_charging', 8.00, 'available'),
            (21, 'EV-03', 4, 'ev_charging', 8.00, 'available')
        ]
        cur.executemany("""
            INSERT INTO parking_slots (id, slot_number, area_id, slot_type, hourly_rate, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, slots)

        # 4. Customers
        customers = [
            (1, 'Alex Johnson', 'alex.j@example.com', '+1-555-0192'),
            (2, 'Maria Rodriguez', 'maria.r@example.com', '+1-555-0283'),
            (3, 'David Kim', 'david.k@example.com', '+1-555-0374'),
            (4, 'Sarah Chen', 'sarah.c@example.com', '+1-555-0465')
        ]
        cur.executemany("""
            INSERT INTO customers (id, name, email, phone)
            VALUES (?, ?, ?, ?)
        """, customers)

        # 5. Vehicles
        vehicles = [
            (1, 1, 'CA-8892-TX', 'Sedan', 'Toyota Camry'),
            (2, 2, 'NY-4421-BL', 'SUV', 'Honda CR-V'),
            (3, 3, 'EV-9901-GO', 'Electric', 'Tesla Model 3'),
            (4, 4, 'FL-1289-PK', 'Hatchback', 'Volkswagen Golf')
        ]
        cur.executemany("""
            INSERT INTO vehicles (id, customer_id, plate_number, vehicle_type, vehicle_model)
            VALUES (?, ?, ?, ?, ?)
        """, vehicles)

        # 6. Reservations
        t_minus_2 = (now - datetime.timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
        t_plus_2 = (now + datetime.timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
        t_plus_1 = (now + datetime.timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
        t_plus_4 = (now + datetime.timedelta(hours=4)).strftime('%Y-%m-%d %H:%M:%S')
        t_minus_1 = (now - datetime.timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
        t_minus_3 = (now - datetime.timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
        t_minus_24 = (now - datetime.timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        t_minus_20 = (now - datetime.timedelta(hours=20)).strftime('%Y-%m-%d %H:%M:%S')

        reservations = [
            (1, 'RES-2026-1001', 1, 1, 3, t_minus_2, t_plus_2, 4.0, 5.0, 20.0, 'active', 'Checked in on arrival'),
            (2, 'RES-2026-1002', 2, 2, 4, t_plus_1, t_plus_4, 3.0, 5.0, 15.0, 'reserved', 'Business appointment'),
            (3, 'RES-2026-1003', 4, 4, 11, t_minus_1, t_plus_2, 3.0, 4.0, 12.0, 'active', 'Attending conference'),
            (4, 'RES-2026-1004', 3, 3, 19, t_minus_3, t_plus_1, 4.0, 8.0, 32.0, 'active', 'Fast charge needed'),
            (5, 'RES-2026-1005', 1, 1, 6, t_minus_24, t_minus_20, 4.0, 5.0, 20.0, 'completed', 'Past successful booking')
        ]
        cur.executemany("""
            INSERT INTO reservations (id, reservation_code, customer_id, vehicle_id, slot_id, start_time, end_time, duration_hours, hourly_rate, estimated_amount, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, reservations)

        # 7. Payments
        payments = [
            (1, 'PAY-2026-5001', 1, 20.00, 'Credit Card', 'TXN-DEMO-98231', 'paid', t_minus_2, 'Paid via simulated card checkout'),
            (2, 'PAY-2026-5002', 2, 15.00, 'demo_gateway', 'TXN-DEMO-98232', 'pending', t_minus_1, 'Awaiting counter/online clearance'),
            (3, 'PAY-2026-5003', 3, 12.00, 'UPI / QR', 'TXN-DEMO-98233', 'paid', t_minus_1, 'Paid via mobile demo UPI'),
            (4, 'PAY-2026-5004', 4, 32.00, 'Credit Card', 'TXN-DEMO-98234', 'paid', t_minus_3, 'EV charging prepay'),
            (5, 'PAY-2026-5005', 5, 20.00, 'Cash', 'TXN-DEMO-98235', 'paid', t_minus_24, 'Over-the-counter cash receipt')
        ]
        cur.executemany("""
            INSERT INTO payments (id, payment_code, reservation_id, amount, payment_method, transaction_ref, status, payment_date, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, payments)

        # 8. Sessions
        sessions = [
            (1, 1, 3, 'CA-8892-TX', t_minus_2, None, None, None, 'active'),
            (2, 3, 11, 'FL-1289-PK', t_minus_1, None, None, None, 'active'),
            (3, 4, 19, 'EV-9901-GO', t_minus_3, None, None, None, 'active'),
            (4, 5, 6, 'CA-8892-TX', t_minus_24, t_minus_20, 4.0, 20.0, 'completed')
        ]
        cur.executemany("""
            INSERT INTO parking_sessions (id, reservation_id, slot_id, vehicle_plate, check_in_time, check_out_time, actual_duration_hours, final_amount, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, sessions)

        # 9. Logs
        logs = [
            (3, 'check_in', t_minus_2, 'Vehicle CA-8892-TX checked in for RES-2026-1001'),
            (11, 'check_in', t_minus_1, 'Vehicle FL-1289-PK checked in for RES-2026-1003'),
            (19, 'check_in', t_minus_3, 'Vehicle EV-9901-GO checked in for RES-2026-1004'),
            (6, 'check_in', t_minus_24, 'Vehicle CA-8892-TX checked in for RES-2026-1005'),
            (6, 'check_out', t_minus_20, 'Vehicle CA-8892-TX checked out, slot released')
        ]
        cur.executemany("""
            INSERT INTO occupancy_logs (slot_id, event_type, timestamp, notes)
            VALUES (?, ?, ?, ?)
        """, logs)

        conn.commit()

    conn.close()
    logger.info("SQLite database initialized successfully at %s", Config.SQLITE_PATH)


# Initialize SQLite if running under SQLite engine
try:
    if get_active_engine() == 'sqlite':
        init_sqlite_db()
except Exception as e:
    print(f"DB init skipped: {e}")

