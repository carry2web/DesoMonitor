#!/bin/bash

# Azure Container Instances Deployment Script
# Prerequisites: Azure CLI installed and logged in

set -e

# Configuration
RESOURCE_GROUP="desomonitor-rg"
CONTAINER_NAME="desomonitor"
LOCATION="eastus"
IMAGE_NAME="desomonitor:latest"

echo "🚀 Deploying DesoMonitor to Azure Container Instances"

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI not found. Please install: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

# Check if logged in
if ! az account show &> /dev/null; then
    echo "❌ Not logged into Azure. Run: az login"
    exit 1
fi

echo "✅ Azure CLI ready"

# Create resource group
echo "📦 Creating resource group: $RESOURCE_GROUP"
az group create --name $RESOURCE_GROUP --location $LOCATION

# Build and run locally first (optional test)
echo "🔨 Building Docker image..."
docker build -t $IMAGE_NAME .

# Prompt for environment variables
echo "🔐 Please provide your DeSo credentials:"
read -p "DESO_PUBLIC_KEY: " DESO_PUBLIC_KEY
read -s -p "DESO_SEED_HEX: " DESO_SEED_HEX
echo

# Deploy to Azure Container Instances
echo "☁️ Deploying to Azure Container Instances..."
az container create \
    --resource-group $RESOURCE_GROUP \
    --name $CONTAINER_NAME \
    --image $IMAGE_NAME \
    --cpu 1 \
    --memory 1 \
    --restart-policy Always \
    --environment-variables \
        DESO_PUBLIC_KEY="$DESO_PUBLIC_KEY" \
        DESO_SEED_HEX="$DESO_SEED_HEX" \
    --location $LOCATION

echo "✅ Deployment complete!"

# Show container status
echo "📊 Container status:"
az container show --resource-group $RESOURCE_GROUP --name $CONTAINER_NAME --query "{FQDN:ipAddress.fqdn,ProvisioningState:provisioningState}" --out table

# Show logs command
echo "📋 To view logs, run:"
echo "az container logs --resource-group $RESOURCE_GROUP --name $CONTAINER_NAME --follow"

# Show cleanup command
echo "🧹 To delete resources, run:"
echo "az group delete --name $RESOURCE_GROUP --yes --no-wait"
