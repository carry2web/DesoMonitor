import time
import threading
import datetime
import matplotlib.pyplot as plt
import os
import logging
import json
from dotenv import load_dotenv
from deso_sdk import DeSoDexClient

# Setup logging with UTF-8 encoding
import sys

# Configure console output for UTF-8 (cloud-friendly)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/data/desomonitor.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Set matplotlib backend for cloud environment
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend

# Configuration - Verified nodes with TxIndex enabled
NODES = [
    "https://node.deso.org",  # Main DeSo node - confirmed TxIndex enabled
    "https://desocialworld.desovalidator.net",  # Validator with public API - confirmed TxIndex enabled
    "https://safetynet.social"  # SafetyNet node - confirmed working
]
SCHEDULE_INTERVAL = int(os.getenv("SCHEDULE_INTERVAL", "600"))  # seconds, configurable via env
DAILY_POST_TIME = "00:00"  # UTC time for daily summary post
POST_TAG = "#desomonitormeasurement"

# Load environment variables (cloud-friendly)
load_dotenv()
PUBLIC_KEY = os.getenv("DESO_PUBLIC_KEY", "").replace('"','').replace("'","").strip()
SEED_HEX = os.getenv("DESO_SEED_HEX", "").replace('"','').replace("'","").strip()

if not PUBLIC_KEY or not SEED_HEX:
    logging.error("❌ Missing required environment variables: DESO_PUBLIC_KEY, DESO_SEED_HEX")
    sys.exit(1)

# Data storage with persistence
MEASUREMENTS_FILE = "/app/data/measurements.json"

def load_measurements():
    """Load measurements from persistent storage"""
    try:
        if os.path.exists(MEASUREMENTS_FILE):
            with open(MEASUREMENTS_FILE, 'r') as f:
                data = json.load(f)
                logging.info(f"📊 Loaded {sum(len(v) for v in data.values())} historical measurements")
                return data
    except Exception as e:
        logging.warning(f"⚠️ Could not load measurements: {e}")
    
    # Initialize empty measurements for all nodes
    return {node: [] for node in NODES}

def save_measurements(measurements):
    """Save measurements to persistent storage"""
    try:
        os.makedirs(os.path.dirname(MEASUREMENTS_FILE), exist_ok=True)
        with open(MEASUREMENTS_FILE, 'w') as f:
            json.dump(measurements, f)
        logging.debug(f"💾 Saved measurements to {MEASUREMENTS_FILE}")
    except Exception as e:
        logging.error(f"❌ Could not save measurements: {e}")

# Load existing measurements
measurements = load_measurements()

