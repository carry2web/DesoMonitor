# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY deso_monitor.py .
COPY deso_sdk.py .
COPY node_manager.py .
COPY nodes_config.json .
COPY .env .

# Create data directory
RUN mkdir -p /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MATPLOTLIB_BACKEND=Agg

# Expose port (if needed for future web interface)
EXPOSE 8000

# Run the DesoMonitor
CMD ["python", "deso_monitor.py"]
