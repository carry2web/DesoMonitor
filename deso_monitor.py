import time
import threading
import datetime
import matplotlib.pyplot as plt
import os
import logging
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
    "https://node.deso.org",  # Main DeSo node - confirmed TxIndex enabled
    "https://desocialworld.desovalidator.net",  # Validator with public API - confirmed TxIndex enabled
    "https://safetynet.social"  # SafetyNet node - confirmed working
]
SCHEDULE_INTERVAL = 600  # seconds
DAILY_POST_TIME = "00:00"  # UTC time for daily summary post
POST_TAG = "#desomonitormeasurement"

load_dotenv()
PUBLIC_KEY = os.getenv("DESO_PUBLIC_KEY").replace('"','').replace("'","").strip()
SEED_HEX = os.getenv("DESO_SEED_HEX").replace('"','').replace("'","").strip()

# Data storage - now tracking both post speed and confirmation speed
measurements = {node: [] for node in NODES}


def post_measurement(node, parent_post_hash):
    logging.info(f"🔄 DesoMonitor: Starting dual measurement for {node}")
    start_total = time.time()
    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    # Phase 1: Measure POST speed
    post_start = time.time()
    try:
        logging.info(f"📡 Connecting to {node}...")
        client = DeSoDexClient(is_testnet=False, seed_phrase_or_hex=SEED_HEX, node_url=node)
        
        logging.info(f"📝 Testing POST speed to {node}...")
        temp_comment = f"\U0001F310 Node check-in\nTesting POST + CONFIRMATION...\nTimestamp: {timestamp}\nNode: {node}\n{POST_TAG}"
        
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
        
        post_elapsed = time.time() - post_start
        logging.info(f"📤 POST completed in {post_elapsed:.2f}s (TxnHash: {txn_hash[:8]}...)")
        
    except Exception as e:
        total_elapsed = time.time() - start_total
        logging.error(f"❌ POST ERROR: Failed to post to {node} after {total_elapsed:.2f}s: {e}")
        measurements[node].append((timestamp, None, None, str(e)))
        return
    
    # Phase 2: Measure CONFIRMATION speed
    confirm_start = time.time()
    try:
        logging.info(f"⏳ Waiting for CONFIRMATION from {node}...")
        client.wait_for_commitment_with_timeout(txn_hash, 120.0)
        confirm_elapsed = time.time() - confirm_start
        total_elapsed = time.time() - start_total
        
        logging.info(f"✅ CONFIRMED in {confirm_elapsed:.2f}s (Total: {total_elapsed:.2f}s)")
        
    except Exception as confirm_err:
        confirm_elapsed = None
        total_elapsed = time.time() - start_total
        logging.warning(f"⚠️ CONFIRMATION TIMEOUT after {total_elapsed:.2f}s: {confirm_err}")
        measurements[node].append((timestamp, post_elapsed, None, "Confirmation timeout"))
        return
    
    # Success - record both metrics
    final_comment = f"\U0001F310 Node Performance RESULT\nPOST: {post_elapsed:.2f}s | CONFIRM: {confirm_elapsed:.2f}s | TOTAL: {total_elapsed:.2f}s\nTimestamp: {timestamp}\nNode: {node}\n{POST_TAG}"
    
    logging.info(f"📝 Posting final result...")
    try:
        final_resp = client.submit_post(
            updater_public_key_base58check=PUBLIC_KEY,
            body=final_comment,
            parent_post_hash_hex=parent_post_hash,
            title="",
            image_urls=[],
            video_urls=[],
            post_extra_data={"Node": node, "Type": "measurement_result", "PostTime": f"{post_elapsed:.2f}", "ConfirmTime": f"{confirm_elapsed:.2f}"},
            min_fee_rate_nanos_per_kb=1000,
            is_hidden=False,
            in_tutorial=False
        )
        client.sign_and_submit_txn(final_resp)
        
        logging.info(f"🎯 SUCCESS: {node} - POST: {post_elapsed:.2f}s, CONFIRM: {confirm_elapsed:.2f}s")
        print(final_comment)
        measurements[node].append((timestamp, post_elapsed, confirm_elapsed, "Success"))
        
    except Exception as result_err:
        logging.warning(f"⚠️ Result post failed, but measurements recorded: {result_err}")
        measurements[node].append((timestamp, post_elapsed, confirm_elapsed, "Result post failed"))

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
    logging.info("📈 DesoMonitor: Generating dual-metric performance graph...")
    
    # Create subplot with two graphs
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    
    # Graph 1: POST Speed
    ax1.set_title("DeSo Node POST Speed (Transaction Submission)")
    for node in NODES:
        # Extract data: (timestamp, post_time, confirm_time, status)
        valid_data = [(t, p) for t, p, c, s in measurements[node] if p is not None]
        if valid_data:
            times = [datetime.datetime.strptime(t, "%Y-%m-%d %H:%M:%S UTC") for t, p in valid_data]
            post_times = [p for t, p in valid_data]
            ax1.plot(times, post_times, label=f"{node} (POST)", marker='o', markersize=3)
            logging.info(f"📊 POST data for {node}: {len(post_times)} measurements")
    
    ax1.set_xlabel("Time")
    ax1.set_ylabel("POST Speed (seconds)")
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Graph 2: CONFIRMATION Speed  
    ax2.set_title("DeSo Node CONFIRMATION Speed (Transaction Commitment)")
    for node in NODES:
        # Extract confirmation data
        valid_data = [(t, c) for t, p, c, s in measurements[node] if c is not None]
        if valid_data:
            times = [datetime.datetime.strptime(t, "%Y-%m-%d %H:%M:%S UTC") for t, c in valid_data]
            confirm_times = [c for t, c in valid_data]
            ax2.plot(times, confirm_times, label=f"{node} (CONFIRM)", marker='s', markersize=3)
            logging.info(f"📊 CONFIRM data for {node}: {len(confirm_times)} measurements")
    
    ax2.set_xlabel("Time")
    ax2.set_ylabel("CONFIRMATION Speed (seconds)")
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig("daily_performance.png", dpi=150)
    plt.close()
    logging.info("📈 Dual-metric performance graph saved as 'daily_performance.png'")

