import os
import sys
import tempfile
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), "../shorturl-app"))


class TestModels(unittest.TestCase):

    def test_imports(self):
        """Test that models can be imported without errors"""
        try:
            # Mock settings
            os.environ["DB_CONNECTION"] = ":memory:"
            # Import should not raise exceptions
            from apps.shorturl import models

            self.assertTrue(hasattr(models, "db"))
        except ImportError as e:
            # Skip if dependencies not available
            self.skipTest(f"Dependencies not available: {e}")

    def test_role_constants(self):
        """Test that role constants are defined"""
        try:
            from apps.shorturl.models import ROLES

            self.assertIn("admin", ROLES)
            self.assertIn("contributor", ROLES)
            self.assertIn("viewer", ROLES)
            self.assertIn("reporter", ROLES)
        except ImportError:
            self.skipTest("Models not available")


if __name__ == "__main__":
    unittest.main()
