import threading
import datetime
import matplotlib.pyplot as plt
import os
import logging
from dotenv import load_dotenv
from deso_sdk import DeSoDexClient

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

# Configure console output for UTF-8 on Windows
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('desomonitor.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Set matplotlib backend for threading support
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend

# Configuration - Verified nodes with TxIndex enabled
NODES = [
 "https://node.deso.org",
 "https://desonode-eu-west-1.desocialworld.com",
 "https://validator.safetynet.social",
 "https://node.beyondsocial.app"
 ]
SCHEDULE_INTERVAL = 3600  # seconds
DAILY_POST_TIME = "00:00"  # UTC time for daily summary post
POST_TAG = "#desomonitormeasurement"

load_dotenv()
PUBLIC_KEY = os.getenv("DESO_PUBLIC_KEY").replace('"','').replace("'","").strip()
SEED_HEX = os.getenv("DESO_SEED_HEX").replace('"','').replace("'","").strip()

# Data storage

MEASUREMENTS_FILE = "measurements.json"
measurements = {node: [] for node in NODES}

def save_measurements():
    """Save measurements to JSON, keeping only last 30 days for each node."""
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=30)
    filtered = {}
    for node, entries in measurements.items():
        filtered_entries = []
        for t, e in entries:
            try:
                dt = datetime.datetime.strptime(t, "%Y-%m-%d %H:%M:%S UTC")
                if dt >= cutoff:
                    filtered_entries.append((t, e))
            except Exception:
                # If timestamp is invalid, keep entry
                filtered_entries.append((t, e))
        filtered[node] = filtered_entries
    with open(MEASUREMENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(filtered, f, indent=2, ensure_ascii=False)
    logging.info(f"💾 Measurements saved to {MEASUREMENTS_FILE} (clipped to 30 days)")


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
        # Wait for commitment (confirmed reply) - increased timeout for slow networks
        try:
            client.wait_for_commitment_with_timeout(txn_hash, 120.0)  # Increased to 2 minutes
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
            print(final_comment)
            measurements[node].append((timestamp, elapsed))
            save_measurements()
        except Exception as confirm_err:
            elapsed = time.time() - start
            logging.warning(f"⚠️ TIMEOUT: Reply txn not confirmed for {node} after {elapsed:.2f}s: {confirm_err}")
            print(f"Reply txn not confirmed for {node}: {confirm_err}")
            measurements[node].append((timestamp, None))
            save_measurements()
    except Exception as e:
        elapsed = time.time() - start
        logging.error(f"❌ ERROR: Failed to post to {node} after {elapsed:.2f}s: {e}")
        print(f"Error posting to {node}: {e}")
        measurements[node].append((datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"), None))
        save_measurements()

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
    plt.figure(figsize=(8, 4))
    for node in NODES:
        times = [datetime.datetime.strptime(t, "%Y-%m-%d %H:%M:%S UTC") for t, e in measurements[node] if e is not None]
        elapsed = [e for t, e in measurements[node] if e is not None]
        plt.plot(times, elapsed, label=node)
        logging.info(f"📊 Graph data for {node}: {len(elapsed)} measurements")
    plt.xlabel("Time")
    plt.ylabel("Elapsed (sec)")
    plt.title("Node Performance - Daily")
    plt.legend()
    plt.tight_layout()
    plt.savefig("daily_performance.png")
    plt.close()
    logging.info("📈 Daily performance graph saved as 'daily_performance.png'")

def generate_gauge():
    logging.info("🎯 DesoMonitor: Generating daily performance gauge...")
    # Median per node
    import numpy as np
    fig, ax = plt.subplots(figsize=(6, 3), subplot_kw={'projection': 'polar'})
    for i, node in enumerate(NODES):
        elapsed = [e for t, e in measurements[node] if e is not None]
        if elapsed:
            median = np.median(elapsed)
            color = 'green' if median < 3 else 'yellow' if median < 20 else 'red'
            ax.bar(i * np.pi / len(NODES), 1, width=np.pi / len(NODES), color=color, alpha=0.7)
            ax.text(i * np.pi / len(NODES), 1.1, f"{node}\n{median:.2f}s", ha='center')
            logging.info(f"🎯 Gauge for {node}: {median:.2f}s median ({color})")
    ax.set_yticklabels([])
    ax.set_xticklabels([])
    ax.set_title("Median Node Response (Gauge)")
    plt.savefig("daily_gauge.png")
    plt.close()
    logging.info("🎯 Daily performance gauge saved as 'daily_gauge.png'")

def daily_post():
    logging.info("📋 DesoMonitor: Starting daily summary post creation...")
    generate_daily_graph()
    generate_gauge()
    body = f"\U0001F4C8 Daily Node Performance Summary\n{POST_TAG}"
    try:
        save_measurements()
        logging.info("📤 Posting daily summary to DeSo...")
        client = DeSoDexClient(is_testnet=False, seed_phrase_or_hex=SEED_HEX, node_url=NODES[0])
        post_resp = client.submit_post(
            updater_public_key_base58check=PUBLIC_KEY,
            body=body,
            parent_post_hash_hex=None,
            title="",
            image_urls=[],
            video_urls=[],
            post_extra_data={"Node": NODES[0]},
            min_fee_rate_nanos_per_kb=1000,
            is_hidden=False,
            in_tutorial=False
        )
        submit_resp = client.sign_and_submit_txn(post_resp)
        parent_post_hash = submit_resp.get("TxnHashHex")
        logging.info(f"✅ Daily summary posted successfully! PostHashHex: {parent_post_hash}")
        print(f"Daily summary posted. PostHashHex: {parent_post_hash}")
        return parent_post_hash
    except Exception as e:
        logging.error(f"❌ Error posting daily summary: {e}")
        print(f"Error posting daily summary: {e}")
        return None

def daily_scheduler():
    logging.info("📅 DesoMonitor: Daily scheduler started")
    
    # Start measurements immediately with a temporary parent post
    logging.info("🚀 Creating initial daily post...")
    parent_post_hash = daily_post()
    
    if parent_post_hash:
        logging.info("🔄 Starting initial measurements thread...")
        threading.Thread(target=scheduled_measurements, args=(parent_post_hash,), daemon=True).start()
    
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
    logging.info("🚀 DesoMonitor: Starting up...")
    logging.info(f"📊 Configuration: {len(NODES)} nodes, {SCHEDULE_INTERVAL}s interval")
    for i, node in enumerate(NODES, 1):
        logging.info(f"   Node {i}: {node}")
    
    logging.info("📅 Starting daily scheduler thread...")
    threading.Thread(target=daily_scheduler, daemon=True).start()
    
    logging.info("💤 DesoMonitor: Ready and running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logging.info("🛑 DesoMonitor: Shutting down gracefully...")
        print("\nDesoMonitor stopped.")