def generate_gauge():
    logging.info("🎯 DesoMonitor: Generating dual-metric horizontal bar gauge...")
    import numpy as np
    
    # Create horizontal bar chart
    fig, ax = plt.subplots(figsize=(10, 6))
    
    node_names = []
    post_medians = []
    confirm_medians = []
    
    for node in NODES:
        # Extract POST times
        post_times = [p for t, p, c, s in measurements[node] if p is not None]
        confirm_times = [c for t, p, c, s in measurements[node] if c is not None]
        
        if post_times:
            post_median = np.median(post_times)
            post_medians.append(post_median)
        else:
            post_medians.append(0)
            
        if confirm_times:
            confirm_median = np.median(confirm_times)
            confirm_medians.append(confirm_median)
        else:
            confirm_medians.append(0)
            
        # Shorten node names for display
        short_name = node.replace("https://", "").replace("www.", "")
        if len(short_name) > 25:
            short_name = short_name[:25] + "..."
        node_names.append(short_name)
        
        logging.info(f"🎯 {node}: POST {post_medians[-1]:.2f}s, CONFIRM {confirm_medians[-1]:.2f}s")
    
    # Create horizontal bars
    y_pos = np.arange(len(node_names))
    bar_height = 0.35
    
    # POST bars (left side)
    bars1 = ax.barh(y_pos - bar_height/2, post_medians, bar_height, 
                    label='POST Speed', color='#1f77b4', alpha=0.8)
    
    # CONFIRM bars (right side) 
    bars2 = ax.barh(y_pos + bar_height/2, confirm_medians, bar_height,
                    label='CONFIRM Speed', color='#ff7f0e', alpha=0.8)
    
    # Add value labels on bars
    for i, (post_val, confirm_val) in enumerate(zip(post_medians, confirm_medians)):
        if post_val > 0:
            ax.text(post_val + 0.1, i - bar_height/2, f'{post_val:.1f}s', 
                   va='center', fontsize=9)
        if confirm_val > 0:
            ax.text(confirm_val + 0.1, i + bar_height/2, f'{confirm_val:.1f}s', 
                   va='center', fontsize=9)
    
    ax.set_yticks(y_pos)
    ax.set_yticklabels(node_names)
    ax.set_xlabel('Response Time (seconds)')
    ax.set_title('DeSo Node Performance - POST vs CONFIRMATION Speed (Median)')
    ax.legend()
    ax.grid(True, alpha=0.3, axis='x')
    
    plt.tight_layout()
    plt.savefig("daily_gauge.png", dpi=150, bbox_inches='tight')
    plt.close()
    logging.info("🎯 Dual-metric horizontal bar gauge saved as 'daily_gauge.png'")

def daily_post():
    logging.info("📋 DesoMonitor: Starting daily summary post creation...")
    generate_daily_graph()
    generate_gauge()
    
    # Upload images to DeSo
    image_urls = []
    try:
        logging.info("📤 Uploading performance graph to DeSo...")
        client = DeSoDexClient(is_testnet=False, seed_phrase_or_hex=SEED_HEX, node_url=NODES[0])
        
        # Upload daily performance graph
        if os.path.exists('daily_performance.png'):
            perf_url = client.upload_image('daily_performance.png')
            image_urls.append(perf_url)
            logging.info(f"✅ Performance graph uploaded: {perf_url}")
        
        # Upload daily gauge
        if os.path.exists('daily_gauge.png'):
            gauge_url = client.upload_image('daily_gauge.png')
            image_urls.append(gauge_url)
            logging.info(f"✅ Gauge chart uploaded: {gauge_url}")
            
    except Exception as e:
        logging.error(f"⚠️ Error uploading images: {e}")
        # Continue with post creation even if image upload fails
    
    body = f"\U0001F4C8 Daily Node Performance Summary\n{POST_TAG}"
    try:
        logging.info("📤 Posting daily summary to DeSo...")
        post_resp = client.submit_post(
            updater_public_key_base58check=PUBLIC_KEY,
            body=body,
            parent_post_hash_hex=None,
            title="",
            image_urls=image_urls,
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
