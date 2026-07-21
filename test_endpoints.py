import unittest
import json
from app import app, TELEMETRY_SECRET_TOKEN

class EndpointTestCase(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_health_check(self):
        """Test the /health observability endpoint."""
        response = self.app.get('/health')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data['status'], 'healthy')
        self.assertIn('uptime_seconds', data)
        self.assertIn('total_telemetry_records', data)

    def test_telemetry_unauthorized(self):
        """Test that /api/telemetry rejects POST requests without token."""
        response = self.app.post('/api/telemetry', json={'link_ativo': 'VIVO'})
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data['status'], 'error')

    def test_telemetry_authorized(self):
        """Test that /api/telemetry accepts POST requests with valid secret token."""
        payload = {
            'link_ativo': 'VIVO',
            'cpu': 12,
            'temp': 35,
            'ram': 28,
            'uptime': '1w1d',
            'rtt_vivo_mm': 45.2,
            'rtt_micks_mm': 60.1
        }
        url = f'/api/telemetry?token={TELEMETRY_SECRET_TOKEN}'
        response = self.app.post(url, json=payload)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data['status'], 'success')

    def test_latest_data_endpoint(self):
        """Test the /api/data/latest endpoint."""
        response = self.app.get('/api/data/latest')
        self.assertEqual(response.status_code, 200)

if __name__ == '__main__':
    unittest.main()
