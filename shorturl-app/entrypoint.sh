#!/bin/bash

# Generate self-signed certificate if not exists
if [ ! -f /etc/letsencrypt/live/${DOMAIN}/fullchain.pem ]; then
    mkdir -p /etc/letsencrypt/live/${DOMAIN}
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout /etc/letsencrypt/live/${DOMAIN}/privkey.pem \
        -out /etc/letsencrypt/live/${DOMAIN}/fullchain.pem \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=${DOMAIN}"
fi

# Setup cron for certificate renewal
echo "0 2 * * * /usr/bin/certbot renew --quiet" | crontab -
service cron start

# Start the application
exec python /app/main.py