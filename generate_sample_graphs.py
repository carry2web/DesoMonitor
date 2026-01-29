import datetime
import matplotlib.pyplot as plt
import numpy as np
import random

# Set matplotlib backend for non-interactive use
import matplotlib
matplotlib.use('Agg')

# Configuration - Extended for testing scalability
NODES = [
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
]# Generate fake measurement data
def generate_fake_data():
    measurements = {node: [] for node in NODES}
    
    # Generate data for the last 24 hours
    start_time = datetime.datetime.utcnow() - datetime.timedelta(hours=24)
    
    for i in range(144):  # Every 10 minutes for 24 hours = 144 measurements
        timestamp = start_time + datetime.timedelta(minutes=i*10)
        timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
        
        # Generate realistic response times for each node
        for j, node in enumerate(NODES):
            # Different performance characteristics per node
            base_time = 8 + j * 3  # Each node gets progressively slower
            response_time = base_time + random.uniform(-3, 15) + random.gauss(0, 2)
            response_time = max(2, response_time)  # Minimum 2 seconds
            
            # Add some occasional timeouts (None values)
            if random.random() < 0.03 + j * 0.01:  # Higher timeout rate for slower nodes
                response_time = None
                
            measurements[node].append((timestamp_str, response_time))
    
    return measurements

def generate_daily_graph(measurements):
    print("📈 Generating sample daily performance graph...")
    plt.figure(figsize=(14, 8))
    
    # Use a color palette that works well for many lines
    colors = plt.cm.tab10(np.linspace(0, 1, len(NODES)))
    
    for i, node in enumerate(NODES):
        times = [datetime.datetime.strptime(t, "%Y-%m-%d %H:%M:%S UTC") for t, e in measurements[node] if e is not None]
        elapsed = [e for t, e in measurements[node] if e is not None]
        
        node_name = node.replace('https://', '').replace('http://', '')
        plt.plot(times, elapsed, label=node_name, color=colors[i], linewidth=1.5, marker='o', markersize=2, alpha=0.8)
        print(f"📊 Graph data for {node}: {len(elapsed)} measurements")
    
    plt.xlabel("Time (UTC)", fontsize=12)
    plt.ylabel("Response Time (seconds)", fontsize=12)
    plt.title("DeSo Node Performance - 24 Hour Monitoring", fontsize=14, fontweight='bold')
    
    # Handle legend for many nodes
    if len(NODES) > 6:
        plt.legend(fontsize=9, ncol=2, loc='upper left', bbox_to_anchor=(1.02, 1))
    else:
        plt.legend(fontsize=11)
        
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    # Add some styling
    plt.gca().spines['top'].set_visible(False)
    plt.gca().spines['right'].set_visible(False)
    
    plt.savefig("sample_daily_performance.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("📈 Sample daily performance graph saved as 'sample_daily_performance.png'")

def generate_gauge(measurements):
    print("🎯 Generating sample daily performance gauge...")
    import numpy as np
    
    # Calculate medians and prepare data
    node_data = []
    for node in NODES:
        elapsed = [e for t, e in measurements[node] if e is not None]
        if elapsed:
            median = np.median(elapsed)
            node_name = node.replace('https://', '').replace('http://', '')
            
            # Color coding: green < 15s, yellow 15-30s, red > 30s
            if median < 15:
                color = '#28a745'  # Green
                status = 'EXCELLENT'
            elif median < 30:
                color = '#ffc107'  # Yellow  
                status = 'GOOD'
            else:
                color = '#dc3545'  # Red
                status = 'SLOW'
            
            node_data.append({
                'name': node_name,
                'median': median,
                'color': color,
                'status': status
            })
            print(f"🎯 Gauge for {node}: {median:.2f}s median ({status})")
    
    # Sort by performance (fastest first)
    node_data.sort(key=lambda x: x['median'])
    
    # Create horizontal bar chart for better scalability
    fig, ax = plt.subplots(figsize=(12, max(6, len(node_data) * 0.8)))
    
    names = [d['name'] for d in node_data]
    medians = [d['median'] for d in node_data]
    colors = [d['color'] for d in node_data]
    statuses = [d['status'] for d in node_data]
    
    # Create horizontal bars
    y_pos = np.arange(len(names))
    bars = ax.barh(y_pos, medians, color=colors, alpha=0.8, edgecolor='white', linewidth=2)
    
    # Add value labels on bars
    for i, (bar, median, status) in enumerate(zip(bars, medians, statuses)):
        width = bar.get_width()
        ax.text(width + max(medians) * 0.01, bar.get_y() + bar.get_height()/2, 
                f'{median:.1f}s ({status})', 
                ha='left', va='center', fontweight='bold', fontsize=10)
    
    # Customize the chart
    ax.set_yticks(y_pos)
    ax.set_yticklabels(names, fontsize=11)
    ax.set_xlabel('Median Response Time (seconds)', fontsize=12)
    ax.set_title('DeSo Node Performance Ranking\nMedian Response Times (24h)', 
                 fontsize=14, fontweight='bold', pad=20)
    
    # Add performance zones as background
    ax.axvspan(0, 15, alpha=0.1, color='green', label='Excellent (< 15s)')
    ax.axvspan(15, 30, alpha=0.1, color='yellow', label='Good (15-30s)')  
    ax.axvspan(30, max(medians) * 1.1, alpha=0.1, color='red', label='Slow (> 30s)')
    
    # Add grid and styling
    ax.grid(True, axis='x', alpha=0.3)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    # Add legend
    ax.legend(loc='lower right', fontsize=10)
    
    # Ensure all text fits
    plt.tight_layout()
    
    plt.savefig("sample_daily_gauge.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("🎯 Sample daily performance gauge saved as 'sample_daily_gauge.png'")

def main():
    print("🚀 Generating sample DesoMonitor graphics with fake data...")
    
    # Generate fake measurement data
    measurements = generate_fake_data()
    
    # Generate graphs
    generate_daily_graph(measurements)
    generate_gauge(measurements)
    
    print("✅ Sample graphics generated successfully!")
    print("Files created:")
    print("  - sample_daily_performance.png")
    print("  - sample_daily_gauge.png")

if __name__ == "__main__":
    main()
