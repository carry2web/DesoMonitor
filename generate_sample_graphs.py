#!/usr/bin/env python3
"""
DesoMonitor Sample Graph Generator
Generates sample performance graphs and gauges using fake data for demonstration.
Uses the new dual-metric format (POST speed vs CONFIRMATION speed).
"""

import json
import random
import time
from datetime import datetime, timedelta
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

# Configuration for sample data
SAMPLE_NODES = [
    "https://lazynina.org:17000",
    "https://desocialworld.desovalidator.net:17000", 
    "https://staketomeorelse.com:17000",
    "https://revolutionarystaking.com:17000",
    "https://notanagi.com:17000",
    "https://respectforyield.com:17000",
    "https://americanstakers.com:17000",
    "https://simplemanstaking.com:17000",
    "https://utopiancondition.com:17000",
    "https://highkey.desovalidator.net:17000"
]

def generate_sample_measurements():
    """Generate fake measurement data for each node using new dual-metric format."""
    measurements = {}
    
    # Generate data for the last 24 hours
    now = datetime.now()
    start_time = now - timedelta(hours=24)
    
    for node in SAMPLE_NODES:
        measurements[node] = []
        
        # Generate random number of measurements (120-150 for 24 hours)
        num_measurements = random.randint(120, 150)
        
        for i in range(num_measurements):
            # Random timestamp within the last 24 hours
            timestamp = start_time + timedelta(seconds=random.randint(0, 24*3600))
            
            # Generate realistic POST and CONFIRMATION times
            # POST time: 0.5-3 seconds (transaction submission)
            post_time = random.uniform(0.5, 3.0)
            
            # CONFIRMATION time: 10-45 seconds (waiting for confirmation)
            # Some nodes are faster, some slower
            base_confirm = 15 + (SAMPLE_NODES.index(node) * 3)  # Vary by node
            confirm_time = random.uniform(base_confirm, base_confirm + 15)
            
            # Status: mostly success, occasional failures
            status = "SUCCESS" if random.random() > 0.05 else "TIMEOUT"
            
            # Store in new format: [timestamp, post_time, confirm_time, status]
            measurements[node].append([
                timestamp.isoformat(),
                post_time,
                confirm_time,
                status
            ])
        
        # Sort by timestamp
        measurements[node].sort(key=lambda x: x[0])
        
    return measurements

def main():
    print("🚀 Generating sample DesoMonitor graphics with fake data...")
    
    # Generate sample measurement data
    measurements = generate_sample_measurements()
    
    # Save to JSON file for testing
    with open("sample_measurements.json", "w", encoding="utf-8") as f:
        json.dump(measurements, f, indent=2, default=str)
    
    # Import the graph generation functions from the main script
    import sys
    sys.path.append('.')
    from deso_monitor import generate_daily_graph, generate_gauge
    
    # Temporarily replace the global measurements variable
    import deso_monitor
    original_measurements = getattr(deso_monitor, 'measurements', {})
    deso_monitor.measurements = measurements
    
    try:
        # Generate the daily performance graph
        print("📈 Generating sample daily performance graph...")
        generate_daily_graph()
        
        # Rename to sample files
        import os
        if os.path.exists("daily_performance.png"):
            os.rename("daily_performance.png", "sample_daily_performance.png")
            print("📈 Sample daily performance graph saved as 'sample_daily_performance.png'")
        
        # Generate the gauge
        print("🎯 Generating sample daily performance gauge...")
        generate_gauge()
        
        # Rename to sample files
        if os.path.exists("daily_gauge.png"):
            os.rename("daily_gauge.png", "sample_daily_gauge.png")
            print("🎯 Sample daily performance gauge saved as 'sample_daily_gauge.png'")
            
    finally:
        # Restore original measurements
        deso_monitor.measurements = original_measurements
    
    print("✅ Sample graphics generated successfully!")
    print("Files created:")
    print("  - sample_daily_performance.png")
    print("  - sample_daily_gauge.png")
    print("  - sample_measurements.json")

if __name__ == "__main__":
    main()
