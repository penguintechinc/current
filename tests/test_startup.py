import unittest
import sys
import os
import tempfile

class TestApplicationStartup(unittest.TestCase):
    """Test application startup and configuration"""
    
    def test_main_py_structure(self):
        """Test that main.py has the expected structure"""
        main_py_path = os.path.join(os.path.dirname(__file__), '../shorturl-app/main.py')
        
        with open(main_py_path, 'r') as f:
            content = f.read()
            
        # Check for essential imports and functions
        self.assertIn('asyncio', content)
        self.assertIn('def main()', content)
        self.assertIn('if __name__ == \'__main__\':', content)
        self.assertIn('init_database', content)
        self.assertIn('init_certificates', content)
        
    def test_settings_structure(self):
        """Test that settings.py has required configuration"""
        settings_path = os.path.join(os.path.dirname(__file__), '../shorturl-app/settings.py')
        
        with open(settings_path, 'r') as f:
            content = f.read()
            
        # Check for essential configuration
        required_settings = [
            'APP_NAME',
            'DB_TYPE',
            'DB_CONNECTION',
            'DOMAIN',
            'SECRET_KEY',
            'PROXY_HTTP_PORT',
            'PROXY_HTTPS_PORT',
            'ADMIN_HTTPS_PORT'
        ]
        
        for setting in required_settings:
            self.assertIn(setting, content, f"Missing required setting: {setting}")
            
    def test_docker_compose_structure(self):
        """Test that docker-compose.yml is properly structured"""
        compose_path = os.path.join(os.path.dirname(__file__), '../docker-compose.yml')
        
        with open(compose_path, 'r') as f:
            content = f.read()
            
        # Check for required services and configuration
        required_elements = [
            'version:',
            'services:',
            'shorturl:',
            'redis:',
            'ports:',
            '- "80:80"',
            '- "443:443"',
            '- "9443:9443"',
            'volumes:',
            'networks:'
        ]
        
        for element in required_elements:
            self.assertIn(element, content, f"Missing docker-compose element: {element}")
            
    def test_dockerfile_structure(self):
        """Test that Dockerfile has proper structure"""
        dockerfile_path = os.path.join(os.path.dirname(__file__), '../shorturl-app/Dockerfile')
        
        with open(dockerfile_path, 'r') as f:
            content = f.read()
            
        # Check for essential Dockerfile elements
        required_elements = [
            'FROM python:3.12-slim',
            'WORKDIR /app',
            'COPY requirements.txt',
            'RUN pip install',
            'EXPOSE 80 443 9443',
            'ENTRYPOINT',
            'HEALTHCHECK'
        ]
        
        for element in required_elements:
            self.assertIn(element, content, f"Missing Dockerfile element: {element}")
            
    def test_entrypoint_structure(self):
        """Test that entrypoint.sh is properly structured"""
        entrypoint_path = os.path.join(os.path.dirname(__file__), '../shorturl-app/entrypoint.sh')
        
        with open(entrypoint_path, 'r') as f:
            content = f.read()
            
        # Check for essential entrypoint elements
        self.assertIn('#!/bin/bash', content)
        self.assertIn('openssl req -x509', content)
        self.assertIn('certbot renew', content)
        self.assertIn('exec python /app/main.py', content)
        
    def test_github_workflows_exist(self):
        """Test that GitHub workflows are present"""
        workflows_dir = os.path.join(os.path.dirname(__file__), '../.github/workflows')
        
        self.assertTrue(os.path.exists(workflows_dir))
        
        # Check for workflow files
        build_workflow = os.path.join(workflows_dir, 'build-and-test.yml')
        release_workflow = os.path.join(workflows_dir, 'release.yml')
        
        self.assertTrue(os.path.exists(build_workflow))
        self.assertTrue(os.path.exists(release_workflow))
        
        # Check workflow content
        with open(build_workflow, 'r') as f:
            content = f.read()
            self.assertIn('linux/amd64,linux/arm64,linux/arm/v7', content)
            self.assertIn('python -m pytest', content)
            
    def test_requirements_files(self):
        """Test that requirements files are properly structured"""
        req_path = os.path.join(os.path.dirname(__file__), '../shorturl-app/requirements.txt')
        dev_req_path = os.path.join(os.path.dirname(__file__), '../shorturl-app/requirements-dev.txt')
        
        # Check main requirements
        with open(req_path, 'r') as f:
            req_content = f.read()
            
        essential_packages = [
            'py4web',
            'pydal',
            'aiohttp',
            'qrcode',
            'cryptography'
        ]
        
        for package in essential_packages:
            self.assertIn(package, req_content, f"Missing essential package: {package}")
            
        # Check dev requirements exist
        self.assertTrue(os.path.exists(dev_req_path))
        
        with open(dev_req_path, 'r') as f:
            dev_content = f.read()
            self.assertIn('pytest', dev_content)

if __name__ == '__main__':
    unittest.main()