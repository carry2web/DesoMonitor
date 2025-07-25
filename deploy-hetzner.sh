#!/bin/bash
# DesoMonitor Hetzner Deployment Script
# Usage: ./deploy-hetzner.sh <server-ip> <username>

SERVER_IP=$1
USERNAME=${2:-root}
PROJECT_NAME="DesoMonitor"

if [ -z "$SERVER_IP" ]; then
    echo "Usage: $0 <server-ip> [username]"
    echo "Example: $0 1.2.3.4 root"
    exit 1
fi

echo "🚀 Deploying DesoMonitor to Hetzner server $SERVER_IP..."

# Create deployment package
echo "📦 Creating deployment package..."
tar -czf desomonitor.tar.gz \
    deso_monitor_cloud.py \
    deso_sdk.py \
    requirements.txt \
    .env \
    --exclude='__pycache__' \
    --exclude='*.log' \
    --exclude='*.png'

# Copy files to server
echo "📤 Uploading files to server..."
scp desomonitor.tar.gz $USERNAME@$SERVER_IP:/tmp/

# Install and setup on server
echo "🔧 Setting up on server..."
ssh $USERNAME@$SERVER_IP << 'EOF'
    # Create project directory
    mkdir -p /opt/desomonitor
    cd /opt/desomonitor
    
    # Extract files
    tar -xzf /tmp/desomonitor.tar.gz
    rm /tmp/desomonitor.tar.gz
    
    # Install Python and dependencies
    apt update
    apt install -y python3 python3-pip python3-venv
    
    # Create virtual environment
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    
    # Create systemd service
    cat > /etc/systemd/system/desomonitor.service << 'SERVICE'
[Unit]
Description=DeSo Node Monitor
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/desomonitor
Environment=PATH=/opt/desomonitor/venv/bin
ExecStart=/opt/desomonitor/venv/bin/python deso_monitor_cloud.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE
    
    # Enable and start service
    systemctl daemon-reload
    systemctl enable desomonitor
    systemctl start desomonitor
    
    echo "✅ DesoMonitor deployed and started!"
    echo "📊 Status: $(systemctl is-active desomonitor)"
    echo "📝 Logs: journalctl -u desomonitor -f"
EOF

# Cleanup
rm desomonitor.tar.gz

echo "🎉 Deployment complete!"
echo "📱 Connect to server: ssh $USERNAME@$SERVER_IP"
echo "📊 Check status: systemctl status desomonitor"
echo "📝 View logs: journalctl -u desomonitor -f"
