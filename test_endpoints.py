import unittest
import json
from app import app, TELEMETRY_SECRET_TOKEN
from services.sla_service import calculate_mos_score, estimate_dicom_load_time

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

    def test_radiology_status_endpoint(self):
        """Test the /api/radiology/status endpoint."""
        response = self.app.get('/api/radiology/status')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertIn('mos_laudite', data)
        self.assertIn('ct_load_time_500mb', data)
        self.assertIn('flapping_risk', data)

    def test_laudite_mos_calculation(self):
        """Test ITU-T G.107 MOS score for Laudite audio."""
        mos, status = calculate_mos_score(30, 2)
        self.assertGreaterEqual(mos, 4.0)
        self.assertIn("Excelente", status)
        
        mos_bad, status_bad = calculate_mos_score(600, 150, loss_pct=5.0)
        self.assertLess(mos_bad, 3.5)

    def test_dicom_estimator(self):
        """Test DICOM CT load time estimation."""
        time_str = estimate_dicom_load_time(100000000, 500) # 100 Mbps
        self.assertEqual(time_str, "40.0 s")

    def test_routeros_time_parsing(self):
        """Test RouterOS 7 HH:MM:SS.ffffff time string parsing."""
        from db import parse_float
        self.assertEqual(parse_float('00:00:00.051138'), 51.1)
        self.assertEqual(parse_float('00:00:00.173400'), 173.4)

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

if __name__ == '__main__':
    unittest.main()
