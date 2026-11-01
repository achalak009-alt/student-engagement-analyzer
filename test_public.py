import io
import unittest
from pathlib import Path
from app import app

class PublicAppTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_health_and_page(self):
        self.assertEqual(self.client.get('/health').json, {'status':'ok'})
        page = self.client.get('/')
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'synthetic', page.data)

    def test_fictional_demo(self):
        response = self.client.post('/api/demo', json={})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['total'], 500)
        self.assertTrue(all(r['student_id'].startswith('DEMO-') for r in response.json['records']))
        self.assertTrue(all(r['source_label']==r['rule_label'] for r in response.json['records']))

    def test_upload_and_validation(self):
        raw = (Path(__file__).parent/'data/upload_template.csv').read_bytes()
        self.assertEqual(self.client.post('/api/upload', data={'file':(io.BytesIO(raw),'sample.csv')}).json['total'], 3)
        self.assertEqual(self.client.post('/api/demo', json={'threshold':101}).status_code, 400)

if __name__ == '__main__':
    unittest.main()