def post_measurement(node, parent_post_hash):
    logging.info(f"🔄 DesoMonitor: Starting measurement post to {node}")
    start = time.time()
    try:
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        logging.info(f"📡 Connecting to {node}...")
        client = DeSoDexClient(is_testnet=False, seed_phrase_or_hex=SEED_HEX, node_url=node)
        
        # Create a temporary post first to measure response time
        logging.info(f"📝 Testing connection to {node}...")
        temp_comment = f"\U0001F310 Node check-in\nTesting connection...\nTimestamp: {timestamp}\nNode: {node}\n{POST_TAG}"
        
        post_resp = client.submit_post(
            updater_public_key_base58check=PUBLIC_KEY,
            body=temp_comment,
            parent_post_hash_hex=parent_post_hash,
            title="",
            image_urls=[],
            video_urls=[],
            post_extra_data={"Node": node},
            min_fee_rate_nanos_per_kb=1000,
            is_hidden=False,
            in_tutorial=False
        )
        submit_resp = client.sign_and_submit_txn(post_resp)
        txn_hash = submit_resp.get("TxnHashHex")
        
        logging.info(f"⏳ Waiting for commitment from {node} (TxnHash: {txn_hash[:8]}...)")
        # Wait for commitment (confirmed reply) - increased timeout for cloud networks
        try:
            client.wait_for_commitment_with_timeout(txn_hash, 120.0)  # 2 minutes
            elapsed = time.time() - start
            
            # Now post the actual measurement with real timing as a reply
            final_comment = f"\U0001F310 Node check-in RESULT\nElapsed: {elapsed:.2f} sec\nTimestamp: {timestamp}\nNode: {node}\n{POST_TAG}"
            
            logging.info(f"📝 Posting final result: {elapsed:.2f}s...")
            final_resp = client.submit_post(
                updater_public_key_base58check=PUBLIC_KEY,
                body=final_comment,
                parent_post_hash_hex=parent_post_hash,  # Reply to main thread
                title="",
                image_urls=[],
                video_urls=[],
                post_extra_data={"Node": node, "Type": "measurement_result"},
                min_fee_rate_nanos_per_kb=1000,
                is_hidden=False,
                in_tutorial=False
            )
            client.sign_and_submit_txn(final_resp)
            
            logging.info(f"✅ SUCCESS: {node} responded in {elapsed:.2f} seconds")
            measurements[node].append((timestamp, elapsed))
            save_measurements(measurements)  # Persist after each measurement
            
        except Exception as confirm_err:
            elapsed = time.time() - start
            logging.warning(f"⚠️ TIMEOUT: Reply txn not confirmed for {node} after {elapsed:.2f}s: {confirm_err}")
            measurements[node].append((timestamp, None))
            save_measurements(measurements)
            
    except Exception as e:
        elapsed = time.time() - start
        logging.error(f"❌ ERROR: Failed to post to {node} after {elapsed:.2f}s: {e}")
        measurements[node].append((datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"), None))
        save_measurements(measurements)

def scheduled_measurements(parent_post_hash):
    logging.info(f"🚀 DesoMonitor: Starting scheduled measurements every {SCHEDULE_INTERVAL} seconds")
    measurement_count = 0
    while True:
        measurement_count += 1
        logging.info(f"📊 DesoMonitor: Starting measurement cycle #{measurement_count} for {len(NODES)} nodes")
        
        for i, node in enumerate(NODES, 1):
            logging.info(f"🔍 DesoMonitor: Processing node {i}/{len(NODES)}: {node}")
            post_measurement(node, parent_post_hash)
        
        next_run = datetime.datetime.utcnow() + datetime.timedelta(seconds=SCHEDULE_INTERVAL)
        logging.info(f"💤 DesoMonitor: Measurement cycle #{measurement_count} complete. Next run at {next_run.strftime('%H:%M:%S UTC')}")
        time.sleep(SCHEDULE_INTERVAL)

def generate_daily_graph():
    logging.info("📈 DesoMonitor: Generating daily performance graph...")
    try:
        plt.figure(figsize=(12, 6))  # Larger for better visibility
        
        for node in NODES:
            node_measurements = measurements.get(node, [])
            if not node_measurements:
                continue
                
            times = []
            elapsed = []
            for t, e in node_measurements:
                if e is not None:
                    try:
                        times.append(datetime.datetime.strptime(t, "%Y-%m-%d %H:%M:%S UTC"))
                        elapsed.append(e)
                    except ValueError:
                        continue
            
            if times and elapsed:
                plt.plot(times, elapsed, label=node.replace("https://", ""), marker='o', markersize=2)
                logging.info(f"📊 Graph data for {node}: {len(elapsed)} measurements")
        
        plt.xlabel("Time (UTC)")
        plt.ylabel("Response Time (seconds)")
        plt.title("DeSo Node Performance - 24 Hour Rolling")
        plt.legend()
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        graph_path = "/app/data/daily_performance.png"
        plt.savefig(graph_path, dpi=150, bbox_inches='tight')
        plt.close()
        logging.info(f"📈 Daily performance graph saved as '{graph_path}'")
        
    except Exception as e:
        logging.error(f"❌ Error generating daily graph: {e}")

def generate_gauge():
    logging.info("🎯 DesoMonitor: Generating daily performance gauge...")
    try:
        import numpy as np
        
        # Use horizontal bar chart for better cloud/mobile viewing
        fig, ax = plt.subplots(figsize=(10, 6))
        
        node_names = []
        medians = []
        colors = []
        
        for node in NODES:
            node_measurements = measurements.get(node, [])
            elapsed_times = [e for t, e in node_measurements if e is not None]
            
            if elapsed_times:
                median = np.median(elapsed_times)
                node_names.append(node.replace("https://", ""))
                medians.append(median)
                
                # Color coding
                if median < 15:
                    colors.append('green')
                    status = "EXCELLENT"
                elif median < 30:
                    colors.append('yellow') 
                    status = "GOOD"
                else:
                    colors.append('red')
                    status = "SLOW"
                    
                logging.info(f"🎯 Gauge for {node}: {median:.2f}s median ({status})")
        
        if node_names:
            bars = ax.barh(node_names, medians, color=colors, alpha=0.7)
            
            # Add value labels on bars
            for bar, median in zip(bars, medians):
                width = bar.get_width()
                ax.text(width + 0.5, bar.get_y() + bar.get_height()/2, 
                       f'{median:.2f}s', ha='left', va='center')
            
            ax.set_xlabel('Median Response Time (seconds)')
            ax.set_title('DeSo Node Performance Summary')
            ax.grid(axis='x', alpha=0.3)
            
            # Add performance thresholds
            ax.axvline(x=15, color='orange', linestyle='--', alpha=0.5, label='Good (15s)')
            ax.axvline(x=30, color='red', linestyle='--', alpha=0.5, label='Slow (30s)')
            ax.legend()
        
        gauge_path = "/app/data/daily_gauge.png"
        plt.tight_layout()
        plt.savefig(gauge_path, dpi=150, bbox_inches='tight')
        plt.close()
        logging.info(f"🎯 Daily performance gauge saved as '{gauge_path}'")
        
    except Exception as e:
        logging.error(f"❌ Error generating gauge: {e}")

def daily_post():
    logging.info("📋 DesoMonitor: Starting daily summary post creation...")
    generate_daily_graph()
    generate_gauge()
    
    # Enhanced summary with stats
    total_measurements = sum(len([m for m in measurements[node] if m[1] is not None]) for node in NODES)
    body = f"\U0001F4C8 Daily Node Performance Summary\n\nTotal measurements: {total_measurements}\nNodes monitored: {len(NODES)}\n\n{POST_TAG}"
    
    try:
        logging.info("📤 Posting daily summary to DeSo...")
        client = DeSoDexClient(is_testnet=False, seed_phrase_or_hex=SEED_HEX, node_url=NODES[0])
        post_resp = client.submit_post(
            updater_public_key_base58check=PUBLIC_KEY,
            body=body,
            parent_post_hash_hex=None,
            title="",
            image_urls=[],
            video_urls=[],
            post_extra_data={"Node": NODES[0], "Type": "daily_summary"},
            min_fee_rate_nanos_per_kb=1000,
            is_hidden=False,
            in_tutorial=False
        )
        submit_resp = client.sign_and_submit_txn(post_resp)
        parent_post_hash = submit_resp.get("TxnHashHex")
        logging.info(f"✅ Daily summary posted successfully! PostHashHex: {parent_post_hash}")
        return parent_post_hash
    except Exception as e:
        logging.error(f"❌ Error posting daily summary: {e}")
        return None

def daily_scheduler():
    logging.info("📅 DesoMonitor: Daily scheduler started")
    
    # Start measurements immediately with a daily post
    logging.info("🚀 Creating initial daily post...")
    parent_post_hash = daily_post()
    
    if parent_post_hash:
        logging.info("🔄 Starting measurements thread...")
        threading.Thread(target=scheduled_measurements, args=(parent_post_hash,), daemon=True).start()
    else:
        logging.error("❌ Failed to create initial post, exiting...")
        return
    
    while True:
        now = datetime.datetime.utcnow()
        target = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if now > target:
            target += datetime.timedelta(days=1)
        sleep_time = (target - now).total_seconds()
        
        hours = int(sleep_time // 3600)
        minutes = int((sleep_time % 3600) // 60)
        logging.info(f"⏰ DesoMonitor: Next daily post in {hours}h {minutes}m at {target.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        time.sleep(sleep_time)
        
        # Create new daily post with accumulated data
        new_parent_post_hash = daily_post()
        if new_parent_post_hash:
            parent_post_hash = new_parent_post_hash
            logging.info("🔄 Daily post created, measurements continue under new post...")

if __name__ == "__main__":
    logging.info("🚀 DesoMonitor: Starting in cloud mode...")
    logging.info(f"📊 Configuration: {len(NODES)} nodes, {SCHEDULE_INTERVAL}s interval")
    for i, node in enumerate(NODES, 1):
        logging.info(f"   Node {i}: {node}")
    
    # Health check for cloud platforms
    health_file = "/app/data/health"
    os.makedirs(os.path.dirname(health_file), exist_ok=True)
    with open(health_file, 'w') as f:
        f.write("healthy")
    
    logging.info("📅 Starting daily scheduler...")
    
    try:
        daily_scheduler()
    except KeyboardInterrupt:
        logging.info("🛑 DesoMonitor: Shutting down gracefully...")
    except Exception as e:
        logging.error(f"❌ DesoMonitor crashed: {e}")
        sys.exit(1)
