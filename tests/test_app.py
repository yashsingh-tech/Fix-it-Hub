import os
import sqlite3
import tempfile
import unittest

import app as app_module


class FixItHubFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        app_module.DB_PATH = os.path.join(self.tmpdir.name, "test.db")
        app_module.ADMIN_USERNAME = "admin"
        app_module.ADMIN_PASSWORD = "admin123"
        app_module.app.config.update(TESTING=True, SESSION_COOKIE_SECURE=False)
        app_module.app.secret_key = "test-secret"
        app_module.init_db()
        self.client = app_module.app.test_client()

    def tearDown(self):
        self.tmpdir.cleanup()

    def csrf_for(self, path):
        self.client.get(path)
        with self.client.session_transaction() as sess:
            return sess["_csrf_token"]

    def post_with_csrf(self, path, data=None, token_path=None):
        token = self.csrf_for(token_path or path)
        payload = {"_csrf_token": token}
        payload.update(data or {})
        return self.client.post(path, data=payload, follow_redirects=False)

    def db_value(self, query, args=()):
        with sqlite3.connect(app_module.DB_PATH) as conn:
            return conn.execute(query, args).fetchone()[0]

    def register_worker(self, email="worker@example.com", service="plumber"):
        return self.post_with_csrf(
            "/worker/register",
            {
                "name": "Asha Worker",
                "phone": "+91 9876543210",
                "service": service,
                "email": email,
                "address": "Vaishali Nagar",
                "password": "strongpass123",
            },
        )

    def login_worker(self, email="worker@example.com"):
        return self.post_with_csrf(
            "/worker/login",
            {"email": email, "password": "strongpass123"},
        )

    def test_post_requires_csrf_token(self):
        response = self.client.post("/worker/login", data={"email": "x@y.com", "password": "password"})
        self.assertEqual(response.status_code, 400)

    def test_worker_registration_validates_and_rejects_duplicate_email(self):
        weak = self.post_with_csrf(
            "/worker/register",
            {
                "name": "Asha Worker",
                "phone": "+91 9876543210",
                "service": "plumber",
                "email": "worker@example.com",
                "address": "Vaishali Nagar",
                "password": "short",
            },
        )
        self.assertEqual(weak.status_code, 400)

        created = self.register_worker()
        self.assertEqual(created.status_code, 302)
        self.assertEqual(self.db_value("SELECT COUNT(*) FROM workers"), 1)

        duplicate = self.register_worker()
        self.assertEqual(duplicate.status_code, 409)

    def test_booking_validates_worker_and_customer_phone(self):
        self.register_worker()
        worker_id = self.db_value("SELECT id FROM workers WHERE email=?", ("worker@example.com",))

        self.assertEqual(self.client.get("/book/999").status_code, 404)

        invalid = self.post_with_csrf(
            f"/book/{worker_id}",
            {
                "customer_name": "Customer",
                "customer_phone": "bad-phone",
                "customer_address": "Main Road",
            },
        )
        self.assertEqual(invalid.status_code, 400)

        booked = self.post_with_csrf(
            f"/book/{worker_id}",
            {
                "customer_name": "Customer",
                "customer_phone": "+91 9000000000",
                "customer_address": "Main Road",
            },
        )
        self.assertEqual(booked.status_code, 302)
        self.assertEqual(self.db_value("SELECT COUNT(*) FROM bookings"), 1)

    def test_booking_status_requires_logged_in_owner(self):
        self.register_worker("first@example.com", "plumber")
        self.register_worker("second@example.com", "electrician")

        first_id = self.db_value("SELECT id FROM workers WHERE email=?", ("first@example.com",))
        second_id = self.db_value("SELECT id FROM workers WHERE email=?", ("second@example.com",))
        with sqlite3.connect(app_module.DB_PATH) as conn:
            conn.execute(
                "INSERT INTO bookings (customer_name, customer_phone, customer_address, service, worker_id) VALUES (?, ?, ?, ?, ?)",
                ("Other Customer", "+91 9000000000", "Other Road", "electrician", second_id),
            )
            conn.commit()
        booking_id = self.db_value("SELECT id FROM bookings WHERE worker_id=?", (second_id,))

        unauthenticated = self.post_with_csrf(f"/booking/accept/{booking_id}", token_path="/worker/login")
        self.assertEqual(unauthenticated.status_code, 302)

        self.login_worker("first@example.com")
        denied = self.post_with_csrf(f"/booking/accept/{booking_id}", token_path="/worker/dashboard")
        self.assertEqual(denied.status_code, 302)
        self.assertEqual(self.db_value("SELECT status FROM bookings WHERE id=?", (booking_id,)), "pending")

        with sqlite3.connect(app_module.DB_PATH) as conn:
            conn.execute(
                "INSERT INTO bookings (customer_name, customer_phone, customer_address, service, worker_id) VALUES (?, ?, ?, ?, ?)",
                ("Own Customer", "+91 9111111111", "Own Road", "plumber", first_id),
            )
            conn.commit()
        own_booking_id = self.db_value("SELECT id FROM bookings WHERE worker_id=?", (first_id,))
        accepted = self.post_with_csrf(f"/booking/accept/{own_booking_id}", token_path="/worker/dashboard")
        self.assertEqual(accepted.status_code, 302)
        self.assertEqual(self.db_value("SELECT status FROM bookings WHERE id=?", (own_booking_id,)), "accepted")


if __name__ == "__main__":
    unittest.main()
