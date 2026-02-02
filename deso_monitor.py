import threading
import datetime
import matplotlib.pyplot as plt
import numpy as np
import os
import logging
from dotenv import load_dotenv
from deso_sdk_fork.deso_sdk import DeSoDexClient
import requests

import time
import threading
import datetime
import matplotlib.pyplot as plt
import os
            generate_daily_graph()
            print(f"[DesoMonitor] Done. Exiting after single daily graph post for {single_date} (from MODE config).")
            sys.exit(0)
        except Exception as e:
            print(f"[DesoMonitor] Invalid MODE config for SINGLE-DAILY-GRAPH: {e}")
            sys.exit(1)
    # ...existing code for main()...
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
SEED_HEX = os.getenv("DESO_SEED_HEX",""").replace('"','').replace("'",""").strip()
PUBLIC_KEY = os.getenv("DESO_PUBLIC_KEY",""").replace('"','').replace("'",""").strip()

# Load GRAPH_DAYS from .env or config (default 7)
GRAPH_DAYS = int(os.getenv("GRAPH_DAYS", "7"))


# --- Config loader ---
def load_config():
    try:
        config = fetch_config_from_post(CONFIG_POST_HASH)
        nodes = config.get("NODES", ["https://node.deso.org"])
        schedule_interval = int(config.get("SCHEDULE_INTERVAL", 3600))
        daily_post_time = config.get("DAILY_POST_TIME", "00:00")
        post_tag = config.get("POST_TAG", "#desomonitormeasurement")
        graph_days = int(config.get("GRAPH_DAYS", GRAPH_DAYS))
        # Always prefer config post MODE over .env
        mode = config.get("MODE")
        if not mode or not isinstance(mode, str) or not mode.strip():
            mode = os.getenv("MODE", "DAILY-CYCLE")
        if isinstance(nodes, str):
            nodes = [n.strip() for n in nodes.split(",") if n.strip()]
        logging.info(f"DEBUG: Loaded NODES from config post: {nodes} (count={len(nodes)})")
        return nodes, schedule_interval, daily_post_time, post_tag, graph_days, mode
    except Exception as e:
        print(f"Error loading config from chain: {e}. Falling back to .env config.")
        nodes = os.getenv("DESO_NODES", "https://node.deso.org,https://desocialworld.desovalidator.net,https://safetynet.social")
        nodes = [n.strip() for n in nodes.split(",") if n.strip()]
        schedule_interval = int(os.getenv("SCHEDULE_INTERVAL", "3600"))
        daily_post_time = os.getenv("DAILY_POST_TIME", "00:00")
        post_tag = os.getenv("POST_TAG", "#desomonitormeasurement")
        graph_days = int(os.getenv("GRAPH_DAYS", str(GRAPH_DAYS)))
        return nodes, schedule_interval, daily_post_time, post_tag, graph_days

