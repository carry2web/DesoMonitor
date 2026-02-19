

# --- Imports ---
import os
import json
import time
import logging
import threading
from threading import Lock
import datetime
import requests
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from dotenv import load_dotenv
from deso_sdk_fork.deso_sdk import DeSoDexClient

matplotlib.use('Agg')  # Use non-interactive backend
load_dotenv()

# --- Logging setup (moved to top for immediate effect) ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('desomonitor.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

SEED_HEX = os.getenv("DESO_SEED_HEX", "").replace('"','').replace("'",'').strip()  # from .env: DESO_SEED_HEX
PUBLIC_KEY = os.getenv("DESO_PUBLIC_KEY", "").replace('"','').replace("'",'').strip()  # from .env: DESO_PUBLIC_KEY
CONFIG_POST_HASH = os.getenv("CONFIG_POST_HASH", "91522722c35f6b38588f059723ae3a401a92ae7a09826c6a987bf511d02f21aa")
print(f"DEBUG: PUBLIC_KEY loaded: {PUBLIC_KEY}")
required_env = {
    'DESO_SEED_HEX': SEED_HEX,
    'DESO_PUBLIC_KEY': PUBLIC_KEY,
    'CONFIG_POST_HASH': CONFIG_POST_HASH,
}
missing = [k for k, v in required_env.items() if not v or v == '']
if missing:
    print(f"FATAL: Missing required .env keys: {', '.join(missing)}. Please set them in your .env file.")
    import sys
    sys.exit(1)

# --- On-chain config support ---
def fetch_config_from_post(post_hash):
    client = DeSoDexClient(is_testnet=False, seed_phrase_or_hex=SEED_HEX)  # SEED_HEX from DESO_SEED_HEX
    url = f"{client.node_url}/api/v0/get-single-post"
    payload = {"PostHashHex": post_hash}
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    post = resp.json().get("PostFound")
    if not post:
        raise Exception("Config post not found")
    body = post.get("Body", "")
    config = json.loads(body)
    return config

# --- Config loader and initial config ---
def load_config():
    try:
        config = fetch_config_from_post(CONFIG_POST_HASH)
        nodes = config.get("NODES", ["https://node.deso.org"])
        schedule_interval = int(config.get("SCHEDULE_INTERVAL", 3600))
        daily_post_time = config.get("DAILY_POST_TIME", "00:00")
        post_tag = config.get("POST_TAG", "#desomonitormeasurement")
        graph_days = int(config.get("GRAPH_DAYS", 7))
        mode = config.get("MODE", os.getenv("MODE", "DAILY-CYCLE"))
        if isinstance(nodes, str):
            nodes = [n.strip() for n in nodes.split(",") if n.strip()]
        return nodes, schedule_interval, daily_post_time, post_tag, graph_days, mode
    except Exception as e:
        print(f"Error loading config from chain: {e}. Falling back to .env config.")
        nodes = os.getenv("DESO_NODES", "https://node.deso.org,https://desocialworld.desovalidator.net,https://safetynet.social")
        nodes = [n.strip() for n in nodes.split(",") if n.strip()]
        schedule_interval = int(os.getenv("SCHEDULE_INTERVAL", "3600"))
        daily_post_time = os.getenv("DAILY_POST_TIME", "00:00")
        post_tag = os.getenv("POST_TAG", "#desomonitormeasurement")
        graph_days = int(os.getenv("GRAPH_DAYS", "7"))
        mode = os.getenv("MODE", "DAILY-CYCLE")
        return nodes, schedule_interval, daily_post_time, post_tag, graph_days, mode


# Initial config load
config_result = load_config()
if len(config_result) == 6:
    NODES, SCHEDULE_INTERVAL, DAILY_POST_TIME, POST_TAG, GRAPH_DAYS, MODE = config_result
else:
    NODES, SCHEDULE_INTERVAL, DAILY_POST_TIME, POST_TAG, GRAPH_DAYS = config_result
    MODE = "DAILY-CYCLE"

# Data storage with persistence
MEASUREMENTS_FILE = "measurements.json"
def load_measurements():
    if os.path.exists(MEASUREMENTS_FILE):
        with open(MEASUREMENTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Convert keys to current NODES and migrate old format
        migrated = {}
        for node in NODES:
            entries = data.get(node, [])
            migrated_entries = []
            for entry in entries:
                timestamp, measurement = entry
                # Check if old format (float) or new format (dict)
                if isinstance(measurement, (int, float)):
                    # OLD FORMAT: Convert elapsed to estimated POST/CONFIRM split
                    elapsed = float(measurement)
                    migrated_entries.append((timestamp, {
                        "post": elapsed * 0.1,  # Estimate 10% for POST
                        "confirm": elapsed * 0.9,  # Estimate 90% for CONFIRM
                        "total": elapsed
                    }))
                elif isinstance(measurement, dict):
                    # NEW FORMAT: Keep as-is
                    migrated_entries.append((timestamp, measurement))
                # Skip invalid entries
            migrated[node] = migrated_entries
        return migrated
    else:
        return {node: [] for node in NODES}

measurements = load_measurements()

def save_measurements():
    """Save measurements to JSON, keeping only last GRAPH_DAYS for each node."""
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=GRAPH_DAYS)
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
    logging.info(f"💾 Measurements saved to {MEASUREMENTS_FILE} (clipped to {GRAPH_DAYS} days)")

