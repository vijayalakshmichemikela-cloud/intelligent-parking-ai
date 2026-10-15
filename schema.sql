-- ====================================================================
-- Smart Parking Management System - MySQL Database Schema
-- Compatible with MySQL 8.0+ and MySQL Workbench
-- Timezone Standard: UTC / Local Server Time (Documented in README)
-- ====================================================================

CREATE DATABASE IF NOT EXISTS smart_parking_db 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE smart_parking_db;

-- --------------------------------------------------------------------
-- 1. Admins Table
-- --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'admin',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME NULL,
    INDEX idx_admin_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------------------
-- 2. Parking Areas Table
-- --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS parking_areas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    area_name VARCHAR(100) NOT NULL UNIQUE,
    floor_level VARCHAR(20) NOT NULL,
    total_capacity INT NOT NULL DEFAULT 0,
    description VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_area_floor (floor_level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------------------
-- 3. Parking Slots Table
-- --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS parking_slots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    slot_number VARCHAR(20) NOT NULL,
    area_id INT NOT NULL,
    slot_type ENUM('regular', 'compact', 'accessible', 'ev_charging') NOT NULL DEFAULT 'regular',
    hourly_rate DECIMAL(10, 2) NOT NULL DEFAULT 5.00,
    status ENUM('available', 'reserved', 'occupied', 'maintenance') NOT NULL DEFAULT 'available',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uk_slot_area UNIQUE (slot_number, area_id),
    CONSTRAINT fk_slots_area FOREIGN KEY (area_id) 
        REFERENCES parking_areas(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    INDEX idx_slot_status (status),
    INDEX idx_slot_type (slot_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------------------
-- 4. Customers Table
-- --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS customers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NULL,
    phone VARCHAR(25) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_customer_name (name),
    INDEX idx_customer_phone (phone)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------------------
-- 5. Vehicles Table
-- --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vehicles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    plate_number VARCHAR(20) NOT NULL UNIQUE,
    vehicle_type VARCHAR(30) NOT NULL DEFAULT 'Sedan',
    vehicle_model VARCHAR(50) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_vehicles_customer FOREIGN KEY (customer_id) 
        REFERENCES customers(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_plate_number (plate_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------------------
-- 6. Reservations Table
-- --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reservations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    reservation_code VARCHAR(30) NOT NULL UNIQUE,
    customer_id INT NOT NULL,
    vehicle_id INT NOT NULL,
    slot_id INT NOT NULL,
    start_time DATETIME NOT NULL,
    end_time DATETIME NOT NULL,
    duration_hours DECIMAL(6, 2) NOT NULL,
    hourly_rate DECIMAL(10, 2) NOT NULL,
    estimated_amount DECIMAL(10, 2) NOT NULL,
    status ENUM('pending', 'reserved', 'active', 'completed', 'cancelled') NOT NULL DEFAULT 'reserved',
    notes TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_res_customer FOREIGN KEY (customer_id) 
        REFERENCES customers(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_res_vehicle FOREIGN KEY (vehicle_id) 
        REFERENCES vehicles(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_res_slot FOREIGN KEY (slot_id) 
        REFERENCES parking_slots(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    INDEX idx_res_status (status),
    INDEX idx_res_slot_time (slot_id, start_time, end_time, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------------------
-- 7. Payments Table
-- --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS payments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    payment_code VARCHAR(30) NOT NULL UNIQUE,
    reservation_id INT NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    payment_method VARCHAR(50) NOT NULL DEFAULT 'demo_gateway',
    transaction_ref VARCHAR(100) NOT NULL UNIQUE,
    status ENUM('pending', 'paid', 'failed', 'refunded') NOT NULL DEFAULT 'pending',
    payment_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes TEXT NULL,
    CONSTRAINT fk_payments_reservation FOREIGN KEY (reservation_id) 
        REFERENCES reservations(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_payment_status (status),
    INDEX idx_payment_date (payment_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------------------
-- 8. Parking Sessions Table (Check-in / Check-out tracking)
-- --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS parking_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    reservation_id INT NOT NULL,
    slot_id INT NOT NULL,
    vehicle_plate VARCHAR(20) NOT NULL,
    check_in_time DATETIME NOT NULL,
    check_out_time DATETIME NULL,
    actual_duration_hours DECIMAL(6, 2) NULL,
    final_amount DECIMAL(10, 2) NULL,
    status ENUM('active', 'completed') NOT NULL DEFAULT 'active',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_sessions_reservation FOREIGN KEY (reservation_id) 
        REFERENCES reservations(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_sessions_slot FOREIGN KEY (slot_id) 
        REFERENCES parking_slots(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    INDEX idx_session_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------------------
-- 9. Occupancy Logs Table
-- --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS occupancy_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    slot_id INT NOT NULL,
    event_type ENUM('check_in', 'check_out', 'status_change') NOT NULL,
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes VARCHAR(255) NULL,
    CONSTRAINT fk_logs_slot FOREIGN KEY (slot_id) 
        REFERENCES parking_slots(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_log_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ====================================================================
-- Sample Data Seed
-- ====================================================================

-- 1. Default Administrator (Password: Admin@12345)
-- Hash generated using scrypt/pbkdf2 compatible with werkzeug.security
INSERT INTO admins (username, email, password_hash, full_name, role) 
VALUES (
    'admin', 
    'admin@smartparking.local', 
    'scrypt:32768:8:1$z2xQYYZgk1USECNL$b69d6157b38a4ca04d84722e511aab43b6a7c1265a68f49bff4d7ea1bbfe6236324cd7c94770586ac7a0ec18b8b45505ec5af856bda31623b9a5b975f7585cc5',
    'System Administrator', 
    'admin'
) ON DUPLICATE KEY UPDATE id=id;


-- 2. Parking Areas
INSERT INTO parking_areas (id, area_name, floor_level, total_capacity, description) VALUES
(1, 'Zone A - Ground Level', 'Ground', 10, 'Closest to main entrance, mixed standard and accessible slots'),
(2, 'Zone B - 1st Floor', '1st Floor', 12, 'Spacious standard and compact parking with wide ramps'),
(3, 'Zone C - 2nd Floor', '2nd Floor', 10, 'Long-term parking and economical hourly rates'),
(4, 'Zone EV - Green Hub', 'Ground', 6, 'Dedicated high-speed electric vehicle charging stations')
ON DUPLICATE KEY UPDATE id=id;

-- 3. Parking Slots
INSERT INTO parking_slots (id, slot_number, area_id, slot_type, hourly_rate, status) VALUES
-- Zone A (Ground)
(1, 'A-101', 1, 'accessible', 4.00, 'available'),
(2, 'A-102', 1, 'accessible', 4.00, 'available'),
(3, 'A-103', 1, 'regular', 5.00, 'occupied'),
(4, 'A-104', 1, 'regular', 5.00, 'reserved'),
(5, 'A-105', 1, 'compact', 4.50, 'available'),
(6, 'A-106', 1, 'regular', 5.00, 'available'),
(7, 'A-107', 1, 'regular', 5.00, 'available'),
(8, 'A-108', 1, 'regular', 5.00, 'available'),
-- Zone B (1st Floor)
(9,  'B-201', 2, 'regular', 4.50, 'available'),
(10, 'B-202', 2, 'regular', 4.50, 'available'),
(11, 'B-203', 2, 'compact', 4.00, 'occupied'),
(12, 'B-204', 2, 'compact', 4.00, 'available'),
(13, 'B-205', 2, 'regular', 4.50, 'available'),
(14, 'B-206', 2, 'regular', 4.50, 'available'),
-- Zone C (2nd Floor)
(15, 'C-301', 3, 'regular', 3.50, 'available'),
(16, 'C-302', 3, 'compact', 3.00, 'available'),
(17, 'C-303', 3, 'regular', 3.50, 'available'),
(18, 'C-304', 3, 'regular', 3.50, 'available'),
-- Zone EV (Green Hub)
(19, 'EV-01', 4, 'ev_charging', 8.00, 'occupied'),
(20, 'EV-02', 4, 'ev_charging', 8.00, 'available'),
(21, 'EV-03', 4, 'ev_charging', 8.00, 'available')
ON DUPLICATE KEY UPDATE id=id;

-- 4. Sample Customers
INSERT INTO customers (id, name, email, phone) VALUES
(1, 'Alex Johnson', 'alex.j@example.com', '+1-555-0192'),
(2, 'Maria Rodriguez', 'maria.r@example.com', '+1-555-0283'),
(3, 'David Kim', 'david.k@example.com', '+1-555-0374'),
(4, 'Sarah Chen', 'sarah.c@example.com', '+1-555-0465')
ON DUPLICATE KEY UPDATE id=id;

-- 5. Sample Vehicles
INSERT INTO vehicles (id, customer_id, plate_number, vehicle_type, vehicle_model) VALUES
(1, 1, 'CA-8892-TX', 'Sedan', 'Toyota Camry'),
(2, 2, 'NY-4421-BL', 'SUV', 'Honda CR-V'),
(3, 3, 'EV-9901-GO', 'Electric', 'Tesla Model 3'),
(4, 4, 'FL-1289-PK', 'Hatchback', 'Volkswagen Golf')
ON DUPLICATE KEY UPDATE id=id;

-- 6. Sample Reservations
-- A-103 is Active (Checked-in)
INSERT INTO reservations (id, reservation_code, customer_id, vehicle_id, slot_id, start_time, end_time, duration_hours, hourly_rate, estimated_amount, status, notes) VALUES
(1, 'RES-2026-1001', 1, 1, 3, NOW() - INTERVAL 2 HOUR, NOW() + INTERVAL 2 HOUR, 4.00, 5.00, 20.00, 'active', 'Checked in on arrival'),
-- A-104 is Reserved for upcoming slot
(2, 'RES-2026-1002', 2, 2, 4, NOW() + INTERVAL 1 HOUR, NOW() + INTERVAL 4 HOUR, 3.00, 5.00, 15.00, 'reserved', 'Business appointment'),
-- B-203 is Active
(3, 'RES-2026-1003', 4, 4, 11, NOW() - INTERVAL 1 HOUR, NOW() + INTERVAL 2 HOUR, 3.00, 4.00, 12.00, 'active', 'Attending conference'),
-- EV-01 is Active (EV charging session)
(4, 'RES-2026-1004', 3, 3, 19, NOW() - INTERVAL 3 HOUR, NOW() + INTERVAL 1 HOUR, 4.00, 8.00, 32.00, 'active', 'Fast charge needed'),
-- Completed past reservation
(5, 'RES-2026-1005', 1, 1, 6, NOW() - INTERVAL 1 DAY, NOW() - INTERVAL 20 HOUR, 4.00, 5.00, 20.00, 'completed', 'Past successful booking')
ON DUPLICATE KEY UPDATE id=id;

-- 7. Sample Payments
INSERT INTO payments (id, payment_code, reservation_id, amount, payment_method, transaction_ref, status, payment_date, notes) VALUES
(1, 'PAY-2026-5001', 1, 20.00, 'Credit Card', 'TXN-DEMO-98231', 'paid', NOW() - INTERVAL 2 HOUR, 'Paid via simulated card checkout'),
(2, 'PAY-2026-5002', 2, 15.00, 'demo_gateway', 'TXN-DEMO-98232', 'pending', NOW() - INTERVAL 30 MINUTE, 'Awaiting counter/online clearance'),
(3, 'PAY-2026-5003', 3, 12.00, 'UPI / QR', 'TXN-DEMO-98233', 'paid', NOW() - INTERVAL 1 HOUR, 'Paid via mobile demo UPI'),
(4, 'PAY-2026-5004', 4, 32.00, 'Credit Card', 'TXN-DEMO-98234', 'paid', NOW() - INTERVAL 3 HOUR, 'EV charging prepay'),
(5, 'PAY-2026-5005', 5, 20.00, 'Cash', 'TXN-DEMO-98235', 'paid', NOW() - INTERVAL 1 DAY, 'Over-the-counter cash receipt')
ON DUPLICATE KEY UPDATE id=id;

-- 8. Sample Parking Sessions (For the active reservations)
INSERT INTO parking_sessions (id, reservation_id, slot_id, vehicle_plate, check_in_time, check_out_time, actual_duration_hours, final_amount, status) VALUES
(1, 1, 3, 'CA-8892-TX', NOW() - INTERVAL 2 HOUR, NULL, NULL, NULL, 'active'),
(2, 3, 11, 'FL-1289-PK', NOW() - INTERVAL 1 HOUR, NULL, NULL, NULL, 'active'),
(3, 4, 19, 'EV-9901-GO', NOW() - INTERVAL 3 HOUR, NULL, NULL, NULL, 'active'),
(4, 5, 6, 'CA-8892-TX', NOW() - INTERVAL 1 DAY, NOW() - INTERVAL 20 HOUR, 4.00, 20.00, 'completed')
ON DUPLICATE KEY UPDATE id=id;

-- 9. Sample Occupancy Logs
INSERT INTO occupancy_logs (slot_id, event_type, timestamp, notes) VALUES
(3, 'check_in', NOW() - INTERVAL 2 HOUR, 'Vehicle CA-8892-TX checked in for RES-2026-1001'),
(11, 'check_in', NOW() - INTERVAL 1 HOUR, 'Vehicle FL-1289-PK checked in for RES-2026-1003'),
(19, 'check_in', NOW() - INTERVAL 3 HOUR, 'Vehicle EV-9901-GO checked in for RES-2026-1004'),
(6, 'check_in', NOW() - INTERVAL 1 DAY, 'Vehicle CA-8892-TX checked in for RES-2026-1005'),
(6, 'check_out', NOW() - INTERVAL 20 HOUR, 'Vehicle CA-8892-TX checked out, slot released')
ON DUPLICATE KEY UPDATE id=id;
