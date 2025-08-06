# Deployment Guide

This guide provides comprehensive instructions for deploying the HTTP Streamable MCP Server for Microsandbox in various environments.

## Prerequisites

Before deploying the MCP server, ensure you have:

1. **Microsandbox Server**: A running microsandbox server instance
2. **Python 3.8+**: Python runtime environment
3. **Network Access**: Connectivity between MCP server and microsandbox server
4. **Resource Planning**: Adequate CPU, memory, and storage resources

## Quick Deployment

### Local Development

```bash
# 1. Start microsandbox server
./start_msbserver_debug.sh

# 2. Verify microsandbox server health
curl -s http://127.0.0.1:5555/api/v1/health

# 3. Install MCP server dependencies
cd mcp-server
pip install -r requirements.txt

# 4. Start MCP server
python -m mcp_server.main

# 5. Test MCP server
curl http://localhost:8000/
```

### Production Quick Start

```bash
# 1. Set production environment variables
export MCP_SERVER_HOST="0.0.0.0"
export MCP_SERVER_PORT="8080"
export MCP_ENABLE_CORS="false"
export MSB_SERVER_URL="http://microsandbox-server:5555"

# 2. Start with production settings
python -m mcp_server.main --log-level WARNING
```

## Docker Deployment

### Single Container

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy application files
COPY mcp-server/ ./mcp-server/
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user
RUN useradd -m -u 1000 mcp-server && \
    chown -R mcp-server:mcp-server /app
USER mcp-server

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Start server
CMD ["python", "-m", "mcp_server.main"]
```

Build and run:

```bash
# Build image
docker build -t mcp-server:latest .

# Run container
docker run -d \
    --name mcp-server \
    -p 8000:8000 \
    -e MCP_SERVER_HOST=0.0.0.0 \
    -e MSB_SERVER_URL=http://microsandbox:5555 \
    mcp-server:latest
```

### Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  mcp-server:
    build: .
    container_name: mcp-server
    ports:
      - "8000:8000"
    environment:
      MCP_SERVER_HOST: "0.0.0.0"
      MCP_SERVER_PORT: "8000"
      MCP_ENABLE_CORS: "true"
      MSB_SERVER_URL: "http://microsandbox:5555"
      MSB_MAX_SESSIONS: "20"
      MSB_SESSION_TIMEOUT: "3600"
      MSB_DEFAULT_FLAVOR: "medium"
      MSB_LOG_LEVEL: "INFO"
    volumes:
      - ./data/input:/data/input:ro
      - ./data/output:/data/output:rw
      - ./logs:/app/logs:rw
    depends_on:
      - microsandbox
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  microsandbox:
    image: microsandbox:latest
    container_name: microsandbox
    ports:
      - "5555:5555"
    volumes:
      - ./data:/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5555/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  data:
  logs:

networks:
  default:
    name: mcp-network
```

Deploy with Docker Compose:

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f mcp-server

# Scale MCP server (if using load balancer)
docker-compose up -d --scale mcp-server=3

# Stop services
docker-compose down
```

## Kubernetes Deployment

### Basic Deployment

Create `k8s-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-server
  labels:
    app: mcp-server
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mcp-server
  template:
    metadata:
      labels:
        app: mcp-server
    spec:
      containers:
      - name: mcp-server
        image: mcp-server:latest
        ports:
        - containerPort: 8000
        env:
        - name: MCP_SERVER_HOST
          value: "0.0.0.0"
        - name: MCP_SERVER_PORT
          value: "8000"
        - name: MSB_SERVER_URL
          value: "http://microsandbox-service:5555"
        - name: MSB_MAX_SESSIONS
          value: "20"
        - name: MSB_SESSION_TIMEOUT
          value: "3600"
        envFrom:
        - configMapRef:
            name: mcp-server-config
        - secretRef:
            name: mcp-server-secrets
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        volumeMounts:
        - name: data-volume
          mountPath: /data
        - name: logs-volume
          mountPath: /app/logs
      volumes:
      - name: data-volume
        persistentVolumeClaim:
          claimName: mcp-server-data
      - name: logs-volume
        emptyDir: {}

