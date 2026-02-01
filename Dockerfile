FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Install forked deso-python-sdk with image upload functionality


# Copy only needed application files (exclude deso_sdk.py)
COPY deso_monitor_cloud.py .
COPY deso_monitor.py .
COPY node_manager.py .
COPY scammer_report_bot.py .
COPY test_nodes.py .
COPY test_txindex.py .
COPY upload_image_method.py .
COPY upload_image_sdk_method.py .
COPY generate_sample_graphs.py .
COPY get-graph.py .
COPY *.md .
# Copy the forked SDK directory
COPY deso-sdk-fork/ deso-sdk-fork/

# Create directory for logs and graphs
RUN mkdir -p /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import os; exit(0 if os.path.exists('desomonitor.log') else 1)"

# Run the monitor
CMD ["python", "deso_monitor_cloud.py"]
