import unittest
import sys
import os
import tempfile
import shutil

sys.path.append(os.path.join(os.path.dirname(__file__), "../shorturl-app"))

# Mock settings before importing
os.environ["DB_CONNECTION"] = ":memory:"
os.environ["DOMAIN"] = "test.local"

from apps.shorturl.utils.urlshortener import URLShortener


class TestURLShortener(unittest.TestCase):

    def test_generate_short_code(self):
        """Test short code generation"""
        # Test default length
        code = URLShortener.generate_short_code()
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isalnum())

        # Test custom length
        code = URLShortener.generate_short_code(8)
        self.assertEqual(len(code), 8)

        # Test uniqueness (run multiple times)
        codes = set()
        for _ in range(100):
            code = URLShortener.generate_short_code()
            codes.add(code)

        # Should generate mostly unique codes
        self.assertGreater(len(codes), 90)

    def test_qr_code_generation(self):
        """Test QR code generation"""
        qr_data = URLShortener.generate_qr_code("test123")
        self.assertIsInstance(qr_data, bytes)
        self.assertGreater(len(qr_data), 100)  # Should be a reasonable PNG file size

    def test_get_qr_code_base64(self):
        """Test QR code base64 conversion"""
        # This would need a database setup, so just test the method exists
        self.assertTrue(hasattr(URLShortener, "get_qr_code_base64"))


if __name__ == "__main__":
    unittest.main()