# Initial config load
NODES, SCHEDULE_INTERVAL, DAILY_POST_TIME, POST_TAG, GRAPH_DAYS, MODE = load_config()
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
            # After parsing measurement data, print debug info for each node
            for node, times in node_times.items():
                print(f"[DEBUG] Node: {node}, Measurements: {len(times)}")
                for t, elapsed in times:
                    print(f"  Time: {t}, Elapsed: {elapsed}")
        # Debug: print parsed measurement data for each node
        for node, times in node_times.items():
            print(f"[DEBUG] Node: {node}, Measurements: {len(times)}")
            for t, elapsed in times:
                print(f"  Time: {t}, Elapsed: {elapsed}")
    # Debug: print obscured SEED_HEX to confirm .env is read
    if SEED_HEX:
        obscured = SEED_HEX[:4] + "..." + SEED_HEX[-4:]
        logging.info(f"[DEBUG] SEED_HEX loaded: {obscured} (len={len(SEED_HEX)})")
    else:
        logging.warning("[DEBUG] SEED_HEX is empty or not loaded!")
    logging.info(f"📈 DesoMonitor: Generating performance graph for last {graph_days} days (from on-chain comments)...")
    # Fetch the most recent daily post (with the tag and comments) for each of the previous graph_days days
    client = DeSoDexClient(is_testnet=False, seed_phrase_or_hex=SEED_HEX)
    num_to_fetch = graph_days * 3 + 20  # Fetch enough to cover all days, even with extra posts
    url = f"{client.node_url}/api/v0/get-posts-for-public-key"
    # Debug: print parsed measurement data for each node (after node_times is populated)
    for node, times in node_times.items():
        print(f"[DEBUG] Node: {node}, Measurements: {len(times)}")
        for t, elapsed in times:
            print(f"  Time: {t}, Elapsed: {elapsed}")
    payload = {"PublicKeyBase58Check": PUBLIC_KEY, "NumToFetch": num_to_fetch}
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    posts = resp.json().get("Posts", [])
    # Group daily posts by UTC date, pick most recent with comments per day
    from collections import defaultdict
    daily_posts_by_date = defaultdict(list)
    post_comments_by_hash = {}
    for post in posts:
        if POST_TAG in post.get("Body", ""):
            post_time = post.get("TimestampNanos")
            if post_time:
                t = datetime.datetime.utcfromtimestamp(int(post_time) / 1e9)
                date_str = t.strftime("%Y-%m-%d")
                daily_posts_by_date[date_str].append((t, post))
    # For each of the last graph_days days, pick the most recent daily post with comments
    today = datetime.datetime.utcnow().date()
    selected_daily_posts = []
    for i in range(graph_days):
        day = today - datetime.timedelta(days=i)
        date_str = day.strftime("%Y-%m-%d")
        posts_for_day = sorted(daily_posts_by_date.get(date_str, []), key=lambda x: x[0], reverse=True)
        for t, post in posts_for_day:
            daily_post_hash = post.get("PostHashHex")
            url_single = f"{client.node_url}/api/v0/get-single-post"
            payload_single = {"PostHashHex": daily_post_hash, "CommentOffset": 0, "CommentLimit": 100}
            resp_single = requests.post(url_single, json=payload_single)
            resp_single.raise_for_status()
            comments = resp_single.json().get("PostFound", {}).get("Comments", [])
            if comments:
                selected_daily_posts.append((post, comments))
                break  # Only the most recent with comments for this day
    if not selected_daily_posts:
        logging.error("No recent daily posts with comments found for graph generation!")
        return
    # Aggregate measurement comments from all selected daily posts
    measurement_comments = []
    print("[DesoMonitor] Selected daily post dates:", [post.get('TimestampNanos') for post, _ in selected_daily_posts])
    for post, comments in selected_daily_posts:
        measurement_comments.extend([c for c in comments if POST_TAG in c.get("Body", "")])
    logging.info(f"Found {len(measurement_comments)} measurement comments from {len(selected_daily_posts)} daily posts for GRAPH_DAYS={graph_days}")
    print(f"[DesoMonitor] Found {len(measurement_comments)} measurement comments from {len(selected_daily_posts)} daily posts for GRAPH_DAYS={graph_days}")
    print("[DesoMonitor] First 5 measurement comment bodies:")
    for c in measurement_comments[:5]:
        print(c.get('Body', ''))
    # Parse measurement data
    import re
    node_times = {node: [] for node in NODES}
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=graph_days)
    for c in measurement_comments:
        body = c.get("Body", "")
        node = None
        elapsed = None
        timestamp = None
        # Try to extract node, elapsed, timestamp from body
        m_node = re.search(r"Node: (.+)", body)
        m_elapsed = re.search(r"Elapsed: ([0-9.]+) sec", body)
        m_time = re.search(r"Timestamp: ([0-9\-: ]+ UTC)", body)
        if m_node:
            node = m_node.group(1).strip()
        if m_elapsed:
            elapsed = float(m_elapsed.group(1))
        if m_time:
            timestamp = m_time.group(1).strip()
        if node in node_times and elapsed is not None and timestamp is not None:
            try:
                t = datetime.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S UTC")
                if t >= cutoff:
                    node_times[node].append((t, elapsed))
            except Exception:
                continue
    # Debug output for parsed measurement data
    for node, times in node_times.items():
        print(f"[DEBUG] Node: {node}, Measurements: {len(times)}")
        for t, elapsed in times:
            print(f"  Time: {t}, Elapsed: {elapsed}")
    # --- Restored original time series graph ---
    plt.figure(figsize=(14, 8))
    colors = plt.cm.tab10(np.linspace(0, 1, len(NODES)))
    for i, node in enumerate(NODES):
        times = [datetime.datetime.strptime(t, "%Y-%m-%d %H:%M:%S UTC") for t, e in measurements[node] if e is not None]
        elapsed = [e for t, e in measurements[node] if e is not None]
        node_name = node.replace('https://', '').replace('http://', '')
        plt.plot(times, elapsed, label=node_name, color=colors[i], linewidth=1.5, marker='o', markersize=2, alpha=0.8)
        logging.info(f"📊 Graph data for {node}: {len(elapsed)} measurements")
    plt.xlabel("Time (UTC)", fontsize=12)
    plt.ylabel("Response Time (seconds)", fontsize=12)
    plt.title("DeSo Node Performance - 24 Hour Monitoring", fontsize=14, fontweight='bold')
    if len(NODES) > 6:
        plt.legend(fontsize=9, ncol=2, loc='upper left', bbox_to_anchor=(1.02, 1))
    else:
        plt.legend(fontsize=11)
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.gca().spines['top'].set_visible(False)
    plt.gca().spines['right'].set_visible(False)
    plt.savefig("daily_performance.png", dpi=300, bbox_inches='tight')
    plt.close()
    logging.info("📈 Daily performance graph saved as 'daily_performance.png'")

def generate_gauge():
    logging.info("🎯 Generating sample daily performance gauge...")
    import numpy as np
    node_data = []
    for node in NODES:
        elapsed = [e for t, e in measurements[node] if e is not None]
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
        client = DeSoDexClient(is_testnet=False, seed_phrase_or_hex=SEED_HEX, node_url=NODES[0])
        # Upload the graph image and get the URL
        image_url = client.upload_image("daily_performance.png", PUBLIC_KEY)
        post_resp = client.submit_post(
            updater_public_key_base58check=PUBLIC_KEY,
            body=body,
            parent_post_hash_hex=None,
            title="",
            image_urls=[image_url],
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
        NODES, SCHEDULE_INTERVAL, DAILY_POST_TIME, POST_TAG, GRAPH_DAYS = load_config()
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
    main()
