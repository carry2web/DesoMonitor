#!/bin/bash
# DesoMonitor Docker Deployment for Hetzner
# Usage: ./deploy-hetzner-docker.sh <server-ip> <username>

SERVER_IP=$1
USERNAME=${2:-root}
PORT=${3:-22}

if [ -z "$SERVER_IP" ]; then
    echo "Usage: $0 <server-ip> [username]"
    echo "Example: $0 1.2.3.4 root"
    exit 1
fi

echo "🐳 Deploying DesoMonitor with Docker to Hetzner server $SERVER_IP..."

# Create deployment package
echo "📦 Creating deployment package..."
tar -czf desomonitor-docker.tar.gz \
    --exclude='__pycache__' \
    --exclude='*.log' \
    --exclude='*.png' \
    Dockerfile \
    deso_monitor_cloud.py \
    deso_sdk.py \
    requirements.txt \
    .env

# Copy files to server
echo "📤 Uploading files to server..."
scp -P 15689 desomonitor-docker.tar.gz $USERNAME@$SERVER_IP:/tmp/

# Install Docker and deploy
echo "🔧 Setting up Docker on server..."
ssh $USERNAME@$SERVER_IP -p $PORT << 'EOF'
    # Install Docker
    sudo apt update
    sudo apt install -y docker.io docker-compose
    sudo systemctl start docker
    sudo systemctl enable docker
    
    # Create project directory
    sudo mkdir -p /opt/desomonitor
    sudo chown "\$(whoami):\$(whoami)" /opt/desomonitor
    cd /opt/desomonitor
    
    # Extract files
    sudo tar -xzf /tmp/desomonitor-docker.tar.gz -C /opt/desomonitor
    sudo rm /tmp/desomonitor-docker.tar.gz
    
    # Build Docker image
    sudo docker build -t desomonitor:latest .
    
    # Stop existing container if running
    sudo docker stop desomonitor 2>/dev/null || true
    sudo docker rm desomonitor 2>/dev/null || true
    
    # Run container with restart policy
    sudo docker run -d \
        --name desomonitor \
        --restart unless-stopped \
        -v /opt/desomonitor/data:/app/data \
        desomonitor:latest
    
    # Create management script
    sudo tee /usr/local/bin/desomonitor > /dev/null << 'SCRIPT'
#!/bin/bash
case "$1" in
    start)
        sudo docker start desomonitor
        ;;
    stop)
        sudo docker stop desomonitor
        ;;
    restart)
        sudo docker restart desomonitor
        ;;
    logs)
        sudo docker logs -f desomonitor
        ;;
    status)
        sudo docker ps | grep desomonitor
        ;;
    update)
        cd /opt/desomonitor
        sudo docker stop desomonitor
        sudo docker build -t desomonitor:latest .
        sudo docker rm desomonitor
        sudo docker run -d \
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
    echo "📊 Status: \$(sudo docker ps | grep desomonitor | awk '{print \$7}')"
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
echo "📱 Connect to server: ssh $USERNAME@$SERVER_IP -p $PORT"
