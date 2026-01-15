import unittest
import string
import random
import hashlib


class TestUtilityFunctions(unittest.TestCase):
    """Test isolated utility functions"""

    def test_generate_short_code(self):
        """Test short code generation logic"""

        def generate_short_code(length=6):
            chars = string.ascii_letters + string.digits
            return "".join(random.choice(chars) for _ in range(length))

        # Test default length
        code = generate_short_code()
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isalnum())

        # Test custom length
        code = generate_short_code(8)
        self.assertEqual(len(code), 8)

        # Test uniqueness (run multiple times)
        codes = set()
        for _ in range(100):
            code = generate_short_code()
            codes.add(code)

        # Should generate mostly unique codes
        self.assertGreater(len(codes), 90)

    def test_hash_password(self):
        """Test password hashing logic"""

        def hash_password(password):
            return hashlib.sha256(password.encode()).hexdigest()

        def verify_password(password, hashed):
            return hash_password(password) == hashed

        password = "test123"
        hashed = hash_password(password)

        self.assertIsInstance(hashed, str)
        self.assertNotEqual(password, hashed)
        self.assertEqual(len(hashed), 64)  # SHA256 hex length

        # Test verification
        self.assertTrue(verify_password(password, hashed))
        self.assertFalse(verify_password("wrong", hashed))

        # Test consistency
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        self.assertEqual(hash1, hash2)

    def test_reserved_paths(self):
        """Test reserved path validation"""
        RESERVED_PATHS = ["admin", "api", "healthz", "metrics", "static", "auth"]

        def is_reserved_path(path):
            return path.lower() in RESERVED_PATHS

        # Test reserved paths
        self.assertTrue(is_reserved_path("admin"))
        self.assertTrue(is_reserved_path("API"))  # Case insensitive
        self.assertTrue(is_reserved_path("healthz"))

        # Test non-reserved paths
        self.assertFalse(is_reserved_path("mylink"))
        self.assertFalse(is_reserved_path("test123"))

    def test_role_validation(self):
        """Test role validation logic"""
        VALID_ROLES = ["admin", "contributor", "viewer", "reporter"]

        def is_valid_role(role):
            return role in VALID_ROLES

        def has_permission(user_role, required_roles):
            return user_role in required_roles

        # Test role validation
        self.assertTrue(is_valid_role("admin"))
        self.assertTrue(is_valid_role("viewer"))
        self.assertFalse(is_valid_role("invalid"))

        # Test permission checking
        self.assertTrue(has_permission("admin", ["admin", "contributor"]))
        self.assertFalse(has_permission("viewer", ["admin", "contributor"]))


if __name__ == "__main__":
    unittest.main()
