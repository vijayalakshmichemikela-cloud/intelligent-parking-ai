"""
End-to-End Route & Flow Integration Tests
Tests all endpoints, HTML responses, JSON APIs, and complete user workflows.
"""

import os
import sys
import unittest
import json
import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from database import query_db

class TestE2EFlows(unittest.TestCase):

    def setUp(self):
        """Set up test client with cookie jar."""
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def login_admin(self):
        """Helper to log in as administrator using session transaction."""
        with self.client.session_transaction() as sess:
            sess['admin_id'] = 1
            sess['admin_username'] = 'admin'
            sess['admin_name'] = 'System Administrator'
            sess['admin_role'] = 'admin'


    def test_01_login_flow(self):
        """Test login GET and POST authentication."""
        res_get = self.client.get('/login')
        self.assertEqual(res_get.status_code, 200)
        self.assertIn(b'Smart Parking Portal', res_get.data)

        # Bad password
        res_bad = self.client.post('/login', data={'username': 'admin', 'password': 'WrongPassword'})
        self.assertEqual(res_bad.status_code, 200)
        self.assertIn(b'Invalid username or password', res_bad.data)

        # Good password
        res_good = self.client.post('/login', data={'username': 'admin', 'password': 'Admin@12345'}, follow_redirects=True)
        self.assertEqual(res_good.status_code, 200)
        self.assertIn(b'Facility Operations Dashboard', res_good.data)


    def test_02_dashboard_apis(self):
        """Test dashboard JSON APIs for stats and charts."""
        self.login_admin()
        
        # Stats API
        res_stats = self.client.get('/api/dashboard/stats')
        self.assertEqual(res_stats.status_code, 200)
        data = json.loads(res_stats.data)
        self.assertIn('total_spaces', data)
        self.assertIn('occupancy_percentage', data)
        self.assertIn('total_revenue', data)

        # Charts API
        res_charts = self.client.get('/api/dashboard/charts')
        self.assertEqual(res_charts.status_code, 200)
        chart_data = json.loads(res_charts.data)
        self.assertIn('doughnut', chart_data)
        self.assertIn('trends', chart_data)
        self.assertEqual(len(chart_data['doughnut']['labels']), 4)

    def test_03_parking_slots_endpoints(self):
        """Test parking slots management page and add slot."""
        self.login_admin()
        res = self.client.get('/parking-slots')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Parking Space Management', res.data)

        # Add slot via POST
        slot_num = f"E2E-{int(datetime.datetime.now().timestamp()) % 1000}"
        res_add = self.client.post('/parking-slots/add', data={
            'slot_number': slot_num,
            'area_id': 1,
            'slot_type': 'compact',
            'hourly_rate': '4.50',
            'status': 'available'
        }, follow_redirects=True)
        self.assertEqual(res_add.status_code, 200)
        self.assertIn(slot_num.encode(), res_add.data)

    def test_04_reservation_booking_flow(self):
        """Test reservation form, live estimate API, and creation."""
        self.login_admin()
        res_form = self.client.get('/reservations/new')
        self.assertEqual(res_form.status_code, 200)
        self.assertIn(b'Create New Parking Reservation', res_form.data)

        now = datetime.datetime.now()
        unique_plate = f"E2E-{int(now.timestamp()) % 100000}"
        offset_hrs = 400 + (int(now.timestamp()) % 1000)
        start = (now + datetime.timedelta(hours=offset_hrs)).strftime('%Y-%m-%dT%H:%M')
        end = (now + datetime.timedelta(hours=offset_hrs + 4)).strftime('%Y-%m-%dT%H:%M')

        # Live estimate API
        res_est = self.client.post('/api/reservations/estimate-fee', 
            data=json.dumps({
                'slot_id': 1,
                'start_time': start,
                'end_time': end
            }),
            content_type='application/json'
        )
        self.assertEqual(res_est.status_code, 200)
        est_data = json.loads(res_est.data)
        self.assertEqual(est_data['duration_hours'], 4.0)
        self.assertEqual(est_data['estimated_amount'], 16.0)

        # Create reservation
        res_create = self.client.post('/reservations/create', data={
            'customer_name': 'E2E Customer',
            'customer_phone': '+1 555-8888',
            'customer_email': 'e2e@example.com',
            'vehicle_plate': unique_plate,
            'vehicle_type': 'Sedan',
            'vehicle_model': 'Tesla',
            'slot_id': 1,
            'start_time': start,
            'end_time': end,
            'notes': 'E2E automated flow test'
        }, follow_redirects=True)
        self.assertEqual(res_create.status_code, 200)
        self.assertIn(unique_plate.encode(), res_create.data)


    def test_05_payment_demo_and_receipt(self):
        """Test simulated demo payment and printable receipt page."""
        self.login_admin()
        res_pay = self.client.get('/payments')
        self.assertEqual(res_pay.status_code, 200)
        self.assertIn(b'Payment Management', res_pay.data)

        # Receipt view for payment 1
        res_rec = self.client.get('/payments/1/receipt')
        self.assertEqual(res_rec.status_code, 200)
        self.assertIn(b'SmartPark System', res_rec.data)
        self.assertIn(b'Total Paid:', res_rec.data)

    def test_06_occupancy_endpoints(self):
        """Test occupancy monitoring page and live API."""
        self.login_admin()
        res_occ = self.client.get('/occupancy')
        self.assertEqual(res_occ.status_code, 200)
        self.assertIn(b'Live Occupancy & Vehicle Check-In', res_occ.data)

        res_live = self.client.get('/api/occupancy/live')
        self.assertEqual(res_live.status_code, 200)
        live_data = json.loads(res_live.data)
        self.assertIn('overview', live_data)
        self.assertIn('slots', live_data)

    def test_07_customers_endpoints(self):
        """Test customer directory and details."""
        self.login_admin()
        res_cust = self.client.get('/customers')
        self.assertEqual(res_cust.status_code, 200)
        self.assertIn(b'Customer & Vehicle Management', res_cust.data)

        res_detail = self.client.get('/customers/1')
        self.assertEqual(res_detail.status_code, 200)
        self.assertIn(b'Alex Johnson', res_detail.data)

    def test_08_csv_exports(self):
        """Test CSV export downloads."""
        self.login_admin()
        res_res_csv = self.client.get('/reservations/export/csv')
        self.assertEqual(res_res_csv.status_code, 200)
        self.assertIn('text/csv', res_res_csv.headers['Content-Type'])
        self.assertIn(b'Reservation Code,Customer Name', res_res_csv.data)

        res_pay_csv = self.client.get('/payments/export/csv')
        self.assertEqual(res_pay_csv.status_code, 200)
        self.assertIn('text/csv', res_pay_csv.headers['Content-Type'])
        self.assertIn(b'Payment Code,Reservation Code', res_pay_csv.data)

if __name__ == '__main__':
    unittest.main()
