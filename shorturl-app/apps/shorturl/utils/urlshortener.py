import string
import random
import qrcode
from io import BytesIO
import base64
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
from apps.shorturl.models import db
from apps.shorturl.utils.security import Security
from settings import DEFAULT_SHORT_LENGTH, MAX_CUSTOM_LENGTH, RESERVED_PATHS, DOMAIN

class URLShortener:
    
    @staticmethod
    def generate_short_code(length=DEFAULT_SHORT_LENGTH):
        """Generate a random short code"""
        chars = string.ascii_letters + string.digits
        
        # Try up to 10 times to generate a unique code
        for _ in range(10):
            code = ''.join(random.choice(chars) for _ in range(length))
            
            # Check if code already exists
            if db(db.urls.short_code == code).count() == 0:
                return code
                
        # If still no unique code, increase length
        return URLShortener.generate_short_code(length + 1)
    
    @staticmethod
    def create_short_url(long_url, user_id, custom_code=None, category_id=None, 
                        title=None, description=None, show_on_frontpage=False,
                        expires_on=None):
        """Create a new short URL"""
        
        # Validate long URL
        if not Security.validate_url(long_url):
            return None, "Invalid or unsafe URL"
            
        # Handle custom code
        if custom_code:
            # Validate custom code
            if not Security.validate_short_code(custom_code):
                return None, "Invalid short code format"
                
            if len(custom_code) > MAX_CUSTOM_LENGTH:
                return None, f"Custom code must be {MAX_CUSTOM_LENGTH} characters or less"
                
            if custom_code.lower() in RESERVED_PATHS:
                return None, "This short code is reserved"
                
            # Check if already exists
            if db(db.urls.short_code == custom_code).count() > 0:
                return None, "Short code already exists"
                
            short_code = custom_code
        else:
            # Generate random code
            short_code = URLShortener.generate_short_code()
            
        # Generate QR code
        qr_data = URLShortener.generate_qr_code(short_code)
        
        # Insert into database
        url_id = db.urls.insert(
            short_code=short_code,
            long_url=long_url,
            category_id=category_id,
            title=Security.sanitize_input(title) if title else None,
            description=Security.sanitize_input(description) if description else None,
            is_active=True,
            show_on_frontpage=show_on_frontpage,
            created_by=user_id,
            expires_on=expires_on,
            qr_code=qr_data
        )
        db.commit()
        
        return db.urls[url_id], None
    
    @staticmethod
    def generate_qr_code(short_code):
        """Generate QR code for short URL"""
        url = f"https://{DOMAIN}/{short_code}"
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to bytes
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()
    
    @staticmethod
    def get_qr_code_base64(short_code):
        """Get QR code as base64 string for display"""
        url_record = db(db.urls.short_code == short_code).select().first()
        
        if url_record and url_record.qr_code:
            return base64.b64encode(url_record.qr_code).decode('utf-8')
            
        return None
    
    @staticmethod
    def update_short_url(url_id, user_id, **kwargs):
        """Update an existing short URL"""
        url_record = db(db.urls.id == url_id).select().first()
        
        if not url_record:
            return None, "URL not found"
            
        # Check permissions
        user = db(db.auth_user.id == user_id).select().first()
        if user.role not in ['admin', 'contributor'] and url_record.created_by != user_id:
            return None, "Permission denied"
            
        # Build update dict
        update_data = {}
        
        if 'long_url' in kwargs:
            if not Security.validate_url(kwargs['long_url']):
                return None, "Invalid or unsafe URL"
            update_data['long_url'] = kwargs['long_url']
            
        if 'category_id' in kwargs:
            update_data['category_id'] = kwargs['category_id']
            
        if 'title' in kwargs:
            update_data['title'] = Security.sanitize_input(kwargs['title'])
            
        if 'description' in kwargs:
            update_data['description'] = Security.sanitize_input(kwargs['description'])
            
        if 'show_on_frontpage' in kwargs:
            update_data['show_on_frontpage'] = kwargs['show_on_frontpage']
            
        if 'is_active' in kwargs:
            update_data['is_active'] = kwargs['is_active']
            
        if 'expires_on' in kwargs:
            update_data['expires_on'] = kwargs['expires_on']
            
        # Update database
        db(db.urls.id == url_id).update(**update_data)
        db.commit()
        
        return db.urls[url_id], None
    
    @staticmethod
    def delete_short_url(url_id, user_id):
        """Delete a short URL (soft delete)"""
        url_record = db(db.urls.id == url_id).select().first()
        
        if not url_record:
            return False, "URL not found"
            
        # Check permissions
        user = db(db.auth_user.id == user_id).select().first()
        if user.role != 'admin' and url_record.created_by != user_id:
            return False, "Permission denied"
            
        # Soft delete
        db(db.urls.id == url_id).update(is_active=False)
        db.commit()
        
        return True, None
    
    @staticmethod
    def get_url_by_short_code(short_code):
        """Get URL record by short code"""
        return db((db.urls.short_code == short_code) & 
                 (db.urls.is_active == True)).select().first()
    
    @staticmethod
    def search_urls(query, user_id, category_id=None):
        """Search URLs"""
        user = db(db.auth_user.id == user_id).select().first()
        
        if user.role == 'reporter':
            return []
            
        # Build query
        search_query = (db.urls.is_active == True)
        
        if query:
            search_query &= (
                db.urls.short_code.contains(query) |
                db.urls.long_url.contains(query) |
                db.urls.title.contains(query) |
                db.urls.description.contains(query)
            )
            
        if category_id:
            search_query &= (db.urls.category_id == category_id)
            
        # Apply role-based filtering
        if user.role == 'viewer':
            # Viewers can see all active URLs
            pass
        elif user.role == 'contributor':
            # Contributors can see all URLs
            pass
        elif user.role == 'admin':
            # Admins can see everything
            search_query = db.urls.id > 0  # Reset to see all including inactive
            
        return db(search_query).select(orderby=~db.urls.created_on)
    
    @staticmethod
    def get_frontpage_urls():
        """Get URLs marked for frontpage display"""
        return db((db.urls.is_active == True) & 
                 (db.urls.show_on_frontpage == True)).select(
                     orderby=~db.urls.click_count
                 )