---
apiVersion: v1
kind: Service
metadata:
  name: mcp-server-service
spec:
  selector:
    app: mcp-server
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer

---
apiVersion: v1
kind: ConfigMap
metadata:
  name: mcp-server-config
data:
  MCP_ENABLE_CORS: "false"
  MSB_DEFAULT_FLAVOR: "medium"
  MSB_LOG_LEVEL: "INFO"
  MSB_LOG_FORMAT: "json"

---
apiVersion: v1
kind: Secret
metadata:
  name: mcp-server-secrets
type: Opaque
data:
  MSB_API_KEY: <base64-encoded-api-key>

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: mcp-server-data
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 10Gi
```

Deploy to Kubernetes:

```bash
# Apply deployment
kubectl apply -f k8s-deployment.yaml

# Check deployment status
kubectl get deployments
kubectl get pods
kubectl get services

# View logs
kubectl logs -f deployment/mcp-server

# Scale deployment
kubectl scale deployment mcp-server --replicas=5

# Update deployment
kubectl set image deployment/mcp-server mcp-server=mcp-server:v2.0.0
```

### Helm Chart

Create a Helm chart for easier management:

```bash
# Create Helm chart
helm create mcp-server-chart

# Edit values.yaml
cat > mcp-server-chart/values.yaml << EOF
replicaCount: 3

image:
  repository: mcp-server
  tag: latest
  pullPolicy: IfNotPresent

service:
  type: LoadBalancer
  port: 80
  targetPort: 8000

ingress:
  enabled: true
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: mcp-server.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: mcp-server-tls
      hosts:
        - mcp-server.example.com

config:
  mcpServer:
    host: "0.0.0.0"
    port: 8000
    enableCors: false
  microsandbox:
    serverUrl: "http://microsandbox-service:5555"
    maxSessions: 20
    sessionTimeout: 3600
    defaultFlavor: "medium"

resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 250m
    memory: 256Mi

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 10
  targetCPUUtilizationPercentage: 80

persistence:
  enabled: true
  size: 10Gi
  accessMode: ReadWriteMany
EOF

# Install with Helm
helm install mcp-server ./mcp-server-chart

# Upgrade
helm upgrade mcp-server ./mcp-server-chart

# Uninstall
helm uninstall mcp-server
```

## Systemd Service

For traditional Linux deployments, create a systemd service:

Create `/etc/systemd/system/mcp-server.service`:

```ini
[Unit]
Description=MCP Server for Microsandbox
Documentation=https://github.com/microsandbox/microsandbox/tree/main/mcp-server
After=network.target microsandbox.service
Wants=microsandbox.service

[Service]
Type=simple
User=mcp-server
Group=mcp-server
WorkingDirectory=/opt/mcp-server
Environment=PATH=/opt/mcp-server/venv/bin
Environment=MCP_SERVER_HOST=127.0.0.1
Environment=MCP_SERVER_PORT=8000
Environment=MCP_ENABLE_CORS=false
Environment=MSB_SERVER_URL=http://127.0.0.1:5555
Environment=MSB_MAX_SESSIONS=20
Environment=MSB_SESSION_TIMEOUT=3600
Environment=MSB_DEFAULT_FLAVOR=medium
Environment=MSB_LOG_LEVEL=INFO
EnvironmentFile=-/etc/mcp-server/environment
ExecStart=/opt/mcp-server/venv/bin/python -m mcp_server.main
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=mcp-server

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/mcp-server/logs /tmp

[Install]
WantedBy=multi-user.target
```

Setup and manage the service:

```bash
# Create user and directories
sudo useradd -r -s /bin/false mcp-server
sudo mkdir -p /opt/mcp-server /etc/mcp-server
sudo chown mcp-server:mcp-server /opt/mcp-server

