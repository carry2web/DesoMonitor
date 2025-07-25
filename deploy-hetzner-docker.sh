#!/bin/bash
# DesoMonitor Docker Deployment for Hetzner
# Usage: ./deploy-hetzner-docker.sh <server-ip> <username>

SERVER_IP=$1
USERNAME=${2:-root}

if [ -z "$SERVER_IP" ]; then
    echo "Usage: $0 <server-ip> [username]"
    echo "Example: $0 1.2.3.4 root"
    exit 1
fi

echo "🐳 Deploying DesoMonitor with Docker to Hetzner server $SERVER_IP..."

# Create deployment package
echo "📦 Creating deployment package..."
tar -czf desomonitor-docker.tar.gz \
    Dockerfile \
    deso_monitor_cloud.py \
    deso_sdk.py \
    requirements.txt \
    .env \
    --exclude='__pycache__' \
    --exclude='*.log' \
    --exclude='*.png'

# Copy files to server
echo "📤 Uploading files to server..."
scp desomonitor-docker.tar.gz $USERNAME@$SERVER_IP:/tmp/

# Install Docker and deploy
echo "🔧 Setting up Docker on server..."
ssh $USERNAME@$SERVER_IP << 'EOF'
    # Install Docker
    apt update
    apt install -y docker.io docker-compose
    systemctl start docker
    systemctl enable docker
    
    # Create project directory
    mkdir -p /opt/desomonitor
    cd /opt/desomonitor
    
    # Extract files
    tar -xzf /tmp/desomonitor-docker.tar.gz
    rm /tmp/desomonitor-docker.tar.gz
    
    # Build Docker image
    docker build -t desomonitor:latest .
    
    # Stop existing container if running
    docker stop desomonitor 2>/dev/null || true
    docker rm desomonitor 2>/dev/null || true
    
    # Run container with restart policy
    docker run -d \
        --name desomonitor \
        --restart unless-stopped \
        -v /opt/desomonitor/data:/app/data \
        desomonitor:latest
    
    # Create management script
    cat > /usr/local/bin/desomonitor << 'SCRIPT'
#!/bin/bash
case "$1" in
    start)
        docker start desomonitor
        ;;
    stop)
        docker stop desomonitor
        ;;
    restart)
        docker restart desomonitor
        ;;
    logs)
        docker logs -f desomonitor
        ;;
    status)
        docker ps | grep desomonitor
        ;;
    update)
        cd /opt/desomonitor
        docker stop desomonitor
        docker build -t desomonitor:latest .
        docker rm desomonitor
        docker run -d \
            --name desomonitor \
            --restart unless-stopped \
            -v /opt/desomonitor/data:/app/data \
            desomonitor:latest
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|logs|status|update}"
        exit 1
        ;;
esac
SCRIPT
    chmod +x /usr/local/bin/desomonitor
    
    echo "✅ DesoMonitor deployed with Docker!"
    echo "📊 Status: $(docker ps | grep desomonitor | awk '{print $7}')"
EOF

# Cleanup
rm desomonitor-docker.tar.gz

echo "🎉 Docker deployment complete!"
echo ""
echo "🔧 Management commands:"
echo "   desomonitor start    - Start the service"
echo "   desomonitor stop     - Stop the service"
echo "   desomonitor restart  - Restart the service"
echo "   desomonitor logs     - View live logs"
echo "   desomonitor status   - Check status"
echo "   desomonitor update   - Update to latest code"
echo ""
echo "📱 Connect to server: ssh $USERNAME@$SERVER_IP"
