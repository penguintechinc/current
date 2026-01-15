#!/usr/bin/env python3
"""
Smoke Tests for Current Application

Tests basic functionality to ensure the application is working:
1. Services build successfully
2. Services start and run
3. Health endpoints respond
4. API endpoints are accessible
5. WebUI loads
"""

import requests
import subprocess
import time
import sys
from typing import Dict, List, Tuple

# Configuration
FLASK_URL = "http://localhost:5002"
WEBUI_URL = "http://localhost:3008"
TIMEOUT = 30


class Color:
    """ANSI color codes for terminal output"""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    END = "\033[0m"
    BOLD = "\033[1m"


def print_test(name: str, status: str, message: str = ""):
    """Print test result with color"""
    if status == "PASS":
        print(f"{Color.GREEN}✓{Color.END} {name}")
        if message:
            print(f"  {Color.BLUE}{message}{Color.END}")
    elif status == "FAIL":
        print(f"{Color.RED}✗{Color.END} {name}")
        if message:
            print(f"  {Color.RED}{message}{Color.END}")
    elif status == "SKIP":
        print(f"{Color.YELLOW}○{Color.END} {name}")
        if message:
            print(f"  {Color.YELLOW}{message}{Color.END}")


def run_command(cmd: List[str], timeout: int = 60) -> Tuple[int, str, str]:
    """Run shell command and return exit code, stdout, stderr"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"
    except Exception as e:
        return 1, "", str(e)


def test_docker_compose_up() -> bool:
    """Test that docker-compose up succeeds"""
    print(f"\n{Color.BOLD}1. Testing Docker Compose Services{Color.END}")

    # Check if services are already running
    code, stdout, stderr = run_command(["docker", "compose", "ps", "-q"])
    if code == 0 and stdout.strip():
        print_test("Docker Compose services", "PASS", "Services already running")
        return True

    # Start services
    print("  Starting services (this may take a minute)...")
    code, stdout, stderr = run_command(["docker", "compose", "up", "-d"], timeout=120)

    if code != 0:
        print_test("Docker Compose up", "FAIL", f"Failed to start: {stderr}")
        return False

    print_test("Docker Compose up", "PASS", "All services started")
    return True


def test_services_healthy() -> bool:
    """Test that all services are healthy"""
    print(f"\n{Color.BOLD}2. Testing Service Health{Color.END}")

    services = ["postgres", "redis", "flask-backend", "webui"]
    all_healthy = True

    # Wait for services to start
    print("  Waiting for services to become healthy...")
    time.sleep(10)

    for service in services:
        code, stdout, stderr = run_command(
            ["docker", "compose", "ps", "--format", "json", service]
        )

        if code != 0 or not stdout.strip():
            print_test(f"Service: {service}", "FAIL", "Not found")
            all_healthy = False
            continue

        # Check if running
        if "running" in stdout.lower() or "up" in stdout.lower():
            print_test(f"Service: {service}", "PASS", "Running")
        else:
            print_test(f"Service: {service}", "FAIL", "Not running")
            all_healthy = False

    return all_healthy


def test_flask_health() -> bool:
    """Test Flask backend health endpoint"""
    print(f"\n{Color.BOLD}3. Testing Flask Backend API{Color.END}")

    try:
        response = requests.get(f"{FLASK_URL}/healthz", timeout=10)

        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "healthy":
                print_test(
                    "Flask health endpoint",
                    "PASS",
                    f"Database: {data.get('database', 'unknown')}",
                )
                return True
            else:
                print_test(
                    "Flask health endpoint", "FAIL", f"Status: {data.get('status')}"
                )
                return False
        else:
            print_test("Flask health endpoint", "FAIL", f"HTTP {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        print_test("Flask health endpoint", "FAIL", str(e))
        return False


def test_flask_api_endpoints() -> bool:
    """Test Flask API endpoints"""
    print(f"\n{Color.BOLD}4. Testing Flask API Endpoints{Color.END}")

    endpoints = [
        ("/api/v1/status", 200, "Status endpoint"),
        ("/api/v1/scopes", 401, "Scopes endpoint (auth required)"),
        ("/api/v1/roles", 401, "Roles endpoint (auth required)"),
    ]

    all_passed = True

    for path, expected_status, description in endpoints:
        try:
            response = requests.get(f"{FLASK_URL}{path}", timeout=5)

            if response.status_code == expected_status:
                print_test(description, "PASS", f"HTTP {response.status_code}")
            else:
                print_test(
                    description,
                    "FAIL",
                    f"Expected {expected_status}, got {response.status_code}",
                )
                all_passed = False

        except requests.exceptions.RequestException as e:
            print_test(description, "FAIL", str(e))
            all_passed = False

    return all_passed


def test_webui_health() -> bool:
    """Test WebUI health endpoint"""
    print(f"\n{Color.BOLD}5. Testing WebUI{Color.END}")

    try:
        response = requests.get(f"{WEBUI_URL}/healthz", timeout=10)

        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "healthy":
                print_test("WebUI health endpoint", "PASS")
                return True
            else:
                print_test(
                    "WebUI health endpoint", "FAIL", f"Status: {data.get('status')}"
                )
                return False
        else:
            print_test("WebUI health endpoint", "FAIL", f"HTTP {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        print_test("WebUI health endpoint", "FAIL", str(e))
        return False


def test_webui_loads() -> bool:
    """Test that WebUI homepage loads"""
    print(f"\n{Color.BOLD}6. Testing WebUI Page Load{Color.END}")

    try:
        response = requests.get(f"{WEBUI_URL}/", timeout=10)

        if response.status_code == 200:
            # Check for React root element
            if 'id="root"' in response.text:
                print_test("WebUI homepage", "PASS", "React app loaded")
                return True
            else:
                print_test("WebUI homepage", "FAIL", "React root not found")
                return False
        else:
            print_test("WebUI homepage", "FAIL", f"HTTP {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        print_test("WebUI homepage", "FAIL", str(e))
        return False


def test_logo_files() -> bool:
    """Test that logo files are accessible"""
    print(f"\n{Color.BOLD}7. Testing Logo Assets{Color.END}")

    logo_files = [
        "/favicon.ico",
        "/favicon.svg",
        "/logo192.png",
        "/logo512.png",
        "/logo-full.png",
        "/manifest.json",
    ]

    all_passed = True

    for path in logo_files:
        try:
            response = requests.get(f"{WEBUI_URL}{path}", timeout=5)

            if response.status_code == 200:
                print_test(f"Asset: {path}", "PASS")
            else:
                print_test(f"Asset: {path}", "FAIL", f"HTTP {response.status_code}")
                all_passed = False

        except requests.exceptions.RequestException as e:
            print_test(f"Asset: {path}", "FAIL", str(e))
            all_passed = False

    return all_passed


def main():
    """Run all smoke tests"""
    print(f"\n{Color.BOLD}{'='*60}{Color.END}")
    print(f"{Color.BOLD}Current Application - Smoke Tests{Color.END}")
    print(f"{Color.BOLD}{'='*60}{Color.END}")

    results = {
        "Docker Compose": test_docker_compose_up(),
        "Service Health": test_services_healthy(),
        "Flask Health": test_flask_health(),
        "Flask API": test_flask_api_endpoints(),
        "WebUI Health": test_webui_health(),
        "WebUI Load": test_webui_loads(),
        "Logo Assets": test_logo_files(),
    }

    # Summary
    print(f"\n{Color.BOLD}{'='*60}{Color.END}")
    print(f"{Color.BOLD}Summary{Color.END}")
    print(f"{Color.BOLD}{'='*60}{Color.END}")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = (
            f"{Color.GREEN}PASS{Color.END}" if result else f"{Color.RED}FAIL{Color.END}"
        )
        print(f"  {test_name}: {status}")

    print(f"\n{Color.BOLD}Total: {passed}/{total} passed{Color.END}")

    if passed == total:
        print(f"\n{Color.GREEN}{Color.BOLD}✓ All smoke tests passed!{Color.END}")
        return 0
    else:
        print(f"\n{Color.RED}{Color.BOLD}✗ Some tests failed{Color.END}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
