#!/bin/bash
# Deploy DesoMonitor with Enhanced Dual-Metric Monitoring to Hetzner Server
# This script updates the running Docker container with the latest code from GitHub

set -e  # Exit on any error

echo "🚀 Starting deployment of enhanced DesoMonitor to Hetzner server..."

# Configuration
SERVER_IP="159.69.139.36"  # Your Hetzner server IP
SSH_USER="carry"
SSH_PORT="15689"
CONTAINER_NAME="desomonitor"
IMAGE_NAME="desomonitor:latest"
GITHUB_REPO="https://github.com/carry2web/DesoMonitor.git"

echo "📡 Connecting to Hetzner server: $SSH_USER@$SERVER_IP:$SSH_PORT"

# Deploy via SSH
ssh -p $SSH_PORT $SSH_USER@$SERVER_IP << 'ENDSSH'
set -e

echo "🔄 Updating DesoMonitor on Hetzner server..."

# Stop and remove existing container
echo "🛑 Stopping existing DesoMonitor container..."
docker stop desomonitor 2>/dev/null || echo "Container not running"
docker rm desomonitor 2>/dev/null || echo "Container not found"

# Remove old image
echo "🗑️ Removing old Docker image..."
docker rmi desomonitor:latest 2>/dev/null || echo "Image not found"

# Clone/update repository
echo "📥 Fetching latest code from GitHub..."
if [ -d "DesoMonitor" ]; then
    cd DesoMonitor
    git pull origin main
else
    git clone https://github.com/carry2web/DesoMonitor.git
    cd DesoMonitor
fi

# Build new Docker image
echo "🏗️ Building new Docker image with dual-metric monitoring..."
docker build -t desomonitor:latest .

# Run new container with enhanced monitoring
echo "🚀 Starting enhanced DesoMonitor container..."
docker run -d \
    --name desomonitor \
    --restart unless-stopped \
    -v /home/carry/DesoMonitor/data:/app/data \
    desomonitor:latest

# Check if container is running
echo "✅ Checking container status..."
sleep 5
docker ps | grep desomonitor

echo "📊 Container logs (last 20 lines):"
docker logs --tail 20 desomonitor

echo "🎉 Enhanced DesoMonitor deployment complete!"
echo "📈 New features:"
echo "   - Dual-metric monitoring (POST vs CONFIRMATION speed)"
echo "   - Enhanced visualization with horizontal bar charts"
echo "   - Improved error handling and code readability"
echo ""
echo "🔍 Monitor logs with: docker logs -f desomonitor"
echo "📊 Check status with: docker ps | grep desomonitor"

ENDSSH

echo "✅ Deployment to Hetzner server completed successfully!"
echo ""
echo "🎯 Enhanced DesoMonitor is now running with:"
echo "   ✓ Dual POST/CONFIRMATION speed measurements"
echo "   ✓ Improved horizontal bar gauge visualization"
echo "   ✓ Enhanced error handling and logging"
echo "   ✓ Community feedback integration"
echo ""
echo "📱 Monitor the enhanced system:"
echo "   • SSH: ssh -p $SSH_PORT $SSH_USER@$SERVER_IP"
echo "   • Logs: docker logs -f desomonitor" 
echo "   • Status: docker ps | grep desomonitor"
