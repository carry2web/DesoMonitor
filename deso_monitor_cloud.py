# --- On-chain config support ---
CONFIG_POST_HASH = "91522722c35f6b38588f059723ae3a401a92ae7a09826c6a987bf511d02f21aa"

def fetch_config_from_post(post_hash):
    client = DeSoDexClient(is_testnet=False, seed_phrase_or_hex=SEED_HEX)
    url = f"{client.node_url}/api/v0/get-single-post"
    payload = {"PostHashHex": post_hash}
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    post = resp.json().get("PostFound")
    if not post:
        raise Exception("Config post not found")
    body = post.get("Body", "")
    logging.info(f"DEBUG: Raw config post body (len={len(body)}):\n{body}")
    try:
        config = json.loads(body)
    except Exception as e:
        logging.error(f"ERROR: Failed to parse config post body as JSON. Exception: {e}")
        logging.error(f"ERROR: Raw config post body repr: {repr(body)}")
        raise Exception(f"Config post body is not valid JSON: {e}")
    return config

def load_config():
    try:
        config = fetch_config_from_post(CONFIG_POST_HASH)
        nodes = config.get("NODES", ["https://node.deso.org"])
        schedule_interval = int(config.get("SCHEDULE_INTERVAL", 600))
        daily_post_time = config.get("DAILY_POST_TIME", "00:00")
        post_tag = config.get("POST_TAG", "#desomonitormeasurement")
        if isinstance(nodes, str):
            nodes = [n.strip() for n in nodes.split(",") if n.strip()]
        logging.info(f"DEBUG: Loaded NODES from config post: {nodes} (count={len(nodes)})")
        return nodes, schedule_interval, daily_post_time, post_tag
    except Exception as e:
        logging.warning(f"Error loading config from chain: {e}. Falling back to defaults.")
        nodes = os.getenv("DESO_NODES", "https://node.deso.org,https://desocialworld.desovalidator.net,https://safetynet.social")
        nodes = [n.strip() for n in nodes.split(",") if n.strip()]
        schedule_interval = int(os.getenv("SCHEDULE_INTERVAL", "600"))
        daily_post_time = os.getenv("DAILY_POST_TIME", "00:00")
        post_tag = os.getenv("POST_TAG", "#desomonitormeasurement")
        return nodes, schedule_interval, daily_post_time, post_tag

