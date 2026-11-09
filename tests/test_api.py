import importlib.util
import unittest

AVAILABLE = all(importlib.util.find_spec(name) for name in ("fastapi", "sqlalchemy", "httpx"))

@unittest.skipUnless(AVAILABLE, "install project test dependencies for API integration tests")
class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from energy_manager.api import app
        cls.client=TestClient(app)
    def test_dashboard_and_openapi(self):
        self.assertEqual(self.client.get("/").status_code,200)
        self.assertIn("/analytics",self.client.get("/openapi.json").json()["paths"])
    def test_health_and_empty_analytics(self):
        self.assertEqual(self.client.get("/health").json()["status"],"ok")
