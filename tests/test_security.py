import os
import sys
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), "../shorturl-app"))

from apps.shorturl.utils.security import Security


class TestSecurity(unittest.TestCase):

    def test_sanitize_input(self):
        """Test input sanitization"""
        # Test XSS prevention
        malicious_input = "<script>alert('xss')</script>"
        sanitized = Security.sanitize_input(malicious_input)
        self.assertNotIn("<script>", sanitized)

        # Test normal input
        normal_input = "Hello World"
        sanitized = Security.sanitize_input(normal_input)
        self.assertEqual(sanitized, "Hello World")

        # Test None input
        self.assertIsNone(Security.sanitize_input(None))

    def test_validate_url(self):
        """Test URL validation"""
        # Valid URLs
        self.assertTrue(Security.validate_url("https://example.com"))
        self.assertTrue(Security.validate_url("http://example.com"))

        # Invalid URLs
        self.assertFalse(Security.validate_url("ftp://example.com"))
        self.assertFalse(Security.validate_url("javascript:alert('xss')"))
        self.assertFalse(Security.validate_url(""))
        self.assertFalse(Security.validate_url(None))

        # Prevent SSRF
        self.assertFalse(Security.validate_url("http://localhost"))
        self.assertFalse(Security.validate_url("http://127.0.0.1"))
        self.assertFalse(Security.validate_url("http://169.254.169.254"))
        self.assertFalse(Security.validate_url("http://10.0.0.1"))
        self.assertFalse(Security.validate_url("http://192.168.1.1"))

    def test_validate_short_code(self):
        """Test short code validation"""
        # Valid codes
        self.assertTrue(Security.validate_short_code("abc123"))
        self.assertTrue(Security.validate_short_code("my-link"))
        self.assertTrue(Security.validate_short_code("test_url"))

        # Invalid codes
        self.assertFalse(Security.validate_short_code(""))
        self.assertFalse(Security.validate_short_code(None))
        self.assertFalse(Security.validate_short_code("../admin"))
        self.assertFalse(Security.validate_short_code("test/path"))
        self.assertFalse(Security.validate_short_code("test\\path"))
        self.assertFalse(Security.validate_short_code("test<script>"))

    def test_check_sql_injection(self):
        """Test SQL injection prevention"""
        # Safe input
        self.assertTrue(Security.check_sql_injection("normal text"))
        self.assertTrue(Security.check_sql_injection("user@example.com"))
        self.assertTrue(Security.check_sql_injection(""))
        self.assertTrue(Security.check_sql_injection(None))

        # Suspicious input
        self.assertFalse(Security.check_sql_injection("'; DROP TABLE users; --"))
        self.assertFalse(Security.check_sql_injection("UNION SELECT * FROM users"))
        self.assertFalse(Security.check_sql_injection("1 OR 1=1"))


if __name__ == "__main__":
    unittest.main()
