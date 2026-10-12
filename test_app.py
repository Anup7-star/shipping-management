"""
test_app.py - Automated End-to-End Test Suite for ShipFlow DBMS
Tests Flask routes, transactions, status updates, destination changes, and DBMS logging.
"""

import unittest
from app import app
import db

class ShipFlowTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        # Ensure fresh DB state
        db.init_db(force_recreate=True)

    def test_01_public_routes(self):
        """Verify public access to login and tracking pages."""
        res_login = self.client.get('/login')
        self.assertEqual(res_login.status_code, 200)
        self.assertIn(b"ShipFlow DBMS Portal", res_login.data)

        res_track = self.client.get('/track')
        self.assertEqual(res_track.status_code, 200)
        self.assertIn(b"Public Parcel Tracking", res_track.data)

    def test_02_demo_login(self):
        """Verify 1-click quick demo login for Admin."""
        res = self.client.post('/login', data={'demo_role': 'admin'}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Logistics Control Center", res.data)
        self.assertIn(b"Role: ADMIN", res.data)

    def test_03_create_shipment_transaction(self):
        """Verify booking a new shipment via user-friendly form (TCL Transaction)."""
        # Login first
        self.client.post('/login', data={'demo_role': 'admin'}, follow_redirects=True)

        payload = {
            'sender_name': 'Sarah Connor',
            'recipient_name': 'John Connor',
            'recipient_phone': '+1 555-9000',
            'origin_city': 'Los Angeles',
            'origin_address': '8404 Reseda Blvd',
            'destination_city': 'Cyberdyne HQ',
            'destination_address': '18144 El Camino Real',
            'weight_kg': '7.5',
            'shipping_type': 'Express',
            'notes': 'High priority equipment'
        }

        res = self.client.post('/shipments/new', data=payload, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Shipment booked successfully", res.data)
        self.assertIn(b"Cyberdyne HQ", res.data)

        # Verify row in database
        row = db.query_one("SELECT * FROM shipments WHERE recipient_name = 'John Connor'")
        self.assertIsNotNone(row)
        self.assertEqual(row["destination_city"], "Cyberdyne HQ")
        self.assertEqual(row["status"], "Pending")

    def test_04_status_update_and_trigger(self):
        """Verify status update fires SQLite Trigger trg_shipment_status_audit."""
        self.client.post('/login', data={'demo_role': 'admin'}, follow_redirects=True)

        # Get existing shipment
        shipment = db.query_one("SELECT id, tracking_number FROM shipments LIMIT 1")
        s_id = shipment["id"]
        t_num = shipment["tracking_number"]

        # Update status to 'In Transit'
        res = self.client.post(f'/shipments/{s_id}/status', data={
            'status': 'In Transit',
            'current_location': 'Central Sorting Gateway',
            'notes': 'Passed x-ray scan'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Verify DB trigger created a tracking_event row
        event = db.query_one(
            "SELECT * FROM tracking_events WHERE shipment_id = ? AND status = 'In Transit' ORDER BY id DESC LIMIT 1",
            (s_id,)
        )
        self.assertIsNotNone(event)
        self.assertEqual(event["location"], "Central Sorting Gateway")

    def test_05_reroute_destination(self):
        """Verify updating destination address and city."""
        self.client.post('/login', data={'demo_role': 'admin'}, follow_redirects=True)

        shipment = db.query_one("SELECT id FROM shipments LIMIT 1")
        s_id = shipment["id"]

        res = self.client.post(f'/shipments/{s_id}/destination', data={
            'destination_city': 'Seattle',
            'destination_address': '700 Pike Street',
            'reason': 'Customer moved address'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Verify in DB
        updated = db.query_one("SELECT destination_city, destination_address FROM shipments WHERE id = ?", (s_id,))
        self.assertEqual(updated["destination_city"], "Seattle")
        self.assertEqual(updated["destination_address"], "700 Pike Street")

    def test_06_live_sql_logs_api(self):
        """Verify live SQL logs endpoint returns structured entries."""
        res = self.client.get('/api/sql-logs?limit=10')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "success")
        self.assertGreater(data["total_operations"], 0)
        self.assertIsInstance(data["logs"], list)

    def test_07_dbms_inspector_page(self):
        """Verify DBMS inspector page displays tables, views, and triggers."""
        self.client.post('/login', data={'demo_role': 'admin'}, follow_redirects=True)
        res = self.client.get('/dbms-inspector')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"TABLE: shipments", res.data)
        self.assertIn(b"view_active_deliveries", res.data)
        self.assertIn(b"trg_shipment_status_audit", res.data)

if __name__ == '__main__':
    unittest.main()
