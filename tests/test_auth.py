import unittest
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../shorturl-app'))

from apps.shorturl.utils.auth import Auth

class TestAuth(unittest.TestCase):
    
    def setUp(self):
        self.auth = Auth()
        
    def test_hash_password(self):
        """Test password hashing"""
        password = "test123"
        hashed = self.auth.hash_password(password)
        
        self.assertIsInstance(hashed, str)
        self.assertNotEqual(password, hashed)
        self.assertEqual(len(hashed), 64)  # SHA256 hex length
        
    def test_verify_password(self):
        """Test password verification"""
        password = "test123"
        hashed = self.auth.hash_password(password)
        
        # Correct password
        self.assertTrue(self.auth.verify_password(password, hashed))
        
        # Wrong password
        self.assertFalse(self.auth.verify_password("wrong", hashed))
        
    def test_password_consistency(self):
        """Test password hashing consistency"""
        password = "test123"
        hash1 = self.auth.hash_password(password)
        hash2 = self.auth.hash_password(password)
        
        # Same password should produce same hash
        self.assertEqual(hash1, hash2)

if __name__ == '__main__':
    unittest.main()