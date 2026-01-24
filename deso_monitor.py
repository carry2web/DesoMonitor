import time
import threading
import datetime
import matplotlib.pyplot as plt
import os
import logging
from dotenv import load_dotenv
from deso_sdk import DeSoDexClient
import requests

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

# --- On-chain config ---
import json
from deso_sdk import DeSoDexClient

# Hardcoded config post hash (replace with your config post hash)
CONFIG_POST_HASH = "91522722c35f6b38588f059723ae3a401a92ae7a09826c6a987bf511d02f21aa"

def fetch_config_from_post(post_hash):
    # Use mainnet node and always provide seed
    client = DeSoDexClient(is_testnet=False, seed_phrase_or_hex=SEED_HEX)
    url = f"{client.node_url}/api/v0/get-single-post"
    print(f"Fetching config post from URL: {url} for hash: {post_hash}")
    payload = {"PostHashHex": post_hash}
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    post = resp.json().get("PostFound")
    if not post:
        raise Exception("Config post not found")

    body = post.get("Body", "")
    logging.info(f"DEBUG: Raw config post body (len={len(body)}):\n{body}")
    logging.info(f"DEBUG: Raw config post body repr: {repr(body)}")
    print(f"\n--- FETCH CONFIG POST BODY ---\n{body}\n--- END BODY ---\n")
    try:
        config = json.loads(body)
        print(f"\n--- PARSED CONFIG ---\n{config}\n--- END CONFIG ---\n")
    except Exception as e:
        logging.error(f"ERROR: Failed to parse config post body as JSON. Exception: {e}")
        logging.error(f"ERROR: Raw config post body repr: {repr(body)}")
        print(f"Config post body (repr): {repr(body)}")
        raise Exception(f"Config post body is not valid JSON: {e}")
    return config



# Always load SEED_HEX and PUBLIC_KEY from .env for security (never from config post)
load_dotenv()
SEED_HEX = os.getenv("DESO_SEED_HEX",""").replace('"','').replace("'",""").strip()
PUBLIC_KEY = os.getenv("DESO_PUBLIC_KEY",""").replace('"','').replace("'",""").strip()

# Try to fetch config from on-chain post
try:
    config = fetch_config_from_post(CONFIG_POST_HASH)
    NODES = config.get("NODES", ["https://node.deso.org"])
    SCHEDULE_INTERVAL = int(config.get("SCHEDULE_INTERVAL", 3600))
    DAILY_POST_TIME = config.get("DAILY_POST_TIME", "00:00")
    POST_TAG = config.get("POST_TAG", "#desomonitormeasurement")
    if isinstance(NODES, str):
        NODES = [n.strip() for n in NODES.split(",") if n.strip()]
    logging.info(f"DEBUG: Loaded NODES from config post: {NODES} (count={len(NODES)})")
except Exception as e:
    print(f"Error loading config from chain: {e}. Falling back to .env config.")
    NODES = os.getenv("DESO_NODES", "https://node.deso.org,https://desocialworld.desovalidator.net,https://safetynet.social")
    NODES = [n.strip() for n in NODES.split(",") if n.strip()]
    SCHEDULE_INTERVAL = int(os.getenv("SCHEDULE_INTERVAL", "3600"))
    DAILY_POST_TIME = os.getenv("DAILY_POST_TIME", "00:00")
    POST_TAG = os.getenv("POST_TAG", "#desomonitormeasurement")

