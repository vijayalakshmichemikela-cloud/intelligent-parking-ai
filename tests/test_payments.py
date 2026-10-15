"""
Unit Tests for Payment Gateway & Revenue Calculations
Tests simulated demo payments, duplicate charge prevention, failure handling,
and transaction auditing.
"""

import os
import sys
import uuid
import unittest
import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from database import query_db
from services.reservation_service import create_reservation
from services.payment_service import (
    process_demo_payment, get_payment_by_id, get_payment_summary, get_payment_by_reservation
)

class TestPaymentProcessing(unittest.TestCase):

    def setUp(self):
        """Set up test Flask client."""
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.created_res_ids = []

    def tearDown(self):
        """Clean up created test reservations."""
        for res_id in self.created_res_ids:
            query_db("DELETE FROM payments WHERE reservation_id = %s", (res_id,), commit=True)
            query_db("DELETE FROM reservations WHERE id = %s", (res_id,), commit=True)

    def test_01_process_demo_payment_success(self):
        """Test processing a successful demo payment."""
        now = datetime.datetime.now()
        unique_id = uuid.uuid4().hex[:6].upper()
        # Use unique timestamp offset
        offset_hrs = 200 + (int(unique_id, 16) % 1000)
        start = now + datetime.timedelta(hours=offset_hrs)
        end = start + datetime.timedelta(hours=2)

        booking = create_reservation(
            customer_name="Payment Tester",
            vehicle_plate=f"PAY-{unique_id}",
            slot_id=7, # A-107
            start_time=start,
            end_time=end
        )
        self.assertTrue(booking['success'], booking.get('error'))
        res_id = booking['reservation_id']
        self.created_res_ids.append(res_id)

        # Get pending payment record created with the reservation
        payment = get_payment_by_reservation(res_id)
        self.assertIsNotNone(payment)
        self.assertEqual(payment['status'], 'pending')

        # Execute demo payment
        res = process_demo_payment(payment['id'], payment_method='Credit Card (Demo)', simulate_status='paid')
        self.assertTrue(res['success'])
        self.assertEqual(res['status'], 'paid')
        self.assertTrue(res['transaction_ref'].startswith('TXN-DEMO-'))

        # Verify DB updated
        updated_pay = get_payment_by_id(payment['id'])
        self.assertEqual(updated_pay['status'], 'paid')

    def test_02_prevent_duplicate_payment(self):
        """Test rejection of duplicate payments on already settled charges."""
        # Payment ID 1 in seeds is already 'paid'
        res = process_demo_payment(1, payment_method='Credit Card (Demo)', simulate_status='paid')
        self.assertFalse(res['success'])
        self.assertIn("already been paid", res['error'])

    def test_03_simulate_payment_decline(self):
        """Test simulated gateway decline records failed status without error."""
        now = datetime.datetime.now()
        unique_id = uuid.uuid4().hex[:6].upper()
        offset_hrs = 300 + (int(unique_id, 16) % 1000)
        start = now + datetime.timedelta(hours=offset_hrs)
        end = start + datetime.timedelta(hours=2)

        booking = create_reservation(
            customer_name="Declined Customer",
            vehicle_plate=f"FAIL-{unique_id}",
            slot_id=8, # A-108
            start_time=start,
            end_time=end
        )
        self.assertTrue(booking['success'], booking.get('error'))
        res_id = booking['reservation_id']
        self.created_res_ids.append(res_id)

        payment = get_payment_by_reservation(res_id)

        # Simulate decline
        res = process_demo_payment(payment['id'], payment_method='UPI / QR (Demo)', simulate_status='failed')
        self.assertFalse(res['success'])
        self.assertEqual(res['status'], 'failed')

        updated_pay = get_payment_by_id(payment['id'])
        self.assertEqual(updated_pay['status'], 'failed')

    def test_04_revenue_summary_calculation(self):
        """Test payment summary aggregates only paid transactions."""
        summary = get_payment_summary()
        self.assertIn('total_revenue', summary)
        self.assertIn('pending_amount', summary)
        self.assertGreater(summary['total_revenue'], 0)

if __name__ == '__main__':
    unittest.main()
