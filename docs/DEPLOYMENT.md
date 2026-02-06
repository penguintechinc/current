# Deployment Guide

## Quick Start Deployment

1. **Clone the repository**:
```bash
git clone <repository-url>
cd shorturl
```

2. **Configure environment**:
```bash
cp .env.example .env
# Edit .env with your domain and settings
```

3. **Start with Docker Compose**:
```bash
docker-compose up -d
```

4. **Access admin portal**:
   - URL: https://your-domain.com:9443
   - Default login: admin@localhost.local / admin123

## Production Deployment

### Prerequisites
- Docker and Docker Compose
- Domain name pointing to your server
- Ports 80, 443, and 9443 available

### Step-by-step Production Setup

1. **Server Preparation**:
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt install docker-compose-plugin
```

2. **Application Setup**:
```bash
# Clone repository
git clone <repository-url>
cd shorturl

# Configure production environment
cp .env.example .env
```

3. **Configure .env for production**:
```env
# Production domain
DOMAIN=shorturl.yourdomain.com
ADMIN_EMAIL=admin@yourdomain.com

# Strong secret key
SECRET_KEY=your-very-secure-random-key-here

# Database (optional - defaults to SQLite)
DB_TYPE=postgresql
DB_CONNECTION=user:password@db-host:5432/shorturl_db

# Rate limiting
RATE_LIMIT_PER_SECOND=20
```

4. **Start services**:
```bash
# Create data directories
mkdir -p data logs letsencrypt

# Start application
docker-compose up -d

# Check logs
docker-compose logs -f shorturl
```

5. **SSL Certificate Setup**:

   **Option A: Let's Encrypt (Recommended)**
   - Login to admin portal: https://your-domain.com:9443
   - Go to Certificate Management
   - Click "Request ACME Certificate"
   - Follow the prompts

   **Option B: Custom Certificate**
   ```bash
   # Copy your certificates to:
   ./letsencrypt/live/your-domain.com/fullchain.pem
   ./letsencrypt/live/your-domain.com/privkey.pem
   ```

6. **First Login**:
   - Access: https://your-domain.com:9443
   - Login: admin@localhost.local / admin123
   - **Immediately change the password!**

## Database Options

### SQLite (Default)
Best for small to medium deployments:
```env
DB_TYPE=sqlite
DB_CONNECTION=/var/data/current/db.sqlite
```

### PostgreSQL (Recommended for Production)
```env
DB_TYPE=postgresql
DB_CONNECTION=username:password@host:5432/database
```

Add PostgreSQL to docker-compose.yml:
```yaml
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: shorturl
      POSTGRES_USER: shorturl
      POSTGRES_PASSWORD: secure_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - shorturl-network

volumes:
  postgres_data:
```

### MySQL
```env
DB_TYPE=mysql
DB_CONNECTION=username:password@host:3306/database
```

## Scaling and Performance

### Horizontal Scaling
Deploy multiple instances behind a load balancer:

1. **External Database**: Use PostgreSQL or MySQL
2. **Shared Storage**: Use network storage for `/var/data/current`
3. **Load Balancer**: Configure nginx or HAProxy

### Performance Tuning

1. **Database Optimizations**:
   - Index frequently queried columns
   - Regular cleanup of old analytics data
   - Connection pooling

2. **Redis Configuration**:
   ```env
   REDIS_URL=redis://redis-cluster:6379/0
   ```

3. **Resource Limits**:
   ```yaml
   # docker-compose.yml
   services:
     shorturl:
       deploy:
         resources:
           limits:
             memory: 1G
             cpus: '0.5'
   ```

## Monitoring

### Health Checks
```bash
# Application health
curl https://your-domain.com:9443/healthz

# Prometheus metrics
curl https://your-domain.com:9443/metrics
```

### Log Management
```bash
# View logs
docker-compose logs shorturl

# Persistent logging
mkdir -p /var/log/shorturl
# Logs are automatically stored in ./logs/
```

### Backup Strategy

1. **Database Backup** (if using external DB):
```bash
# PostgreSQL
pg_dump shorturl > backup.sql

# MySQL
mysqldump shorturl > backup.sql
```

2. **Application Data**:
```bash
# Backup data directory
tar -czf backup-$(date +%Y%m%d).tar.gz data/ letsencrypt/
```

3. **Automated Backup**:
Add to crontab:
```bash
0 2 * * * cd /path/to/shorturl && tar -czf backup-$(date +\%Y\%m\%d).tar.gz data/
```

## Troubleshooting

### Common Issues

1. **Port Already in Use**:
```bash
# Check what's using the port
sudo netstat -tulpn | grep :80
sudo netstat -tulpn | grep :443

# Stop conflicting services
sudo systemctl stop apache2
sudo systemctl stop nginx
```

2. **Certificate Issues**:
```bash
# Check certificate status
docker-compose exec shorturl ls -la /etc/letsencrypt/live/

# Regenerate self-signed
docker-compose exec shorturl rm -rf /etc/letsencrypt/live/
docker-compose restart shorturl
```

3. **Database Connection Issues**:
```bash
# Check database connectivity
docker-compose exec shorturl python -c "from apps.shorturl.models import db; print(db.executesql('SELECT 1'))"
```

4. **Permission Issues**:
```bash
# Fix data directory permissions
sudo chown -R 1000:1000 data/ logs/
```

### Log Analysis
```bash
# Application logs
docker-compose logs shorturl | grep ERROR

# Access logs (from proxy)
docker-compose logs shorturl | grep "GET\|POST"

# Performance monitoring
docker-compose exec shorturl top
```

## Security Checklist

- [ ] Change default admin password
- [ ] Use strong SECRET_KEY
- [ ] Configure proper SSL certificates
- [ ] Set appropriate rate limits
- [ ] Regular security updates
- [ ] Monitor access logs
- [ ] Backup regularly
- [ ] Use strong database passwords
- [ ] Restrict database network access
- [ ] Configure firewall (only allow 80, 443, 9443)

## Maintenance

### Updates
```bash
# Pull latest images
docker-compose pull

# Restart services
docker-compose up -d

# Cleanup old images
docker image prune -f
```

### Certificate Renewal
Automatic renewal is configured via cron, but you can manually renew:
```bash
docker-compose exec shorturl certbot renew
docker-compose restart shorturl
```

### Database Maintenance
```bash
# Cleanup old analytics (keeps 90 days)
docker-compose exec shorturl python -c "from apps.shorturl.utils.analytics import Analytics; print(f'Deleted {Analytics.cleanup_old_analytics()} records')"
```