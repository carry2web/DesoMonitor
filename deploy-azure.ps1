# Azure Container Instances Deployment (PowerShell)
# Prerequisites: Azure CLI installed and logged in

param(
    [string]$ResourceGroup = "desomonitor-rg",
    [string]$ContainerName = "desomonitor", 
    [string]$Location = "eastus",
    [string]$ImageName = "desomonitor:latest"
)

Write-Host "🚀 Deploying DesoMonitor to Azure Container Instances" -ForegroundColor Green

# Check if Azure CLI is installed
try {
    az --version | Out-Null
    Write-Host "✅ Azure CLI ready" -ForegroundColor Green
} catch {
    Write-Host "❌ Azure CLI not found. Please install: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli" -ForegroundColor Red
    exit 1
}

# Check if logged in
try {
    az account show | Out-Null
    Write-Host "✅ Logged into Azure" -ForegroundColor Green
} catch {
    Write-Host "❌ Not logged into Azure. Run: az login" -ForegroundColor Red
    exit 1
}

# Create resource group
Write-Host "📦 Creating resource group: $ResourceGroup" -ForegroundColor Yellow
az group create --name $ResourceGroup --location $Location

# Build Docker image
Write-Host "🔨 Building Docker image..." -ForegroundColor Yellow
docker build -t $ImageName .

# Get environment variables
Write-Host "🔐 Please provide your DeSo credentials:" -ForegroundColor Yellow
$DESO_PUBLIC_KEY = Read-Host "DESO_PUBLIC_KEY"
$DESO_SEED_HEX = Read-Host "DESO_SEED_HEX" -AsSecureString
$DESO_SEED_HEX_Plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($DESO_SEED_HEX))

# Deploy to Azure Container Instances
Write-Host "☁️ Deploying to Azure Container Instances..." -ForegroundColor Yellow
az container create `
    --resource-group $ResourceGroup `
    --name $ContainerName `
    --image $ImageName `
    --cpu 1 `
    --memory 1 `
    --restart-policy Always `
    --environment-variables `
        DESO_PUBLIC_KEY="$DESO_PUBLIC_KEY" `
        DESO_SEED_HEX="$DESO_SEED_HEX_Plain" `
    --location $Location

Write-Host "✅ Deployment complete!" -ForegroundColor Green

# Show container status
Write-Host "📊 Container status:" -ForegroundColor Yellow
az container show --resource-group $ResourceGroup --name $ContainerName --query "{FQDN:ipAddress.fqdn,ProvisioningState:provisioningState}" --out table

# Show useful commands
Write-Host "`n📋 Useful commands:" -ForegroundColor Cyan
Write-Host "View logs: az container logs --resource-group $ResourceGroup --name $ContainerName --follow" -ForegroundColor White
Write-Host "Delete resources: az group delete --name $ResourceGroup --yes --no-wait" -ForegroundColor White
