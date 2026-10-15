# Smart Parking Management System

A complete, production-grade, full-stack **Smart Parking Management System** built with **Python Flask**, **MySQL** (with automated zero-config fallback), **Bootstrap 5**, and **Chart.js**.

Designed for commercial facility administrators to manage parking spaces, reservations, simulated payments, live occupancy, and customer vehicle records with real-time updates.

---

## Table of Contents
1. [Key Features](#key-features)
2. [Technology Stack](#technology-stack)
3. [System Architecture & Directory Structure](#system-architecture--directory-structure)
4. [Step-by-Step Installation Guide (Windows)](#step-by-step-installation-guide-windows)
5. [Database Setup (MySQL Workbench & Native Engine)](#database-setup-mysql-workbench--native-engine)
6. [Administrator Account Management](#administrator-account-management)
7. [Running the Application](#running-the-application)
8. [Automated Testing Suite](#automated-testing-suite)
9. [User Workflow Guide](#user-workflow-guide)
10. [Troubleshooting & FAQ](#troubleshooting--faq)
11. [Known Limitations & Future Roadmap](#known-limitations--future-roadmap)

---

## 1. Key Features

- **Executive Analytics Dashboard**:
  - Live metric cards: Total Spaces, Available, Reserved, Occupied, Occupancy %, Total Bookings, Revenue Collected, and Pending Charges.
  - Interactive **Chart.js** visualizations: Facility Occupancy Doughnut, 7-Day Reservations Trend, and 7-Day Revenue Trend.
  - Auto-refreshing asynchronous telemetry (`/api/dashboard/stats`).
- **Parking Space Management**:
  - Visual parking slot cards with color states:
    - 🟢 **Available** (`#10b981`)
    - 🟠 **Reserved** (`#f59e0b`)
    - 🔴 **Occupied** (`#ef4444`)
    - ⚪ **Maintenance** (`#64748b`)
  - Search by slot number, filter by zone/floor, slot category (Regular, Compact, Accessible, EV Charging), and status.
  - Deletion safeguard: slots with active bookings or parked vehicles cannot be deleted.
  - Duplicate slot number prevention per zone.
- **Reservation Engine & Double-Booking Prevention**:
  - Overlap prevention algorithm: strictly blocks overlapping bookings for the same parking slot during any shared time window (`start_A < end_B AND end_A > start_B`).
  - Real-time fee estimator: calculates duration (minimum 1 hr) and estimated charge live as users change times or slot selections.
  - Validation: rejects past start times and invalid end times (`end_time <= start_time`).
  - One-click cancellation with automatic slot release.
  - Export reservation history to CSV.
- **Simulated Payment Gateway**:
  - Demo payment sandbox: simulate card payments, UPI QR codes, or cash receipts.
  - Test both Approved and Declined authorization flows.
  - Duplicate payment prevention on already settled charges.
  - Generates unique transaction references (`TXN-DEMO-YYYYMMDD...`).
  - Printable official payment receipts formatted for browser printing or saving as PDF.
  - Export payment transactions to CSV.
- **Live Occupancy & Gate Operations**:
  - Vehicle check-in: verifies booking eligibility, records check-in timestamp, marks slot occupied, and logs gate entry.
  - Vehicle check-out: calculates actual parking duration, records completion, releases slot back to available, and updates facility occupancy.
  - Live facility floor map with status indicators.
- **Customer & Vehicle Management**:
  - Customer directory with linked vehicle license plates, booking counts, and total revenue.
  - Comprehensive customer detail view with complete booking and payment histories.
- **Security & Authentication**:
  - Secure admin login with password hashing via `werkzeug.security` (PBKDF2/scrypt).
  - Protected administrative routes.
  - Environment variable isolation via `.env`.
  - Clean error handlers (404, 500) that never leak database credentials or stack traces.

---

## 2. Technology Stack

- **Backend**: Python 3.10+ with Flask 3.x
- **Database**: MySQL 8.0+ via `mysql-connector-python`
- **Fallback Engine**: Automatic local SQLite fallback (`smart_parking.db`) for instant testing when MySQL is offline
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla ES6)
- **UI Framework**: Bootstrap 5.3
- **Icons**: Bootstrap Icons
- **Typography**: Google Fonts (*Inter*)
- **Charts**: Chart.js 4.x
- **Configuration**: `python-dotenv`
- **Testing**: Python `unittest` / `pytest`

---

## 3. System Architecture & Directory Structure

```
smart_parking_system/
├── app.py                     # Main application factory and server entrypoint
├── config.py                  # Configuration loader (.env integration)
├── database.py                # Dual-engine DB layer (MySQL + SQLite fallback)
├── init_admin.py              # CLI tool to create/update admin accounts securely
├── requirements.txt           # Python dependencies
├── schema.sql                 # MySQL 8.0+ schema with tables, constraints, & seeds
├── .env.example               # Template environment configuration file
├── .env                       # Local active environment configuration
├── .gitignore                 # Git ignore rules
├── README.md                  # Comprehensive documentation
├── routes/
│   ├── auth.py                # Admin login, logout, and session security
│   ├── dashboard.py           # Dashboard metrics, charts API, and summaries
│   ├── parking.py             # Parking slot CRUD and visual grid views
│   ├── reservations.py        # Booking engine, fee estimation, and cancellation
│   ├── payments.py            # Simulated gateway, receipts, and revenue ledger
│   ├── occupancy.py           # Check-in, check-out, and live occupancy map
│   └── customers.py           # Customer profiles and vehicle records
├── services/
│   ├── reservation_service.py # Core overlap prevention & pricing logic
│   ├── payment_service.py     # Demo gateway processing & revenue aggregates
│   ├── occupancy_service.py   # Check-in/out state transitions & log audit
│   ├── parking_service.py     # Slot validation & area operations
│   └── customer_service.py    # Customer search & aggregation queries
├── templates/
│   ├── base.html              # Dark navy sidebar layout shell
│   ├── login.html             # Split login card with quick-fill demo pill
│   ├── dashboard.html         # Operational dashboard with 3 Chart.js graphs
│   ├── parking_slots.html     # Visual slot cards with filters & add/edit modals
│   ├── reservations.html      # Reservation ledger with status badges & export
│   ├── reservation_form.html  # Live dynamic booking form with price estimator
│   ├── reservation_details.html# Single booking details with payment & check-in
│   ├── payments.html          # Transaction ledger & simulated gateway modal
│   ├── receipt.html           # Printable formal customer invoice/receipt
│   ├── occupancy.html         # Live occupancy map, active cars, & gate logs
│   ├── customers.html         # Customer directory & vehicle associations
│   ├── customer_details.html  # Detailed customer history inspection
│   └── error.html             # User-friendly error page (404, 500)
├── static/
│   ├── css/
│   │   └── style.css          # Modern dark navy & clean cards design system
│   └── js/
│       ├── dashboard.js       # Chart.js graphs & real-time telemetry polling
│       └── parking.js         # Interactive fee calculator & modal handlers
└── tests/
    ├── test_reservations.py   # Unit tests: slots, fees, overlaps, check-in/out
    ├── test_payments.py       # Unit tests: demo gateway, duplicate prevention
    └── test_e2e_routes.py     # End-to-end integration tests for all HTTP routes
```

---

## 4. Step-by-Step Installation Guide (Windows)

Follow these steps in **PowerShell** or **Command Prompt**:

### Step 1: Install Python
Ensure Python 3.10+ is installed. During installation, make sure to check the box:
> **☑ Add python.exe to PATH**

Verify in PowerShell:
```powershell
python --version
pip --version
```

### Step 2: Navigate to Project Directory
```powershell
cd "c:\Users\madha\Downloads\Intelligent Parking Management"
```

### Step 3: Create & Activate Virtual Environment
```powershell
# Create virtual environment
python -m venv venv

# Activate on Windows PowerShell
.\venv\Scripts\Activate.ps1

# (If PowerShell displays an ExecutionPolicy error, run once:
#  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser)
```

### Step 4: Install Dependencies
```powershell
pip install -r requirements.txt
```

---

## 5. Database Setup (MySQL Workbench & Native Engine)

### Option A: Using MySQL Server & MySQL Workbench (Recommended for Production / Lab Submission)

1. Open **MySQL Workbench**.
2. Connect to your local MySQL instance (usually `localhost:3306`, user: `root`).
3. Click **File** &rarr; **Open SQL Script...** and choose `schema.sql` located in this project folder.
4. Click the ⚡ **Execute** (lightning bolt) icon to run the script.
   - This creates database `smart_parking_db`, all 9 tables, indexes, foreign keys, and seeds sample data.
5. In your `.env` file, configure your MySQL credentials:
   ```ini
   DB_ENGINE=mysql
   DB_HOST=localhost
   DB_PORT=3306
   DB_USER=root
   DB_PASSWORD=your_mysql_password_here
   DB_NAME=smart_parking_db
   ```

### Option B: Automatic Zero-Config Fallback (Out-of-the-Box)

If MySQL Server is not currently installed or running on your computer, the application's intelligent `database.py` layer will automatically detect that MySQL on port 3306 is unreachable and switch to local SQLite engine (`smart_parking.db`) with identical schema, tables, and seed data.
You can immediately launch and test all features without installing MySQL!

---

## 6. Administrator Account Management

### Default Administrator Credentials:
- **Username**: `admin`
- **Password**: `Admin@12345`

### Create or Reset an Admin Account:
Use the included secure setup script:
```powershell
.\venv\Scripts\python init_admin.py admin admin@smartparking.local Admin@12345 "System Administrator"
```
You can also run it interactively without arguments to be prompted:
```powershell
.\venv\Scripts\python init_admin.py
```

---

## 7. Running the Application

Start the Flask development server:
```powershell
.\venv\Scripts\python app.py
```

Output:
```
============================================================
SMART PARKING MANAGEMENT SYSTEM
Server starting on http://127.0.0.1:5000
Admin Default Login: admin / Admin@12345
============================================================
 * Running on http://127.0.0.1:5000
```

Open your browser and navigate to:
**[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 8. Automated Testing Suite

The repository contains 20 comprehensive unit and integration tests covering all critical requirements.

Run all tests:
```powershell
.\venv\Scripts\python -m unittest discover -s tests -p "test_*.py" -v
```

### Test Coverage Highlights:
- `test_reservations.py`:
  - Parking slot creation & duplicate slot prevention.
  - Fee calculation accuracy (hourly rate & duration).
  - Rejection of invalid end times (`end <= start`).
  - Rejection of past start times.
  - Strict rejection of overlapping bookings for the same parking slot.
  - Vehicle check-in (marks slot occupied, logs session).
  - Vehicle check-out (calculates actual duration, releases slot).
  - Admin route protection (redirects unauthenticated users to `/login`).
- `test_payments.py`:
  - Simulated demo gateway payment processing.
  - Rejection of duplicate payment on already settled reservations.
  - Simulated gateway decline recording.
  - Revenue summary aggregation.
- `test_e2e_routes.py`:
  - Complete end-to-end HTTP route tests, JSON API endpoints, and CSV exports.

---

## 9. User Workflow Guide

1. **Sign In**:
   - Visit `http://127.0.0.1:5000`. You are redirected to `/login`.
   - Click the **Quick Demo Admin** pill to autofill `admin` / `Admin@12345`, then click **Sign In**.
2. **Operations Dashboard**:
   - Inspect live cards for total slots, available slots, reserved, and occupied.
   - Review the **Occupancy Distribution Doughnut**, **7-Day Bookings Trend**, and **7-Day Revenue Trend**.
   - Click **Sync Live** to fetch real-time database telemetry without reloading the page.
3. **Manage Parking Spaces**:
   - Click **Parking Spaces** in the dark navy sidebar.
   - Filter slots by Floor/Zone, Type (EV Charging, Accessible, Compact, Regular), or Status.
   - Click **Add New Slot** to define a new parking space with a custom hourly rate.
   - Click the three dots on any slot card to **Edit Slot** or **Book Slot**.
4. **Make a Reservation**:
   - Click **Quick Booking** or navigate to **Reservations** &rarr; **New Reservation**.
   - Fill in Customer Name and Vehicle License Plate (e.g. `CA-8892-TX`).
   - Pick Start and End dates/times.
   - Click **Filter Available Slots** to see only slots free during that exact window.
   - Notice the **Price Breakdown** card dynamically updates duration and total fee in real time!
   - Click **Confirm & Book Slot**.
5. **Process Simulated Demo Payment**:
   - Navigate to **Payment Gateway**.
   - For any booking with status `Pending`, click **Pay**.
   - In the modal, pick your channel (Credit Card Demo, UPI QR Demo, Cash) and outcome (Approved or Declined), then click **Process Payment**.
   - The status updates to `Paid` with a unique transaction reference (e.g., `TXN-DEMO-20261015...`).
   - Click **Receipt** to inspect the printable invoice and click **Print / Save as PDF**.
6. **Vehicle Check-In & Check-Out**:
   - Navigate to **Live Occupancy**.
   - Under **Currently Parked Vehicles**, click **Check-Out** to release a parked car.
   - To check in an arriving booking, click **Vehicle Check-In**, select the reservation, and authorize gate entry.
7. **Customer Directory**:
   - Navigate to **Customers** to view registered drivers, associated vehicle plates, total bookings, and lifetime spend. Click **Profile** to view individual history.

---

## 10. Troubleshooting & FAQ

### Issue: "mysql : The term 'mysql' is not recognized"
- **Solution**: MySQL command-line tool is not added to your Windows PATH. This does NOT affect the Flask app! The app connects directly via `mysql-connector-python` or uses the built-in SQLite fallback. You can run `schema.sql` directly inside **MySQL Workbench**.

### Issue: "Access denied for user 'root'@'localhost'"
- **Solution**: Open `.env` and verify your `DB_PASSWORD`. If your MySQL root account has no password, leave `DB_PASSWORD=` empty. If it has a password, enter it in `.env`.

### Issue: "Port 5000 is already in use"
- **Solution**: Change the port in `.env`:
  ```ini
  PORT=5001
  ```
  Then restart with `python app.py`.

### Issue: "Charmap codec can't encode character" on Windows PowerShell
- **Solution**: The application uses clean ASCII console logging for 100% compatibility with Windows `cp1252` encoding.

---

## 11. Known Limitations & Recommended Future Improvements

### Current Limitations:
1. **Simulated Payment Gateway**: Real monetary charges are intentionally not executed. A simulated sandbox gateway is implemented to fulfill academic/demo requirements safely without requiring merchant accounts or storing credit cards.
2. **Occupancy Sensors**: Check-in and check-out are triggered through the web admin portal or API. Physical hardware sensors (ultrasonic/RFID/ANPR cameras) are simulated digitally.

### Recommended Future Roadmap:
- **Stripe / PayPal Gateway Integration**: Replace demo modal with real Stripe Elements webhook integration for production deployment.
- **ANPR (Automatic Number Plate Recognition)**: Integrate OpenCV or YOLOv8 camera feed at the gate to automatically read vehicle license plates and trigger check-in/out.
- **Customer Self-Service Portal**: Provide a public customer-facing mobile web view where drivers can view real-time available slots and book directly from their smartphones.
- **IoT Hardware Integration**: Connect ESP32 / Arduino ultrasonic sensors to publish live slot occupancy via MQTT to the Flask backend.

---

## License
MIT License. Created for Smart Parking Facility Management.
