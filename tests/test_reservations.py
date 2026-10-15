"""
Unit & Integration Tests for Smart Parking Management System
Tests parking slot creation, duplicate prevention, reservation booking,
overlap rejection, check-in, check-out, and cancellation.
"""

import os
import sys
import unittest
import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from database import query_db
from services.parking_service import create_slot, delete_slot
from services.reservation_service import (
    create_reservation, cancel_reservation, calculate_fee, is_slot_available
)
from services.occupancy_service import check_in_vehicle, check_out_vehicle

class TestReservationAndParking(unittest.TestCase):

    def setUp(self):
        """Set up test Flask client."""
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_01_create_parking_slot_success(self):
        """Test successful parking slot creation."""
        slot_number = f"T-TEST-{int(datetime.datetime.now().timestamp()) % 10000}"
        res = create_slot(slot_number=slot_number, area_id=1, slot_type='regular', hourly_rate=6.50)
        self.assertTrue(res['success'])
        self.assertIn('slot_id', res)

    def test_02_prevent_duplicate_slot(self):
        """Test duplicate slot numbers in the same area are rejected."""
        # A-101 already exists in Area 1
        res = create_slot(slot_number='A-101', area_id=1, slot_type='regular', hourly_rate=5.00)
        self.assertFalse(res['success'])
        self.assertIn("already exists", res['error'])

    def test_03_calculate_fee(self):
        """Test correct duration and fee estimation."""
        now = datetime.datetime.now()
        start = now + datetime.timedelta(hours=1)
        end = now + datetime.timedelta(hours=4) # 3 hours
        
        # Slot 1 has rate $4.00/hr
        fee_info = calculate_fee(slot_id=1, start_time=start, end_time=end)
        self.assertEqual(fee_info['duration_hours'], 3.0)
        self.assertEqual(fee_info['hourly_rate'], 4.0)
        self.assertEqual(fee_info['estimated_amount'], 12.0)

    def test_04_reject_invalid_times_end_before_start(self):
        """Test rejection when end_time is earlier than start_time."""
        now = datetime.datetime.now()
        start = now + datetime.timedelta(hours=3)
        end = now + datetime.timedelta(hours=1)

        with self.assertRaises(ValueError):
            calculate_fee(slot_id=1, start_time=start, end_time=end)

        res = create_reservation(
            customer_name="Test Customer",
            vehicle_plate="TEST-PLATE-01",
            slot_id=1,
            start_time=start,
            end_time=end
        )
        self.assertFalse(res['success'])
        self.assertIn("End time must be later", res['error'])

    def test_05_reject_past_start_time(self):
        """Test rejection of reservations with past start times."""
        now = datetime.datetime.now()
        past_start = now - datetime.timedelta(hours=2)
        past_end = now + datetime.timedelta(hours=1)

        res = create_reservation(
            customer_name="Past Customer",
            vehicle_plate="TEST-PLATE-02",
            slot_id=1,
            start_time=past_start,
            end_time=past_end
        )
        self.assertFalse(res['success'])
        self.assertIn("cannot be in the past", res['error'])

    def test_06_create_reservation_and_prevent_overlap(self):
        """Test successful reservation creation and strict prevention of overlapping booking."""
        now = datetime.datetime.now()
        # Choose a slot and future timeframe: +10 hours to +14 hours
        start1 = now + datetime.timedelta(hours=10)
        end1 = now + datetime.timedelta(hours=14)

        # 1. Create first booking
        booking1 = create_reservation(
            customer_name="Alice Smith",
            vehicle_plate="ALICE-999",
            slot_id=2, # A-102
            start_time=start1,
            end_time=end1
        )
        self.assertTrue(booking1['success'], booking1.get('error'))
        res_id1 = booking1['reservation_id']

        # 2. Try overlapping booking (starts at +12 hrs, ends at +16 hrs)
        start2 = now + datetime.timedelta(hours=12)
        end2 = now + datetime.timedelta(hours=16)

        booking2 = create_reservation(
            customer_name="Bob Jones",
            vehicle_plate="BOB-888",
            slot_id=2,
            start_time=start2,
            end_time=end2
        )
        self.assertFalse(booking2['success'])
        self.assertIn("already booked", booking2['error'])

        # 3. Clean up Alice's booking by cancelling
        cancel_res = cancel_reservation(res_id1)
        self.assertTrue(cancel_res['success'])

    def test_07_check_in_and_check_out_lifecycle(self):
        """Test full vehicle check-in, occupancy update, and check-out slot release."""
        now = datetime.datetime.now()
        start = now + datetime.timedelta(minutes=5)
        end = now + datetime.timedelta(hours=2)

        # Create reservation on slot 5 (A-105)
        booking = create_reservation(
            customer_name="George Clark",
            vehicle_plate="GEO-777",
            slot_id=5,
            start_time=start,
            end_time=end
        )
        self.assertTrue(booking['success'], booking.get('error'))
        res_id = booking['reservation_id']

        # Check in
        cin = check_in_vehicle(res_id)
        self.assertTrue(cin['success'], cin.get('error'))

        # Verify slot is occupied in DB
        slot = query_db("SELECT status FROM parking_slots WHERE id = 5", fetch_one=True)
        self.assertEqual(slot['status'], 'occupied')

        # Check out
        cout = check_out_vehicle(res_id)
        self.assertTrue(cout['success'], cout.get('error'))
        self.assertGreaterEqual(cout['actual_hours'], 1.0)

        # Verify slot released back to available
        slot_after = query_db("SELECT status FROM parking_slots WHERE id = 5", fetch_one=True)
        self.assertEqual(slot_after['status'], 'available')

    def test_08_admin_route_protection(self):
        """Test unauthenticated requests to protected admin routes are redirected to login."""
        res = self.client.get('/dashboard')
        self.assertEqual(res.status_code, 302)
        self.assertIn('/login', res.headers['Location'])

        res_slots = self.client.get('/parking-slots')
        self.assertEqual(res_slots.status_code, 302)
        self.assertIn('/login', res_slots.headers['Location'])

if __name__ == '__main__':
    unittest.main()
