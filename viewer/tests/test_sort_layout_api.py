import json

from django.test import Client, TestCase


class SortLayoutApiTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_requires_post(self):
        resp = self.client.get("/api/sort-layout")
        self.assertEqual(resp.status_code, 405)

    def test_empty_addresses(self):
        resp = self.client.post(
            "/api/sort-layout",
            data=json.dumps(
                {
                    "addresses": [],
                    "criterion": "Order",
                    "orientation": "vertical",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data.get("ok"))
        self.assertEqual(data.get("glyphs"), [])

    def test_bad_criterion(self):
        resp = self.client.post(
            "/api/sort-layout",
            data=json.dumps(
                {
                    "addresses": ["Xa1-001"],
                    "criterion": "Visual Embedding",
                    "orientation": "vertical",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_horizontal_requires_max_row_width(self):
        resp = self.client.post(
            "/api/sort-layout",
            data=json.dumps(
                {
                    "addresses": ["Xa1-001"],
                    "criterion": "Order",
                    "orientation": "horizontal",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
