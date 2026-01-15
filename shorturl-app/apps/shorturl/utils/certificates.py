import datetime
import os
import ssl
import subprocess
import sys
from pathlib import Path

import OpenSSL.crypto

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
)
from settings import ADMIN_EMAIL, CERT_PATH, DOMAIN

from apps.shorturl.models import db


class CertificateManager:

    def __init__(self):
        self.cert_path = CERT_PATH
        self.domain = DOMAIN
        self.admin_email = ADMIN_EMAIL

    def generate_self_signed(self):
        """Generate a self-signed certificate"""
        cert_dir = Path(self.cert_path)
        cert_dir.mkdir(parents=True, exist_ok=True)

        key_path = cert_dir / "privkey.pem"
        cert_path = cert_dir / "fullchain.pem"

        # Generate key
        key = OpenSSL.crypto.PKey()
        key.generate_key(OpenSSL.crypto.TYPE_RSA, 2048)

        # Generate certificate
        cert = OpenSSL.crypto.X509()
        cert.get_subject().C = "US"
        cert.get_subject().ST = "State"
        cert.get_subject().L = "City"
        cert.get_subject().O = "Organization"
        cert.get_subject().CN = self.domain

        cert.set_serial_number(1000)
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(365 * 24 * 60 * 60)  # 1 year

        cert.set_issuer(cert.get_subject())
        cert.set_pubkey(key)
        cert.sign(key, "sha256")

        # Write files
        with open(key_path, "wb") as f:
            f.write(OpenSSL.crypto.dump_privatekey(OpenSSL.crypto.FILETYPE_PEM, key))

        with open(cert_path, "wb") as f:
            f.write(OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_PEM, cert))

        # Update database
        db.certificates.insert(
            domain=self.domain,
            cert_type="self-signed",
            cert_path=str(cert_path),
            key_path=str(key_path),
            expires_on=datetime.datetime.utcnow() + datetime.timedelta(days=365),
        )
        db.commit()

        return True

    def request_acme_certificate(self):
        """Request a certificate from Let's Encrypt using certbot"""
        try:
            # Run certbot
            cmd = [
                "certbot",
                "certonly",
                "--standalone",
                "--non-interactive",
                "--agree-tos",
                "--email",
                self.admin_email,
                "-d",
                self.domain,
                "--cert-path",
                self.cert_path,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                # Update database
                cert_path = f"/etc/letsencrypt/live/{self.domain}/fullchain.pem"
                key_path = f"/etc/letsencrypt/live/{self.domain}/privkey.pem"

                # Get certificate expiry
                with open(cert_path, "r") as f:
                    cert_data = f.read()
                    cert = OpenSSL.crypto.load_certificate(
                        OpenSSL.crypto.FILETYPE_PEM, cert_data
                    )
                    expires = datetime.datetime.strptime(
                        cert.get_notAfter().decode("ascii"), "%Y%m%d%H%M%SZ"
                    )

                db.certificates.update_or_insert(
                    db.certificates.domain == self.domain,
                    domain=self.domain,
                    cert_type="acme",
                    cert_path=cert_path,
                    key_path=key_path,
                    expires_on=expires,
                    last_renewed=datetime.datetime.utcnow(),
                    auto_renew=True,
                )
                db.commit()

                return True, "Certificate obtained successfully"
            else:
                return False, result.stderr

        except Exception as e:
            return False, str(e)

    def renew_certificate(self):
        """Renew ACME certificate"""
        try:
            cmd = ["certbot", "renew", "--quiet"]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                # Update last renewed time
                db(db.certificates.domain == self.domain).update(
                    last_renewed=datetime.datetime.utcnow()
                )
                db.commit()
                return True
            return False

        except Exception as e:
            return False

    def check_expiry(self):
        """Check if certificate is expiring soon"""
        cert_record = db(db.certificates.domain == self.domain).select().first()

        if not cert_record:
            return None

        days_until_expiry = (cert_record.expires_on - datetime.datetime.utcnow()).days

        if days_until_expiry < 30:
            if cert_record.cert_type == "acme" and cert_record.auto_renew:
                self.renew_certificate()

        return days_until_expiry

    def get_certificate_info(self):
        """Get current certificate information"""
        cert_record = db(db.certificates.domain == self.domain).select().first()

        if not cert_record:
            return None

        return {
            "domain": cert_record.domain,
            "type": cert_record.cert_type,
            "expires_on": cert_record.expires_on,
            "days_until_expiry": (
                cert_record.expires_on - datetime.datetime.utcnow()
            ).days,
            "auto_renew": cert_record.auto_renew,
        }
