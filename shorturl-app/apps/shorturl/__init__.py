import os
import sys

from py4web import URL, abort, action, redirect, request, response
from py4web.core import Fixture

from .models import db

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Initialize the app
__version__ = "1.0.0"