def post_measurement(node, parent_post_hash):
    logging.info(f"🔄 DesoMonitor: Starting measurement post to {node}")
    start = time.time()
    try:
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        logging.info(f"📡 Connecting to {node}...")
        client = DeSoDexClient(is_testnet=False, seed_phrase_or_hex=SEED_HEX, node_url=node)  # SEED_HEX from DESO_SEED_HEX
        # Create a temporary post first to measure response time
        logging.info(f"📝 Testing connection to {node}...")
        temp_comment = f"\U0001F310 Node check-in\nTesting connection...\nTimestamp: {timestamp}\nNode: {node}\n{POST_TAG}"
        post_resp = client.submit_post(
            updater_public_key_base58check=PUBLIC_KEY,  # PUBLIC_KEY from DESO_PUBLIC_KEY
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
        post_time = time.time() - start  # Time to POST (submit transaction)
        
        logging.info(f"⏳ Waiting for commitment from {node} (TxnHash: {txn_hash})")
        print(f"[DesoMonitor] Measurement post submitted. Full TxnHash: {txn_hash}")
        # Wait for commitment (confirmed reply) - increased timeout for slow networks
        try:
            confirm_start = time.time()
            client.wait_for_commitment_with_timeout(txn_hash, 120.0)  # Increased to 2 minutes
            confirm_time = time.time() - confirm_start  # Time to CONFIRM
            elapsed = time.time() - start

            # Now post the actual measurement with real timing as a reply
            final_comment = f"\U0001F310 Node check-in RESULT\nPOST: {post_time:.2f} sec\nCONFIRM: {confirm_time:.2f} sec\nTotal: {elapsed:.2f} sec\nTimestamp: {timestamp}\nNode: {node}\n{POST_TAG}"
            logging.info(f"📝 Posting final result: POST {post_time:.2f}s, CONFIRM {confirm_time:.2f}s, Total {elapsed:.2f}s...")
            final_resp = client.submit_post(
                updater_public_key_base58check=PUBLIC_KEY,  # PUBLIC_KEY from DESO_PUBLIC_KEY
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
            final_submit_resp = client.sign_and_submit_txn(final_resp)
            final_txn_hash = final_submit_resp.get("TxnHashHex")
            # Only log SUCCESS after the hash is available
            logging.info(f"✅ SUCCESS: {node} - POST: {post_time:.2f}s, CONFIRM: {confirm_time:.2f}s, Total: {elapsed:.2f}s | Measurement comment TxnHash: {final_txn_hash}")
            print(final_comment)
            print(f"[DesoMonitor] Measurement comment submitted. Full TxnHash: {final_txn_hash}")
            measurements[node].append((timestamp, {"post": post_time, "confirm": confirm_time, "total": elapsed, "comment_txn_hash": final_txn_hash}))
            save_measurements()
        except Exception as confirm_err:
            elapsed = time.time() - start
            logging.warning(f"⚠️ TIMEOUT: Reply txn not confirmed for {node} after {elapsed:.2f}s: {confirm_err}")
            print(f"Reply txn not confirmed for {node}: {confirm_err}")
            measurements[node].append((timestamp, {"post": post_time, "confirm": None, "total": elapsed}))
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
    # Remove old daily_performance.png generation
    # Only generate daily_performance_stacked.png (line+marker plot) and daily_performance_bar.png
    pass

def generate_gauge():
    logging.info("🎯 DesoMonitor: Generating daily performance gauge...")
    # Median per node
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
    global PUBLIC_KEY, SEED_HEX
    logging.info("📋 DesoMonitor: Starting daily summary post creation...")
    generate_daily_graph(GRAPH_DAYS)
    generate_gauge()
    body = f"\U0001F4C8 Daily Node Performance Summary\n{POST_TAG}"
    try:
        save_measurements()
        logging.info("\U0001F4E4 Posting daily summary to DeSo...")
        client = DeSoDexClient(is_testnet=False, seed_phrase_or_hex=SEED_HEX, node_url=NODES[0])  # SEED_HEX from DESO_SEED_HEX
        # Upload both graph images and get their URLs
        image_url1 = client.upload_image("daily_performance_stacked.png", PUBLIC_KEY)
        image_url2 = client.upload_image("daily_performance_bar.png", PUBLIC_KEY)
        post_resp = client.submit_post(
            updater_public_key_base58check=PUBLIC_KEY,
            body=body,
            parent_post_hash_hex=None,
            title="",
            image_urls=[image_url1, image_url2],
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


def post_measurement(node, parent_post_hash):
    logging.info(f"🔄 DesoMonitor: Starting measurement post to {node}")
    start = time.time()
    try:
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        logging.info(f"📡 Connecting to {node}...")
        client = DeSoDexClient(is_testnet=False, seed_phrase_or_hex=SEED_HEX, node_url=node)  # SEED_HEX from DESO_SEED_HEX
        
        # Create a temporary post first to measure response time
        logging.info(f"📝 Testing connection to {node}...")
        temp_comment = f"\U0001F310 Node check-in\nTesting connection...\nTimestamp: {timestamp}\nNode: {node}\n{POST_TAG}"
        
        post_resp = client.submit_post(
            updater_public_key_base58check=PUBLIC_KEY,  # PUBLIC_KEY from DESO_PUBLIC_KEY
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
        post_time = time.time() - start  # Time to POST (submit transaction)
        
        logging.info(f"⏳ Waiting for commitment from {node} (TxnHash: {txn_hash})")
        # Wait for commitment (confirmed reply) - increased timeout for slow networks
        try:
            confirm_start = time.time()
            client.wait_for_commitment_with_timeout(txn_hash, 120.0)  # Increased to 2 minutes
            confirm_time = time.time() - confirm_start  # Time to CONFIRM
            elapsed = time.time() - start
            
            # Now post the actual measurement with real timing as a reply
            final_comment = f"\U0001F310 Node check-in RESULT\nPOST: {post_time:.2f} sec\nCONFIRM: {confirm_time:.2f} sec\nTotal: {elapsed:.2f} sec\nTimestamp: {timestamp}\nNode: {node}\n{POST_TAG}"
            
            logging.info(f"📝 Posting final result: POST {post_time:.2f}s, CONFIRM {confirm_time:.2f}s, Total {elapsed:.2f}s...")
            final_resp = client.submit_post(
                updater_public_key_base58check=PUBLIC_KEY,  # PUBLIC_KEY from DESO_PUBLIC_KEY
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
            
            logging.info(f"✅ SUCCESS: {node} - POST: {post_time:.2f}s, CONFIRM: {confirm_time:.2f}s, Total: {elapsed:.2f}s")
            print(final_comment)
            measurements[node].append((timestamp, {"post": post_time, "confirm": confirm_time, "total": elapsed}))
        except Exception as confirm_err:
            elapsed = time.time() - start
            logging.warning(f"⚠️ TIMEOUT: Reply txn not confirmed for {node} after {elapsed:.2f}s: {confirm_err}")
            print(f"Reply txn not confirmed for {node}: {confirm_err}")
            measurements[node].append((timestamp, None))
    except Exception as e:
        elapsed = time.time() - start
        logging.error(f"❌ ERROR: Failed to post to {node} after {elapsed:.2f}s: {e}")
        print(f"Error posting to {node}: {e}")
        measurements[node].append((datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"), None))
        save_measurements()

def scheduled_measurements(parent_post_hash):
    logging.info(f"🚀 DesoMonitor: Starting scheduled measurements every {SCHEDULE_INTERVAL} seconds (thread started, parent_post_hash={parent_post_hash})")
    print(f"[DesoMonitor] Measurement thread started. Parent post hash: {parent_post_hash}")
    measurement_count = 0
    try:
        while True:
            measurement_count += 1
            logging.info(f"📊 DesoMonitor: Starting measurement cycle #{measurement_count} for {len(NODES)} nodes")
            logging.info(f"DEBUG: Full NODES list for monitoring: {NODES}")
            for i, node in enumerate(NODES, 1):
                logging.info(f"🔍 DesoMonitor: Processing node {i}/{len(NODES)}: {node} (parent_post_hash={parent_post_hash})")
                print(f"[DesoMonitor] Posting measurement for node {node} (parent_post_hash={parent_post_hash})")
                try:
                    post_measurement(node, parent_post_hash)
                except Exception as e:
                    logging.error(f"❌ ERROR: Exception during monitoring node {node}: {e}")
                    print(f"[DesoMonitor] ERROR posting measurement for node {node}: {e}")
                    # Still log the failed attempt for visibility
                    measurements[node].append((datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"), None))
            next_run = datetime.datetime.utcnow() + datetime.timedelta(seconds=SCHEDULE_INTERVAL)
            logging.info(f"💤 DesoMonitor: Measurement cycle #{measurement_count} complete. Next run at {next_run.strftime('%H:%M:%S UTC')}")
            print(f"[DesoMonitor] Measurement cycle #{measurement_count} complete. Next run at {next_run.strftime('%H:%M:%S UTC')}")
            time.sleep(SCHEDULE_INTERVAL)
    except Exception as thread_exc:
        logging.error(f"❌ ERROR: Measurement thread crashed: {thread_exc}")
        print(f"[DesoMonitor] FATAL: Measurement thread crashed: {thread_exc}")

def generate_daily_graph(graph_days=7):
    # --- NEW: Parse measurement comments from blockchain for last graph_days ---
    # (Legacy single-graph code removed; only stacked and bar graphs are produced)
    import re
    import numpy as np
    client = DeSoDexClient(is_testnet=False, seed_phrase_or_hex=SEED_HEX)
    url = f"{client.node_url}/api/v0/get-posts-for-public-key"
    payload = {"PublicKeyBase58Check": PUBLIC_KEY, "NumToFetch": graph_days * 3 + 20}
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    posts = resp.json().get("Posts", [])
    from collections import defaultdict
    daily_posts_by_date = defaultdict(list)
    for post in posts:
        if POST_TAG in post.get("Body", ""):
            post_time = post.get("TimestampNanos")
            if post_time:
                t = datetime.datetime.utcfromtimestamp(int(post_time) / 1e9)
                date_str = t.strftime("%Y-%m-%d")
                daily_posts_by_date[date_str].append((t, post))
    selected_daily_posts = []
    today = datetime.datetime.utcnow().date()
    # Dynamically determine expected number of measurement comments
    nodes = NODES
    schedule_interval = SCHEDULE_INTERVAL
    per_node_per_day = int(24 * 60 * 60 / schedule_interval)
    expected_comments = len(nodes) * per_node_per_day
    comment_limit = int(expected_comments * 1.2)  # 20% buffer
    for i in range(graph_days):
        day = today - datetime.timedelta(days=i)
        date_str = day.strftime("%Y-%m-%d")
        posts_for_day = sorted(daily_posts_by_date.get(date_str, []), key=lambda x: x[0], reverse=True)
        for t, post in posts_for_day:
            daily_post_hash = post.get("PostHashHex")
            url_single = f"{client.node_url}/api/v0/get-single-post"
            payload_single = {"PostHashHex": daily_post_hash, "CommentOffset": 0, "CommentLimit": comment_limit}
            resp_single = requests.post(url_single, json=payload_single)
            resp_single.raise_for_status()
            comments = resp_single.json().get("PostFound", {}).get("Comments", [])
            if comments:
                selected_daily_posts.append((post, comments))
                break
    measurement_comments = []
    for post, comments in selected_daily_posts:
        measurement_comments.extend([c for c in comments if POST_TAG in c.get("Body", "")])
    logging.info(f"🔎 Found {len(measurement_comments)} on-chain measurement comments for last {graph_days} days.")
    node_times = {node: [] for node in NODES}
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=graph_days)
    node_times_post = {node: [] for node in NODES}
    node_times_confirm = {node: [] for node in NODES}
    for c in measurement_comments:
        body = c.get("Body", "")
        node = None
        post_time = None
        confirm_time = None
        timestamp = None
        m_node = re.search(r"Node: (.+)", body)
        m_post = re.search(r"POST: ([0-9.]+) sec", body)
        m_confirm = re.search(r"CONFIRM: ([0-9.]+) sec", body)
        m_elapsed = re.search(r"Elapsed: ([0-9.]+) sec", body)  # OLD FORMAT
        m_time = re.search(r"Timestamp: ([0-9\-: ]+ UTC)", body)
        if m_node:
            node = m_node.group(1).strip()
        if m_post:
            post_time = float(m_post.group(1))
        if m_confirm:
            confirm_time = float(m_confirm.group(1))
        # Backward compatibility: if no POST/CONFIRM but have Elapsed, estimate split
        if m_elapsed and post_time is None and confirm_time is None:
            elapsed_time = float(m_elapsed.group(1))
            # Estimate: ~10% for POST, ~90% for CONFIRM (typical blockchain behavior)
            post_time = elapsed_time * 0.1
            confirm_time = elapsed_time * 0.9
        if m_time:
            timestamp = m_time.group(1).strip()
        if node in node_times and timestamp is not None:
            try:
                t = datetime.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S UTC")
                if t >= cutoff:
                    if post_time is not None:
                        node_times_post[node].append((t, post_time))
                        node_times[node].append((t, post_time))  # Keep for backward compatibility
                    if confirm_time is not None:
                        node_times_confirm[node].append((t, confirm_time))
                    logging.info(f"📥 Measurement used for graph: node={node}, timestamp={timestamp}, POST={post_time}s, CONFIRM={confirm_time}s")
            except Exception as ex:
                logging.debug(f"⚠️ Skipping invalid measurement comment: {body} (error: {ex})")
    # --- New: Stacked time series plots for POST and CONFIRM speeds ---
    import matplotlib.dates as mdates
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)
    colors = plt.cm.tab10(np.linspace(0, 1, len(NODES)))
    # POST Speed (top) - line+marker plot
    for i, node in enumerate(NODES):
        times = [t for t, e in node_times_post[node] if e is not None]
        elapsed = [e for t, e in node_times_post[node] if e is not None]
        node_name = node.replace('https://', '').replace('http://', '')
        ax1.plot(times, elapsed, marker='o', markersize=4, linestyle='-', label=node_name, color=colors[i])
        logging.info(f"📊 POST graph data for {node}: {len(elapsed)} measurements")
    ax1.set_ylabel("POST Speed (seconds)", fontsize=12)
    ax1.set_title("DeSo Node POST Speed (Transaction Submission)", fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend(fontsize=10, ncol=2, loc='upper left', bbox_to_anchor=(1.02, 1))
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    # CONFIRM Speed (bottom) - line+marker plot
    for i, node in enumerate(NODES):
        times = [t for t, e in node_times_confirm[node] if e is not None]
        elapsed = [e for t, e in node_times_confirm[node] if e is not None]
        node_name = node.replace('https://', '').replace('http://', '')
        ax2.plot(times, elapsed, marker='o', markersize=4, linestyle='-', label=node_name, color=colors[i])
        logging.info(f"📊 CONFIRM graph data for {node}: {len(elapsed)} measurements")
    ax2.set_ylabel("CONFIRMATION Speed (seconds)", fontsize=12)
    ax2.set_title("DeSo Node CONFIRMATION Speed (Transaction Commitment - Full Nodes Only)", fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.legend(fontsize=10, ncol=2, loc='upper left', bbox_to_anchor=(1.02, 1))
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.set_xlabel("Time (UTC)", fontsize=12)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45)
    plt.tight_layout()
    # Remove duplicate daily_performance.png generation
    # Only generate daily_performance_stacked.png and daily_performance_bar.png
    pass

    # --- Bar chart: POST vs CONFIRM Speed (Median) ---
    medians_post = []
    medians_confirm = []
    node_labels = []
    for node in NODES:
        post_times = [e for t, e in node_times_post[node] if e is not None]
        confirm_times = [e for t, e in node_times_confirm[node] if e is not None]
        if post_times or confirm_times:
            medians_post.append(np.median(post_times) if post_times else 0)
            medians_confirm.append(np.median(confirm_times) if confirm_times else 0)
            node_labels.append(node.replace('https://', '').replace('http://', ''))
    y_pos = np.arange(len(node_labels))
    bar_height = 0.35
    fig2, ax = plt.subplots(figsize=(13, max(5, len(node_labels) * 0.8)))
    bars1 = ax.barh(y_pos - bar_height/2, medians_post, bar_height, label='POST Speed', color='#3498db')
    bars2 = ax.barh(y_pos + bar_height/2, medians_confirm, bar_height, label='CONFIRM Speed', color='#27ae60')
    for i, (bar, median) in enumerate(zip(bars1, medians_post)):
        width = bar.get_width()
        ax.text(width + 0.1, bar.get_y() + bar.get_height()/2, f'{median:.1f}s', ha='left', va='center', fontsize=10)
    for i, (bar, median) in enumerate(zip(bars2, medians_confirm)):
        width = bar.get_width()
        ax.text(width + 0.1, bar.get_y() + bar.get_height()/2, f'{median:.1f}s', ha='left', va='center', fontsize=10)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(node_labels, fontsize=12)
    ax.set_xlabel('Response Time (seconds)', fontsize=12)
    ax.set_title('DeSo Node Performance - POST vs CONFIRMATION Speed (Median)', fontsize=15, fontweight='bold', pad=20)
    ax.legend(fontsize=12)
    ax.grid(True, axis='x', alpha=0.3)
    plt.tight_layout()
    plt.savefig("daily_performance_bar.png", dpi=300, bbox_inches='tight')
    plt.close(fig2)
    logging.info("📊 Bar chart saved as 'daily_performance_bar.png'")

def generate_gauge():
    logging.info("🎯 Generating daily performance gauge from on-chain data only...")
    import re
    import numpy as np
    client = DeSoDexClient(is_testnet=False, seed_phrase_or_hex=SEED_HEX)
    url = f"{client.node_url}/api/v0/get-posts-for-public-key"
    payload = {"PublicKeyBase58Check": PUBLIC_KEY, "NumToFetch": GRAPH_DAYS * 3 + 20}
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    posts = resp.json().get("Posts", [])
    from collections import defaultdict
    daily_posts_by_date = defaultdict(list)
    for post in posts:
        if POST_TAG in post.get("Body", ""):
            post_time = post.get("TimestampNanos")
            if post_time:
                t = datetime.datetime.utcfromtimestamp(int(post_time) / 1e9)
                date_str = t.strftime("%Y-%m-%d")
                daily_posts_by_date[date_str].append((t, post))
    selected_daily_posts = []
    today = datetime.datetime.utcnow().date()
    # Dynamically determine expected number of measurement comments
    nodes = NODES
    schedule_interval = SCHEDULE_INTERVAL
    per_node_per_day = int(24 * 60 * 60 / schedule_interval)
    expected_comments = len(nodes) * per_node_per_day
    comment_limit = int(expected_comments * 1.2)  # 20% buffer
    for i in range(GRAPH_DAYS):
        day = today - datetime.timedelta(days=i)
        date_str = day.strftime("%Y-%m-%d")
        posts_for_day = sorted(daily_posts_by_date.get(date_str, []), key=lambda x: x[0], reverse=True)
        for t, post in posts_for_day:
            daily_post_hash = post.get("PostHashHex")
            url_single = f"{client.node_url}/api/v0/get-single-post"
            payload_single = {"PostHashHex": daily_post_hash, "CommentOffset": 0, "CommentLimit": comment_limit}
            resp_single = requests.post(url_single, json=payload_single)
            resp_single.raise_for_status()
            comments = resp_single.json().get("PostFound", {}).get("Comments", [])
            if comments:
                selected_daily_posts.append((post, comments))
                break
    measurement_comments = []
    for post, comments in selected_daily_posts:
        measurement_comments.extend([c for c in comments if POST_TAG in c.get("Body", "")])
    logging.info(f"🔎 Found {len(measurement_comments)} on-chain measurement comments for last {GRAPH_DAYS} days (for gauge graph).")
    node_times = {node: [] for node in NODES}
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=GRAPH_DAYS)
    for c in measurement_comments:
        body = c.get("Body", "")
        node = None
        total_time = None
        timestamp = None
        m_node = re.search(r"Node: (.+)", body)
        m_total = re.search(r"Total: ([0-9.]+) sec", body)
        m_time = re.search(r"Timestamp: ([0-9\-: ]+ UTC)", body)
        if m_node:
            node = m_node.group(1).strip()
        if m_total:
            total_time = float(m_total.group(1))
        if m_time:
            timestamp = m_time.group(1).strip()
        if node in node_times and timestamp is not None and total_time is not None:
            try:
                t = datetime.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S UTC")
                if t >= cutoff:
                    node_times[node].append((t, total_time))
            except Exception as ex:
                logging.debug(f"⚠️ Skipping invalid measurement comment: {body} (error: {ex})")
    node_data = []
    for node in NODES:
        elapsed = [e for t, e in node_times[node] if e is not None]
        if elapsed:
            median = np.median(elapsed)
            node_name = node.replace('https://', '').replace('http://', '')
            if median < 15:
                color = '#28a745'
                status = 'EXCELLENT'
            elif median < 30:
                color = '#ffc107'
                status = 'GOOD'
            else:
                color = '#dc3545'
                status = 'SLOW'
            node_data.append({'name': node_name, 'median': median, 'color': color, 'status': status})
            logging.info(f"🎯 Gauge for {node}: {median:.2f}s median ({status})")
    node_data.sort(key=lambda x: x['median'])
    fig, ax = plt.subplots(figsize=(12, max(6, len(node_data) * 0.8)))
    if not node_data:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', fontsize=18, color='gray', transform=ax.transAxes)
        ax.set_axis_off()
        plt.title('DeSo Node Performance Ranking\nMedian Response Times (24h)', fontsize=14, fontweight='bold', pad=20)
        plt.tight_layout()
        plt.savefig("daily_gauge.png", dpi=300, bbox_inches='tight')
        plt.close()
        logging.info("📈 Daily gauge graph saved as 'daily_gauge.png' (no data)")
        return
    names = [d['name'] for d in node_data]
    medians = [d['median'] for d in node_data]
    colors = [d['color'] for d in node_data]
    statuses = [d['status'] for d in node_data]
    y_pos = np.arange(len(names))
    bars = ax.barh(y_pos, medians, color=colors, alpha=0.8, edgecolor='white', linewidth=2)
    for i, (bar, median, status) in enumerate(zip(bars, medians, statuses)):
        width = bar.get_width()
        ax.text(width + max(medians) * 0.01, bar.get_y() + bar.get_height()/2, f'{median:.1f}s ({status})', ha='left', va='center', fontweight='bold', fontsize=10)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(names, fontsize=11)
    ax.set_xlabel('Median Response Time (seconds)', fontsize=12)
    ax.set_title('DeSo Node Performance Ranking\nMedian Response Times (24h)', fontsize=14, fontweight='bold', pad=20)
    ax.axvspan(0, 15, alpha=0.1, color='green', label='Excellent (< 15s)')
    ax.axvspan(15, 30, alpha=0.1, color='yellow', label='Good (15-30s)')
    ax.axvspan(30, max(medians) * 1.1, alpha=0.1, color='red', label='Slow (> 30s)')
    ax.grid(True, axis='x', alpha=0.3)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(loc='lower right', fontsize=10)
    plt.tight_layout()
    plt.savefig("daily_gauge.png", dpi=300, bbox_inches='tight')
    plt.close()
    logging.info("🎯 Daily performance gauge saved as 'daily_gauge.png'")

def daily_post():
    logging.info("📋 DesoMonitor: Starting daily summary post creation...")
    generate_daily_graph(GRAPH_DAYS)
    generate_gauge()
    body = f"\U0001F4C8 Daily Node Performance Summary\n{POST_TAG}"
    try:
        save_measurements()
        logging.info("📤 Posting daily summary to DeSo...")
        client = DeSoDexClient(is_testnet=False, seed_phrase_or_hex=SEED_HEX, node_url=NODES[0])  # SEED_HEX from DESO_SEED_HEX
        # Upload all graph images and get their URLs
        image_url1 = client.upload_image("daily_performance_stacked.png", PUBLIC_KEY)
        image_url2 = client.upload_image("daily_performance_bar.png", PUBLIC_KEY)
        post_resp = client.submit_post(
            updater_public_key_base58check=PUBLIC_KEY,
            body=body,
            parent_post_hash_hex=None,
            title="",
            image_urls=[image_url1, image_url2],
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
    global NODES, SCHEDULE_INTERVAL, DAILY_POST_TIME, POST_TAG, GRAPH_DAYS, measurements
    logging.info("📅 DesoMonitor: Daily scheduler started")

    # Wait until 5 minutes before the next daily post to generate the graph
    while True:
        now = datetime.datetime.utcnow()
        target = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if now > target:
            target += datetime.timedelta(days=1)
        graph_time = target - datetime.timedelta(minutes=5)
        sleep_time = (graph_time - now).total_seconds()
        if sleep_time > 0:
            logging.info(f"⏰ DesoMonitor: Next graph generation in {int(sleep_time//60)}m {int(sleep_time%60)}s at {graph_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            time.sleep(sleep_time)
        # Generate the graph for the last GRAPH_DAYS days
        generate_daily_graph(GRAPH_DAYS)
        generate_gauge()
        # Wait until 0:00 to post the daily summary
        now = datetime.datetime.utcnow()
        sleep_to_post = (target - now).total_seconds()
        if sleep_to_post > 0:
            logging.info(f"⏰ DesoMonitor: Waiting {int(sleep_to_post//60)}m {int(sleep_to_post%60)}s to post daily summary at {target.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            time.sleep(sleep_to_post)
        # Re-read config at daily restart
        config_result = load_config()
        if len(config_result) == 6:
            NODES, SCHEDULE_INTERVAL, DAILY_POST_TIME, POST_TAG, GRAPH_DAYS, MODE = config_result
        else:
            NODES, SCHEDULE_INTERVAL, DAILY_POST_TIME, POST_TAG, GRAPH_DAYS = config_result
        # Re-init measurements for new/removed nodes
        for node in NODES:
            if node not in measurements:
                measurements[node] = []
        for node in list(measurements.keys()):
            if node not in NODES:
                del measurements[node]
        # Create new daily post with the just-generated graph
        new_parent_post_hash = daily_post()
        if new_parent_post_hash:
            parent_post_hash = new_parent_post_hash
            logging.info("🔄 Daily post created, measurements continue under new post...")

if __name__ == "__main__":
    logging.info("🚀 DesoMonitor: Starting up...")
    logging.info(f"📊 Configuration: {len(NODES)} nodes, {SCHEDULE_INTERVAL}s interval")
    for i, node in enumerate(NODES, 1):
        logging.info(f"   Node {i}: {node}")

    # --- Create or find today's daily post (with graph of last GRAPH_DAYS measurements) ---
    logging.info("📋 Creating today's daily summary post (with graph)...")

    # --- Shared parent_post_hash and lock for thread safety ---
    parent_post_hash = None
    parent_post_hash_lock = Lock()

    def get_parent_post_hash():
        with parent_post_hash_lock:
            return parent_post_hash

    def set_parent_post_hash(new_hash):
        global parent_post_hash
        with parent_post_hash_lock:
            parent_post_hash = new_hash

    # --- Start measurement posting thread (uses latest parent_post_hash) ---
    def measurement_thread():
        logging.info("[DesoMonitor] Measurement thread started.")
        measurement_count = 0
        last_config = None
        while True:
            # Always reload config and parent hash before each cycle
            config_result = load_config()
            if len(config_result) == 6:
                nodes, schedule_interval, daily_post_time, post_tag, graph_days, mode = config_result
            else:
                nodes, schedule_interval, daily_post_time, post_tag, graph_days = config_result
                mode = "DAILY-CYCLE"
            # Update globals for this cycle
            global NODES, SCHEDULE_INTERVAL, DAILY_POST_TIME, POST_TAG, GRAPH_DAYS, MODE
            NODES = nodes
            SCHEDULE_INTERVAL = schedule_interval
            DAILY_POST_TIME = daily_post_time
            POST_TAG = post_tag
            GRAPH_DAYS = graph_days
            MODE = mode
            # Ensure measurements dict is up to date
            for node in NODES:
                if node not in measurements:
                    measurements[node] = []
            for node in list(measurements.keys()):
                if node not in NODES:
                    del measurements[node]
            current_hash = get_parent_post_hash()
            if not current_hash:
                logging.warning("Waiting for parent_post_hash to be set...")
                time.sleep(10)
                continue
            measurement_count += 1
            logging.info(f"[DesoMonitor] Starting measurement cycle #{measurement_count} with parent_post_hash={current_hash}")
            for i, node in enumerate(NODES, 1):
                logging.info(f"🔍 DesoMonitor: Processing node {i}/{len(NODES)}: {node} (parent_post_hash={current_hash})")
                try:
                    post_measurement(node, current_hash)
                except Exception as e:
                    logging.error(f"❌ ERROR: Exception during monitoring node {node}: {e}")
                    print(f"[DesoMonitor] ERROR posting measurement for node {node}: {e}")
                    measurements[node].append((datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"), None))
            next_run = datetime.datetime.utcnow() + datetime.timedelta(seconds=SCHEDULE_INTERVAL)
            logging.info(f"💤 DesoMonitor: Measurement cycle #{measurement_count} complete. Next run at {next_run.strftime('%H:%M:%S UTC')}")
            print(f"[DesoMonitor] Measurement cycle #{measurement_count} complete. Next run at {next_run.strftime('%H:%M:%S UTC')}")
            time.sleep(SCHEDULE_INTERVAL)

    logging.info("📡 Starting scheduled measurements thread...")
    threading.Thread(target=measurement_thread, daemon=True).start()

    # --- Start daily scheduler thread for daily rollovers ---
    def daily_scheduler_with_update():
        global NODES, SCHEDULE_INTERVAL, DAILY_POST_TIME, POST_TAG, GRAPH_DAYS, MODE, measurements
        logging.info("📅 DesoMonitor: Daily scheduler started")
        while True:
            now = datetime.datetime.utcnow()
            target = now.replace(hour=0, minute=0, second=0, microsecond=0)
            if now > target:
                target += datetime.timedelta(days=1)
            graph_time = target - datetime.timedelta(minutes=5)
            sleep_time = (graph_time - now).total_seconds()
            if sleep_time > 0:
                logging.info(f"⏰ DesoMonitor: Next graph generation in {int(sleep_time//60)}m {int(sleep_time%60)}s at {graph_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                time.sleep(sleep_time)
            generate_daily_graph(GRAPH_DAYS)
            generate_gauge()
            now = datetime.datetime.utcnow()
            sleep_to_post = (target - now).total_seconds()
            if sleep_to_post > 0:
                logging.info(f"⏰ DesoMonitor: Waiting {int(sleep_to_post//60)}m {int(sleep_to_post%60)}s to post daily summary at {target.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                time.sleep(sleep_to_post)
            # Reload config and update all globals for the new day
            config_result = load_config()
            if len(config_result) == 6:
                NODES, SCHEDULE_INTERVAL, DAILY_POST_TIME, POST_TAG, GRAPH_DAYS, MODE = config_result
            else:
                NODES, SCHEDULE_INTERVAL, DAILY_POST_TIME, POST_TAG, GRAPH_DAYS = config_result
                MODE = "DAILY-CYCLE"
            for node in NODES:
                if node not in measurements:
                    measurements[node] = []
            for node in list(measurements.keys()):
                if node not in NODES:
                    del measurements[node]
            # Create new daily post and update parent_post_hash
            new_parent_post_hash = daily_post()
            if new_parent_post_hash:
                set_parent_post_hash(new_parent_post_hash)
                logging.info("🔄 Daily post created, measurements continue under new post...")

    logging.info("📅 Starting daily scheduler thread...")
    threading.Thread(target=daily_scheduler_with_update, daemon=True).start()

    # --- Initial daily post and set parent_post_hash ---
    logging.info("📋 Creating today's daily summary post (with graph)...")
    first_parent_post_hash = daily_post()
    if not first_parent_post_hash:
        logging.error("❌ Could not create or find today's daily post. Exiting.")
        exit(1)
    set_parent_post_hash(first_parent_post_hash)
    logging.info(f"🧵 Using parent_post_hash for measurements: {first_parent_post_hash}")

    logging.info("💤 DesoMonitor: Ready and running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logging.info("🛑 DesoMonitor: Shutting down gracefully...")
        print("\nDesoMonitor stopped.")