# Install application
sudo cp -r mcp-server/* /opt/mcp-server/
sudo python -m venv /opt/mcp-server/venv
sudo /opt/mcp-server/venv/bin/pip install -r /opt/mcp-server/requirements.txt
sudo chown -R mcp-server:mcp-server /opt/mcp-server

# Create environment file
sudo tee /etc/mcp-server/environment << EOF
MCP_SERVER_HOST=0.0.0.0
MCP_SERVER_PORT=8080
MSB_SERVER_URL=http://127.0.0.1:5555
MSB_MAX_SESSIONS=50
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable mcp-server
sudo systemctl start mcp-server

# Check status
sudo systemctl status mcp-server
sudo journalctl -u mcp-server -f
```

## Reverse Proxy Setup

### Nginx

Create `/etc/nginx/sites-available/mcp-server`:

```nginx
upstream mcp_server {
    server 127.0.0.1:8000;
    # Add more servers for load balancing
    # server 127.0.0.1:8001;
    # server 127.0.0.1:8002;
}

server {
    listen 80;
    server_name mcp-server.example.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name mcp-server.example.com;
    
    # SSL configuration
    ssl_certificate /etc/letsencrypt/live/mcp-server.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mcp-server.example.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload";
    
    # Logging
    access_log /var/log/nginx/mcp-server.access.log;
    error_log /var/log/nginx/mcp-server.error.log;
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=mcp_limit:10m rate=10r/s;
    limit_req zone=mcp_limit burst=20 nodelay;
    
    location / {
        proxy_pass http://mcp_server;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Buffer settings
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        
        # Health check
        proxy_next_upstream error timeout invalid_header http_500 http_502 http_503;
    }
    
    # Health check endpoint
    location /health {
        access_log off;
        proxy_pass http://mcp_server/;
        proxy_set_header Host $host;
    }
}
```

Enable the configuration:

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/mcp-server /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Get SSL certificate
sudo certbot --nginx -d mcp-server.example.com
```

### Apache

Create `/etc/apache2/sites-available/mcp-server.conf`:

```apache
<VirtualHost *:80>
    ServerName mcp-server.example.com
    Redirect permanent / https://mcp-server.example.com/
</VirtualHost>

<VirtualHost *:443>
    ServerName mcp-server.example.com
    
    # SSL Configuration
    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/mcp-server.example.com/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/mcp-server.example.com/privkey.pem
    
    # Security headers
    Header always set X-Frame-Options DENY
    Header always set X-Content-Type-Options nosniff
    Header always set X-XSS-Protection "1; mode=block"
    Header always set Strict-Transport-Security "max-age=63072000; includeSubDomains; preload"
    
    # Logging
    CustomLog /var/log/apache2/mcp-server.access.log combined
    ErrorLog /var/log/apache2/mcp-server.error.log
    
    # Proxy configuration
    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:8000/
    ProxyPassReverse / http://127.0.0.1:8000/
    
    # Set headers
    ProxyPassReverse / http://127.0.0.1:8000/
    ProxyPassReverseMatch ^/(.*) http://127.0.0.1:8000/$1
</VirtualHost>
```

Enable the configuration:

```bash
# Enable modules and site
sudo a2enmod ssl proxy proxy_http headers
sudo a2ensite mcp-server
sudo systemctl reload apache2

# Get SSL certificate
sudo certbot --apache -d mcp-server.example.com
```

## Monitoring and Logging

### Prometheus Metrics

Add metrics endpoint to the MCP server (future enhancement):

```python
# Add to server.py
from prometheus_client import Counter, Histogram, generate_latest

# Metrics
REQUEST_COUNT = Counter('mcp_requests_total', 'Total MCP requests', ['method', 'status'])
REQUEST_DURATION = Histogram('mcp_request_duration_seconds', 'Request duration')

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")
```

### Log Aggregation

Configure log forwarding to centralized logging:

```bash
# Fluentd configuration
<source>
  @type tail
  path /var/log/mcp-server/*.log
  pos_file /var/log/fluentd/mcp-server.log.pos
  tag mcp-server
  format json
</source>

<match mcp-server>
  @type elasticsearch
  host elasticsearch.example.com
  port 9200
  index_name mcp-server
</match>
```

### Health Monitoring

Create monitoring scripts:

```bash
#!/bin/bash
# health-check.sh

MCP_URL="http://localhost:8000"
MSB_URL="http://localhost:5555/api/v1/health"

# Check MCP server
if curl -f -s "$MCP_URL" > /dev/null; then
    echo "MCP server: OK"
else
    echo "MCP server: FAILED"
    exit 1
fi

# Check microsandbox server
if curl -f -s "$MSB_URL" > /dev/null; then
    echo "Microsandbox server: OK"
else
    echo "Microsandbox server: FAILED"
    exit 1
fi

echo "All services: OK"
```

## Security Considerations

### Network Security

1. **Firewall Rules**:
   ```bash
   # Allow only necessary ports
   sudo ufw allow 22/tcp    # SSH
   sudo ufw allow 80/tcp    # HTTP
   sudo ufw allow 443/tcp   # HTTPS
   sudo ufw deny 8000/tcp   # Block direct access to MCP server
   sudo ufw enable
   ```

2. **Network Segmentation**: Place MCP server and microsandbox server in isolated network segments

3. **VPN Access**: Require VPN for administrative access

### Application Security

1. **Authentication**: Implement authentication for production deployments
2. **Rate Limiting**: Configure rate limiting to prevent abuse
3. **Input Validation**: Ensure all inputs are properly validated
4. **Resource Limits**: Set appropriate resource limits to prevent DoS

### Container Security

1. **Non-root User**: Run containers as non-root user
2. **Read-only Filesystem**: Use read-only root filesystem where possible
3. **Security Scanning**: Regularly scan container images for vulnerabilities
4. **Secrets Management**: Use proper secrets management for sensitive data

## Troubleshooting Deployment

### Common Issues

1. **Port Conflicts**:
   ```bash
   # Check port usage
   sudo netstat -tlnp | grep :8000
   sudo lsof -i :8000
   ```

2. **Permission Issues**:
   ```bash
   # Fix ownership
   sudo chown -R mcp-server:mcp-server /opt/mcp-server
   sudo chmod +x /opt/mcp-server/venv/bin/python
   ```

3. **Network Connectivity**:
   ```bash
   # Test connectivity
   curl -v http://microsandbox-server:5555/api/v1/health
   telnet microsandbox-server 5555
   ```

4. **Resource Exhaustion**:
   ```bash
   # Monitor resources
   htop
   df -h
   free -h
   ```

### Debug Mode

Enable debug logging for troubleshooting:

```bash
export MSB_LOG_LEVEL=DEBUG
python -m mcp_server.main --log-level DEBUG
```

### Log Analysis

Common log patterns to watch for:

```bash
# Connection errors
grep "Connection refused" /var/log/mcp-server/mcp-server.log

# Resource limit errors
grep "Resource limit exceeded" /var/log/mcp-server/mcp-server.log

# Authentication failures
grep "Authentication failed" /var/log/mcp-server/mcp-server.log

# High error rates
grep "ERROR" /var/log/mcp-server/mcp-server.log | wc -l
```

## Performance Tuning

### Server Tuning

1. **Worker Processes**: Configure appropriate number of worker processes
2. **Connection Pooling**: Optimize connection pool settings
3. **Caching**: Implement caching where appropriate
4. **Resource Limits**: Tune resource limits based on workload

### Database Tuning

If using a database for session storage:

1. **Connection Pooling**: Configure database connection pooling
2. **Indexing**: Ensure proper database indexing
3. **Query Optimization**: Optimize database queries
4. **Backup Strategy**: Implement regular database backups

### Monitoring Performance

Set up performance monitoring:

1. **Response Times**: Monitor API response times
2. **Throughput**: Track requests per second
3. **Resource Usage**: Monitor CPU, memory, and disk usage
4. **Error Rates**: Track error rates and types

This deployment guide provides comprehensive instructions for deploying the MCP server in various environments. Choose the deployment method that best fits your infrastructure and requirements.