import datetime
import hashlib
import os
import secrets
import sys
from functools import wraps

from py4web import URL, abort, redirect, request, response
from py4web.core import Fixture

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
)
from apps.shorturl.models import db


class Auth(Fixture):
    def __init__(self):
        self.current_user = None

    def on_request(self, context):
        # Check session for user
        if "user_id" in request.cookies:
            user = db(db.auth_user.id == request.cookies["user_id"]).select().first()
            if user and user.is_active:
                self.current_user = user

    def login(self, email, password):
        user = db(db.auth_user.email == email).select().first()
        if user and self.verify_password(password, user.password):
            if user.is_active:
                response.set_cookie("user_id", str(user.id), secure=True, httponly=True)
                db(db.auth_user.id == user.id).update(
                    last_login=datetime.datetime.utcnow()
                )
                db.commit()
                return user
        return None

    def logout(self):
        response.delete_cookie("user_id")
        self.current_user = None

    def register(self, email, password, first_name, last_name, role="viewer"):
        # Check if user exists
        if db(db.auth_user.email == email).count() > 0:
            return None

        # Hash password
        hashed_password = self.hash_password(password)

        # Generate API key
        api_key = secrets.token_urlsafe(32)

        # Create user
        user_id = db.auth_user.insert(
            email=email,
            password=hashed_password,
            first_name=first_name,
            last_name=last_name,
            role=role,
            api_key=api_key,
        )
        db.commit()
        return db.auth_user[user_id]

    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()

    def verify_password(self, password, hashed):
        return self.hash_password(password) == hashed

    def requires_login(self):
        if not self.current_user:
            redirect(URL("auth/login"))

    def requires_role(self, *roles):
        if not self.current_user:
            redirect(URL("auth/login"))
        if self.current_user.role not in roles:
            abort(403, "Access denied")

    def has_role(self, *roles):
        if not self.current_user:
            return False
        return self.current_user.role in roles


# Role-based decorators
def requires_login(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        auth = Auth()
        auth.on_request({})
        if not auth.current_user:
            redirect(URL("auth/login"))
        return func(*args, **kwargs)

    return wrapper


def requires_role(*roles):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            auth = Auth()
            auth.on_request({})
            if not auth.current_user:
                redirect(URL("auth/login"))
            if auth.current_user.role not in roles:
                abort(403, "Access denied")
            return func(*args, **kwargs)

        return wrapper

    return decorator


# Create singleton instance
auth = Auth()
