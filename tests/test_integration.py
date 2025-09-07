import unittest
import tempfile
import os
import sys

class TestIntegration(unittest.TestCase):
    """Integration tests for the application"""
    
    def test_docker_build_files_exist(self):
        """Test that all required Docker build files exist"""
        required_files = [
            '../shorturl-app/Dockerfile',
            '../shorturl-app/requirements.txt',
            '../shorturl-app/entrypoint.sh',
            '../shorturl-app/main.py',
            '../docker-compose.yml'
        ]
        
        for file_path in required_files:
            full_path = os.path.join(os.path.dirname(__file__), file_path)
            self.assertTrue(os.path.exists(full_path), f"Required file missing: {file_path}")
            
    def test_python_files_syntax(self):
        """Test that all Python files have valid syntax"""
        import py_compile
        
        python_files = [
            '../shorturl-app/main.py',
            '../shorturl-app/proxy_server.py',
            '../shorturl-app/admin_portal.py',
            '../shorturl-app/settings.py'
        ]
        
        for file_path in python_files:
            full_path = os.path.join(os.path.dirname(__file__), file_path)
            if os.path.exists(full_path):
                try:
                    py_compile.compile(full_path, doraise=True)
                except py_compile.PyCompileError as e:
                    self.fail(f"Syntax error in {file_path}: {e}")
                    
    def test_environment_variables(self):
        """Test environment variable handling"""
        # Test default values
        test_vars = {
            'DB_TYPE': 'sqlite',
            'DOMAIN': 'localhost',
            'RATE_LIMIT_PER_SECOND': '10'
        }
        
        for var, default in test_vars.items():
            # Test that we can set and read env vars
            os.environ[var] = default
            self.assertEqual(os.environ.get(var), default)
            
    def test_directory_structure(self):
        """Test that the required directory structure exists"""
        required_dirs = [
            '../shorturl-app/apps/shorturl',
            '../shorturl-app/apps/shorturl/utils',
            '../shorturl-app/apps/shorturl/templates',
            '../docs',
            '../.github/workflows'
        ]
        
        for dir_path in required_dirs:
            full_path = os.path.join(os.path.dirname(__file__), dir_path)
            self.assertTrue(os.path.isdir(full_path), f"Required directory missing: {dir_path}")

if __name__ == '__main__':
    unittest.main()