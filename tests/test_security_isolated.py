import unittest
import sys
import os
import re
import html
import urllib.parse

# Isolated Security class for testing (without external dependencies)
class SecurityIsolated:
    
    @staticmethod
    def sanitize_input(text):
        """Sanitize user input to prevent XSS"""
        if not text:
            return text
        # HTML escape
        text = html.escape(text)
        # Remove potential script tags
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
        # Remove javascript: protocol
        text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
        return text
    
    @staticmethod
    def validate_url(url):
        """Validate URL to prevent SSRF and other attacks"""
        if not url:
            return False
            
        # Parse URL
        try:
            parsed = urllib.parse.urlparse(url)
        except:
            return False
            
        # Check protocol
        if parsed.scheme not in ['http', 'https']:
            return False
            
        # Prevent localhost and internal IPs
        dangerous_hosts = [
            'localhost', '127.0.0.1', '0.0.0.0',
            '169.254.169.254',  # AWS metadata
            '::1', '::ffff:127.0.0.1'
        ]
        
        if parsed.hostname in dangerous_hosts:
            return False
            
        # Check for internal IP ranges
        if parsed.hostname:
            parts = parsed.hostname.split('.')
            if len(parts) == 4:
                try:
                    # Check for private IP ranges
                    octets = [int(p) for p in parts]
                    if octets[0] == 10:  # 10.0.0.0/8
                        return False
                    if octets[0] == 172 and 16 <= octets[1] <= 31:  # 172.16.0.0/12
                        return False
                    if octets[0] == 192 and octets[1] == 168:  # 192.168.0.0/16
                        return False
                except:
                    pass
                    
        return True
    
    @staticmethod
    def validate_short_code(code):
        """Validate short code to prevent path traversal"""
        if not code:
            return False
            
        # Only allow alphanumeric and hyphens/underscores
        if not re.match(r'^[a-zA-Z0-9\-_]+$', code):
            return False
            
        # Prevent path traversal
        if '..' in code or '/' in code or '\\' in code:
            return False
            
        return True
    
    @staticmethod
    def check_sql_injection(text):
        """Basic SQL injection prevention check"""
        if not text:
            return True
            
        # Common SQL injection patterns
        sql_patterns = [
            r'(\bunion\b.*\bselect\b)',
            r'(\bselect\b.*\bfrom\b)',
            r'(\binsert\b.*\binto\b)',
            r'(\bupdate\b.*\bset\b)',
            r'(\bdelete\b.*\bfrom\b)',
            r'(\bdrop\b.*\btable\b)',
            r'(\bcreate\b.*\btable\b)',
            r'(\balter\b.*\btable\b)',
            r'(\bexec\b|\bexecute\b)',
            r'(\bscript\b)',
            r'(--|\#|\/\*)',
            r'(\bor\b.*=.*)',
            r'(\band\b.*=.*)'
        ]
        
        text_lower = text.lower()
        for pattern in sql_patterns:
            if re.search(pattern, text_lower):
                return False
                
        return True

class TestSecurityIsolated(unittest.TestCase):
    
    def test_sanitize_input(self):
        """Test input sanitization"""
        # Test XSS prevention
        malicious_input = "<script>alert('xss')</script>"
        sanitized = SecurityIsolated.sanitize_input(malicious_input)
        self.assertNotIn("<script>", sanitized)
        
        # Test normal input
        normal_input = "Hello World"
        sanitized = SecurityIsolated.sanitize_input(normal_input)
        self.assertEqual(sanitized, "Hello World")
        
        # Test None input
        self.assertIsNone(SecurityIsolated.sanitize_input(None))
        
        # Test HTML escaping
        html_input = "<div>Test & Company</div>"
        sanitized = SecurityIsolated.sanitize_input(html_input)
        self.assertIn("&lt;div&gt;", sanitized)
        self.assertIn("&amp;", sanitized)
        
    def test_validate_url(self):
        """Test URL validation"""
        # Valid URLs
        self.assertTrue(SecurityIsolated.validate_url("https://example.com"))
        self.assertTrue(SecurityIsolated.validate_url("http://example.com"))
        self.assertTrue(SecurityIsolated.validate_url("https://sub.example.com/path"))
        
        # Invalid URLs
        self.assertFalse(SecurityIsolated.validate_url("ftp://example.com"))
        self.assertFalse(SecurityIsolated.validate_url("javascript:alert('xss')"))
        self.assertFalse(SecurityIsolated.validate_url(""))
        self.assertFalse(SecurityIsolated.validate_url(None))
        
        # Prevent SSRF
        self.assertFalse(SecurityIsolated.validate_url("http://localhost"))
        self.assertFalse(SecurityIsolated.validate_url("http://127.0.0.1"))
        self.assertFalse(SecurityIsolated.validate_url("http://169.254.169.254"))
        self.assertFalse(SecurityIsolated.validate_url("http://10.0.0.1"))
        self.assertFalse(SecurityIsolated.validate_url("http://192.168.1.1"))
        self.assertFalse(SecurityIsolated.validate_url("http://172.16.0.1"))
        
    def test_validate_short_code(self):
        """Test short code validation"""
        # Valid codes
        self.assertTrue(SecurityIsolated.validate_short_code("abc123"))
        self.assertTrue(SecurityIsolated.validate_short_code("my-link"))
        self.assertTrue(SecurityIsolated.validate_short_code("test_url"))
        self.assertTrue(SecurityIsolated.validate_short_code("Test123"))
        
        # Invalid codes
        self.assertFalse(SecurityIsolated.validate_short_code(""))
        self.assertFalse(SecurityIsolated.validate_short_code(None))
        self.assertFalse(SecurityIsolated.validate_short_code("../admin"))
        self.assertFalse(SecurityIsolated.validate_short_code("test/path"))
        self.assertFalse(SecurityIsolated.validate_short_code("test\\path"))
        self.assertFalse(SecurityIsolated.validate_short_code("test<script>"))
        self.assertFalse(SecurityIsolated.validate_short_code("test space"))
        self.assertFalse(SecurityIsolated.validate_short_code("test@url"))
        
    def test_check_sql_injection(self):
        """Test SQL injection prevention"""
        # Safe input
        self.assertTrue(SecurityIsolated.check_sql_injection("normal text"))
        self.assertTrue(SecurityIsolated.check_sql_injection("user@example.com"))
        self.assertTrue(SecurityIsolated.check_sql_injection(""))
        self.assertTrue(SecurityIsolated.check_sql_injection(None))
        self.assertTrue(SecurityIsolated.check_sql_injection("Hello World 123"))
        
        # Suspicious input
        self.assertFalse(SecurityIsolated.check_sql_injection("'; DROP TABLE users; --"))
        self.assertFalse(SecurityIsolated.check_sql_injection("UNION SELECT * FROM users"))
        self.assertFalse(SecurityIsolated.check_sql_injection("1 OR 1=1"))
        self.assertFalse(SecurityIsolated.check_sql_injection("admin'--"))
        self.assertFalse(SecurityIsolated.check_sql_injection("SELECT password FROM users"))

if __name__ == '__main__':
    unittest.main()