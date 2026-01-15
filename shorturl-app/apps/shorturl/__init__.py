from py4web import action, request, response, abort, redirect, URL
from py4web.core import Fixture
from .models import db
import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Initialize the app
__version__ = "1.0.0"
