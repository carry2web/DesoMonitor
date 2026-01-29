# DesoMonitor Azure Deployment Guide

## Option 1: Azure Container Instances (Recommended for simplicity)

### Step 1: Create Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create directory for logs and graphs
RUN mkdir -p /app/data

# Environment variables will be set in Azure
ENV PYTHONUNBUFFERED=1

# Run the monitor
CMD ["python", "deso_monitor.py"]
```

### Step 2: Create requirements.txt
```
requests==2.31.0
python-dotenv==1.0.0
matplotlib==3.7.2
numpy==1.24.3
```

### Step 3: Build and Deploy
```bash
# Build container
docker build -t desomonitor .

# Push to Azure Container Registry (ACR)
az acr create --resource-group myResourceGroup --name myregistry --sku Basic
az acr login --name myregistry
docker tag desomonitor myregistry.azurecr.io/desomonitor:latest
docker push myregistry.azurecr.io/desomonitor:latest

# Create container instance
az container create \
    --resource-group myResourceGroup \
    --name desomonitor \
    --image myregistry.azurecr.io/desomonitor:latest \
    --cpu 1 \
    --memory 1 \
    --restart-policy Always \
    --environment-variables \
        DESO_PUBLIC_KEY="your_public_key" \
        DESO_SEED_HEX="your_seed_hex"
```

## Option 2: Azure App Service (Web Apps)

**Free tier: F1 (1GB RAM, 1GB storage)**

### Requirements:
- Remove matplotlib GUI backends (already done with 'Agg')
- Handle file storage differently (Azure provides temp storage)

### Deploy steps:
1. Create App Service Plan (Free F1)
2. Create Web App (Python 3.11)
3. Deploy via Git or ZIP
4. Set environment variables in Azure portal

## Option 3: Azure Functions (Serverless)

**Free tier: 1M requests/month + 400,000 GB-s**

### Challenges:
- 10-minute execution limit (need to break into smaller functions)
- Stateless (need external storage for measurements)

## Option 4: Azure VM (Free for 12 months)

**Free tier: B1S (1 vCPU, 1GB RAM)**

### Benefits:
- Full control
- Can run exactly as-is
- SSH access

## Recommended: Container Instances

### Why ACI is best for DesoMonitor:
✅ **Always running** (restart-policy: Always)
✅ **Simple deployment** (single container)
✅ **Cost effective** (pay per second)
✅ **No modifications needed** (runs your code as-is)
✅ **Environment variables** (secure credential storage)

### Estimated costs (after free tier):
- **Free tier**: ~1 million vCPU-seconds/month FREE
- **Paid**: ~$30-50/month for 24/7 operation

## Alternative Free Options

### GitHub Actions (Creative approach)
```yaml
# .github/workflows/monitor.yml
name: DeSo Monitor
on:
  schedule:
    - cron: '*/10 * * * *'  # Every 10 minutes
  workflow_dispatch:

jobs:
  monitor:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    - name: Install dependencies
      run: pip install -r requirements.txt
    - name: Run single measurement
      env:
        DESO_PUBLIC_KEY: ${{ secrets.DESO_PUBLIC_KEY }}
        DESO_SEED_HEX: ${{ secrets.DESO_SEED_HEX }}
      run: python single_measurement.py
```

### Railway.app (Free tier)
- 500 hours/month free
- Simple git deployment
- Good for small applications

### Heroku alternatives:
- **Render.com**: Free tier available
- **fly.io**: Free allowances
- **PythonAnywhere**: Free tier with limitations

## Next Steps

1. **Choose platform** (I recommend Azure Container Instances)
2. **Modify code slightly** for cloud environment
3. **Set up deployment** 
4. **Monitor costs** (start with free tier)

Would you like me to help you set up any of these options?