import time
import threading
import datetime
import matplotlib.pyplot as plt
import os
import logging
import json
import requests
from dotenv import load_dotenv
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deso-sdk-fork'))
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
            # On-chain only: no local storage
            
        except Exception as confirm_err:
            elapsed = time.time() - start
            logging.warning(f"⚠️ TIMEOUT: Reply txn not confirmed for {node} after {elapsed:.2f}s: {confirm_err}")
            # On-chain only: no local storage
            
    except Exception as e:
        elapsed = time.time() - start
        logging.error(f"❌ ERROR: Failed to post to {node} after {elapsed:.2f}s: {e}")
        # On-chain only: no local storage
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
        plt.figure(figsize=(12, 6))
        # Fetch measurement posts (comments) from the current daily post
        client = DeSoDexClient(is_testnet=False, seed_phrase_or_hex=SEED_HEX, node_url=NODES[0])
        # Find the latest daily post by this account (or pass in parent_post_hash)
        # For now, assume the latest post is the parent (could be improved)
        url = f"{client.node_url}/api/v0/get-posts-for-public-key"
        payload = {"PublicKeyBase58Check": PUBLIC_KEY, "NumToFetch": 5}
        resp = requests.post(url, json=payload)
        resp.raise_for_status()
        posts = resp.json().get("Posts", [])
        parent_post_hash = None
        for post in posts:
            if post.get("Body", "").startswith("\U0001F4C8 Daily Node Performance Summary"):
                parent_post_hash = post.get("PostHashHex")
                break
        if not parent_post_hash:
            logging.error("No daily summary post found for graphing.")
            return
        # Fetch all comments (measurement posts) for the daily post
        url = f"{client.node_url}/api/v0/get-single-post"
        payload = {"PostHashHex": parent_post_hash}
        resp = requests.post(url, json=payload)
        resp.raise_for_status()
        comments = resp.json().get("PostFound", {}).get("Comments")
        if comments is None:
            comments = []
        # Parse measurement data from comments
        node_data = {node: ([], []) for node in NODES}
        for comment in comments:
            body = comment.get("Body", "")
            extra = comment.get("PostExtraData", {})
            node = extra.get("Node")
            if not node or node not in node_data:
                continue
            # Parse timestamp and elapsed from body
            try:
                # Example: "🌐 Node check-in RESULT\nElapsed: 1.23 sec\nTimestamp: 2026-02-01 12:34:56 UTC\nNode: ..."
                lines = body.split("\n")
                elapsed = None
                timestamp = None
                for line in lines:
                    if line.startswith("Elapsed:"):
                        elapsed = float(line.split()[1])
                    if line.startswith("Timestamp:"):
                        timestamp = line.split("Timestamp:")[1].strip()
                if elapsed is not None and timestamp:
                    node_data[node][0].append(datetime.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S UTC"))
                    node_data[node][1].append(elapsed)
            except Exception as e:
                continue
        for node, (times, elapsed) in node_data.items():
            if times and elapsed:
                plt.plot(times, elapsed, label=node.replace("https://", ""), marker='o', markersize=2)
                logging.info(f"📊 On-chain graph data for {node}: {len(elapsed)} measurements")
        plt.xlabel("Time (UTC)")
        plt.ylabel("Response Time (seconds)")
        plt.title("DeSo Node Performance - 24 Hour Rolling (On-Chain)")
        plt.legend()
        plt.xticks(rotation=45)
        plt.tight_layout()
        graph_path = "/app/data/daily_performance.png"
        plt.savefig(graph_path, dpi=150, bbox_inches='tight')
        plt.close()
        logging.info(f"📈 Daily performance graph saved as '{graph_path}' (on-chain data)")
    except Exception as e:
        logging.error(f"❌ Error generating daily graph: {e}")

def generate_gauge():
    logging.info("🎯 DesoMonitor: Generating daily performance gauge...")
    try:
        import numpy as np
        # Fetch measurement posts (comments) from the current daily post
        client = DeSoDexClient(is_testnet=False, seed_phrase_or_hex=SEED_HEX, node_url=NODES[0])
        url = f"{client.node_url}/api/v0/get-posts-for-public-key"
        payload = {"PublicKeyBase58Check": PUBLIC_KEY, "NumToFetch": 5}
        resp = requests.post(url, json=payload)
        resp.raise_for_status()
        posts = resp.json().get("Posts", [])
        parent_post_hash = None
        for post in posts:
            if post.get("Body", "").startswith("\U0001F4C8 Daily Node Performance Summary"):
                parent_post_hash = post.get("PostHashHex")
                break
        if not parent_post_hash:
            logging.error("No daily summary post found for gauge.")
            return
        # Fetch all comments (measurement posts) for the daily post
        url = f"{client.node_url}/api/v0/get-single-post"
        payload = {"PostHashHex": parent_post_hash}
        resp = requests.post(url, json=payload)
        resp.raise_for_status()
        comments = resp.json().get("PostFound", {}).get("Comments")
        if comments is None:
            comments = []
        # Parse measurement data from comments
        node_data = {node: [] for node in NODES}
        for comment in comments:
            body = comment.get("Body", "")
            extra = comment.get("PostExtraData", {})
            node = extra.get("Node")
            if not node or node not in node_data:
                continue
            try:
                lines = body.split("\n")
                elapsed = None
                for line in lines:
                    if line.startswith("Elapsed:"):
                        elapsed = float(line.split()[1])
                if elapsed is not None:
                    node_data[node].append(elapsed)
            except Exception:
                continue
        # Generate gauge plot
        plt.figure(figsize=(8, 4))
        medians = []
        for node, values in node_data.items():
            if values:
                median = np.median(values)
                medians.append((node, median))
        if not medians:
            logging.error("No on-chain measurement data for gauge plot.")
            return
        medians.sort(key=lambda x: x[1])
        nodes = [n for n, _ in medians]
        values = [v for _, v in medians]
        plt.bar(nodes, values, color='skyblue')
        plt.ylabel('Median Response Time (s)')
        plt.title('Median Node Response (On-Chain)')
        plt.tight_layout()
        plt.savefig("/app/data/daily_gauge.png", dpi=150, bbox_inches='tight')
        plt.close()
        logging.info("🎯 Daily performance gauge saved as '/app/data/daily_gauge.png' (on-chain data)")
    except Exception as e:
        logging.error(f"❌ Error generating gauge: {e}")

def daily_post():
    logging.info("📋 DesoMonitor: Starting daily summary post creation...")
    generate_daily_graph()
    generate_gauge()
    
    # Enhanced summary with stats
    # On-chain only: count measurements by fetching comments
    try:
        client = DeSoDexClient(is_testnet=False, seed_phrase_or_hex=SEED_HEX, node_url=NODES[0])
        url = f"{client.node_url}/api/v0/get-posts-for-public-key"
        payload = {"PublicKeyBase58Check": PUBLIC_KEY, "NumToFetch": 5}
        resp = requests.post(url, json=payload)
        resp.raise_for_status()
        posts = resp.json().get("Posts", [])
        parent_post_hash = None
        for post in posts:
            if post.get("Body", "").startswith("\U0001F4C8 Daily Node Performance Summary"):
                parent_post_hash = post.get("PostHashHex")
                break
        if not parent_post_hash:
            total_measurements = 0
        else:
            url = f"{client.node_url}/api/v0/get-single-post"
            payload = {"PostHashHex": parent_post_hash}
            resp = requests.post(url, json=payload)
            resp.raise_for_status()
            comments = resp.json().get("PostFound", {}).get("Comments", [])
            total_measurements = sum(1 for c in comments if c.get("PostExtraData", {}).get("Type") == "measurement_result")
    except Exception as e:
        total_measurements = 0
    body = f"\U0001F4C8 Daily Node Performance Summary\n\nTotal measurements: {total_measurements}\nNodes monitored: {len(NODES)}\n\n{POST_TAG}"
    
    try:
        logging.info("📤 Posting daily summary to DeSo...")
        client = DeSoDexClient(is_testnet=False, seed_phrase_or_hex=SEED_HEX, node_url=NODES[0])
        # Upload the graph image and get the URL (now requires public key)
        image_url = client.upload_image("/app/data/daily_performance.png", PUBLIC_KEY)
        post_resp = client.submit_post(
            updater_public_key_base58check=PUBLIC_KEY,
            body=body,
            parent_post_hash_hex=None,
            title="",
            image_urls=[image_url],
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

    # Load config from on-chain post at the start of each daily cycle
    global NODES, SCHEDULE_INTERVAL, DAILY_POST_TIME, POST_TAG
    NODES, SCHEDULE_INTERVAL, DAILY_POST_TIME, POST_TAG = load_config()

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

        # Reload config from on-chain post before each new daily post
        NODES, SCHEDULE_INTERVAL, DAILY_POST_TIME, POST_TAG = load_config()

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
