from py4web import DAL, Field
from pydal.validators import *
import datetime
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from settings import DB_URI

db = DAL(DB_URI, pool_size=20, migrate=True, fake_migrate=False)

# User roles
ROLES = {
    'admin': 'Admin',
    'contributor': 'Contributor',
    'viewer': 'Viewer',
    'reporter': 'Reporter'
}

# Users table
db.define_table('auth_user',
    Field('email', 'string', unique=True, requires=[IS_EMAIL(), IS_NOT_EMPTY()]),
    Field('password', 'password', requires=[IS_NOT_EMPTY(), CRYPT()]),
    Field('first_name', 'string', requires=IS_NOT_EMPTY()),
    Field('last_name', 'string', requires=IS_NOT_EMPTY()),
    Field('role', 'string', default='viewer', requires=IS_IN_SET(list(ROLES.keys()))),
    Field('is_active', 'boolean', default=True),
    Field('created_on', 'datetime', default=datetime.datetime.utcnow),
    Field('last_login', 'datetime'),
    Field('api_key', 'string', unique=True),
    format='%(first_name)s %(last_name)s'
)

# Categories table
db.define_table('categories',
    Field('name', 'string', unique=True, requires=[IS_NOT_EMPTY(), IS_ALPHANUMERIC()]),
    Field('description', 'text'),
    Field('is_active', 'boolean', default=True),
    Field('created_by', 'reference auth_user'),
    Field('created_on', 'datetime', default=datetime.datetime.utcnow),
    format='%(name)s'
)

# URLs table
db.define_table('urls',
    Field('short_code', 'string', unique=True, requires=[IS_NOT_EMPTY(), IS_LENGTH(maxsize=14)]),
    Field('long_url', 'string', requires=[IS_NOT_EMPTY(), IS_URL()]),
    Field('category_id', 'reference categories'),
    Field('title', 'string'),
    Field('description', 'text'),
    Field('is_active', 'boolean', default=True),
    Field('show_on_frontpage', 'boolean', default=False),
    Field('click_count', 'integer', default=0),
    Field('created_by', 'reference auth_user'),
    Field('created_on', 'datetime', default=datetime.datetime.utcnow),
    Field('expires_on', 'datetime'),
    Field('qr_code', 'upload'),
    format='%(short_code)s'
)

# Analytics table
db.define_table('analytics',
    Field('url_id', 'reference urls'),
    Field('ip_address', 'string', requires=IS_NOT_EMPTY()),
    Field('user_agent', 'text'),
    Field('referer', 'string'),
    Field('country', 'string'),
    Field('city', 'string'),
    Field('latitude', 'double'),
    Field('longitude', 'double'),
    Field('device_type', 'string'),
    Field('browser', 'string'),
    Field('os', 'string'),
    Field('clicked_on', 'datetime', default=datetime.datetime.utcnow),
    Field('response_time_ms', 'integer')
)

# Rate limiting table
db.define_table('rate_limits',
    Field('ip_address', 'string', unique=True, requires=IS_NOT_EMPTY()),
    Field('request_count', 'integer', default=0),
    Field('window_start', 'datetime', default=datetime.datetime.utcnow),
    Field('is_blocked', 'boolean', default=False),
    Field('blocked_until', 'datetime')
)

# Certificate management table
db.define_table('certificates',
    Field('domain', 'string', unique=True, requires=IS_NOT_EMPTY()),
    Field('cert_type', 'string', requires=IS_IN_SET(['self-signed', 'acme'])),
    Field('cert_path', 'string'),
    Field('key_path', 'string'),
    Field('expires_on', 'datetime'),
    Field('last_renewed', 'datetime'),
    Field('auto_renew', 'boolean', default=True),
    Field('created_on', 'datetime', default=datetime.datetime.utcnow)
)

# Settings table for configurable options
db.define_table('settings',
    Field('key', 'string', unique=True, requires=IS_NOT_EMPTY()),
    Field('value', 'text'),
    Field('description', 'text'),
    Field('updated_by', 'reference auth_user'),
    Field('updated_on', 'datetime', default=datetime.datetime.utcnow)
)

# Insert default categories if not exist
if db(db.categories).count() == 0:
    db.categories.insert(name='default', description='Default category')
    db.categories.insert(name='frontpage', description='Links shown on frontpage')
    db.commit()

# Insert default settings
if db(db.settings).count() == 0:
    db.settings.insert(key='rate_limit_per_second', value='10', description='Maximum requests per second per IP')
    db.settings.insert(key='analytics_retention_days', value='90', description='Days to retain analytics data')
    db.settings.insert(key='auto_renew_certs', value='true', description='Automatically renew ACME certificates')
    db.commit()