# Data storage
measurements = {node: [] for node in NODES}


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
        
        post_resp = None
        try:
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
            # Save raw response text for debugging
            raw_post_resp = None
            try:
                raw_post_resp = json.dumps(post_resp)
            except Exception:
                raw_post_resp = str(post_resp)
            try:
                submit_resp = client.sign_and_submit_txn(post_resp)
            except Exception as post_err:
                if raw_post_resp is not None:
                    print(f"\n--- ERROR RESPONSE FROM NODE (SDK payload) ---\n{raw_post_resp}\n--- END ERROR RESPONSE ---\n")
                    logging.error(f"ERROR RESPONSE FROM NODE {node}: {raw_post_resp}")
                print(f"Error posting to {node}: {post_err}")
                logging.error(f"Error posting to {node}: {post_err}")
                measurements[node].append((datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"), None))
                # Fallback debug block will run below
                raise post_err
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
        except Exception as post_err:
            # Always print/log the raw response text if available
            raw_post_resp = None
            if post_resp is not None:
                try:
                    raw_post_resp = json.dumps(post_resp)
                except Exception:
                    raw_post_resp = str(post_resp)
            if raw_post_resp is not None:
                print(f"\n--- ERROR RESPONSE FROM NODE ---\n{raw_post_resp}\n--- END ERROR RESPONSE ---\n")
                logging.error(f"ERROR RESPONSE FROM NODE {node}: {raw_post_resp}")
            print(f"Error posting to {node}: {post_err}")
            logging.error(f"Error posting to {node}: {post_err}")
            measurements[node].append((datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"), None))
            # Fallback: try direct requests.post for debug (always runs on error)
            try:
                node_url = node.rstrip('/') + '/api/v0/submit-post'
                # If SDK payload is not a dict, build a minimal valid payload
                if isinstance(post_resp, dict) and post_resp:
                    debug_payload = post_resp
                else:
                    debug_payload = {
                        "UpdaterPublicKeyBase58Check": PUBLIC_KEY,
                        "Body": temp_comment,
                        "ParentStakeID": parent_post_hash or "",
                        "Title": "",
                        "ImageURLs": [],
                        "VideoURLs": [],
                        "PostExtraData": {"Node": node},
                        "MinFeeRateNanosPerKB": 1000,
                        "IsHidden": False,
                        "InTutorial": False
                    }
                print(f"\n--- FALLBACK DEBUG ---\nPOST to: {node_url}\nPayload: {json.dumps(debug_payload, indent=2)}\n--- END PAYLOAD ---\n")
                debug_resp = requests.post(node_url, json=debug_payload)
                print(f"Status code: {debug_resp.status_code}")
                print(f"Headers: {debug_resp.headers}")
                print(f"\n--- RAW NODE RESPONSE ---\n{debug_resp.text}\n--- END RAW NODE RESPONSE ---\n")
                print(f"\n--- RAW NODE RESPONSE REPR ---\n{repr(debug_resp.text)}\n--- END RAW NODE RESPONSE REPR ---\n")
                if len(debug_resp.text) > 2000:
                    print(f"\n--- RAW NODE RESPONSE (first 2000 chars) ---\n{debug_resp.text[:2000]}\n--- END PARTIAL RESPONSE ---\n")
                logging.error(f"RAW NODE RESPONSE {node}: {debug_resp.text}")
            except Exception as fallback_err:
                print(f"Could not fetch raw node response: {fallback_err}")
    except Exception as e:
        elapsed = time.time() - start
        logging.error(f"❌ ERROR: Failed to post to {node} after {elapsed:.2f}s: {e}")
        print(f"Error posting to {node}: {e}")
        measurements[node].append((datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"), None))

def scheduled_measurements(parent_post_hash):
    logging.info(f"🚀 DesoMonitor: Starting scheduled measurements every {SCHEDULE_INTERVAL} seconds")
    measurement_count = 0
    while True:
        measurement_count += 1
        logging.info(f"📊 DesoMonitor: Starting measurement cycle #{measurement_count} for {len(NODES)} nodes")
        logging.info(f"DEBUG: Full NODES list for monitoring: {NODES}")
        for i, node in enumerate(NODES, 1):
            logging.info(f"🔍 DesoMonitor: Processing node {i}/{len(NODES)}: {node}")
            try:
                post_measurement(node, parent_post_hash)
            except Exception as e:
                logging.error(f"❌ ERROR: Exception during monitoring node {node}: {e}")
                # Still log the failed attempt for visibility
                measurements[node].append((datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"), None))
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
    # Direct test/debug call to fetch_config_from_post
    print("\n--- DEBUG: Fetching config post directly ---")
    try:
        debug_config = fetch_config_from_post(CONFIG_POST_HASH)
        print("Fetched config post body and parsed config:")
        print(debug_config)
    except Exception as e:
        print(f"Error fetching config post directly: {e}")
    print("--- END DEBUG ---\n")

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
