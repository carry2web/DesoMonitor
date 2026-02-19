import os
import json
import datetime
import matplotlib.pyplot as plt
import requests
from dotenv import load_dotenv
from deso_sdk import DeSoDexClient

# Load keys from .env
load_dotenv()
SEED_HEX = os.getenv("DESO_SEED_HEX", "").replace('"','').replace("'","").strip()
PUBLIC_KEY = os.getenv("DESO_PUBLIC_KEY", "").replace('"','').replace("'","").strip()

# Hardcoded config post hash
CONFIG_POST_HASH = "91522722c35f6b38588f059723ae3a401a92ae7a09826c6a987bf511d02f21aa"

# Helper to fetch config
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
    config = json.loads(body)
    return config

# Helper to fetch all measurement comments for a given parent post
# (Assumes parent post is the daily summary post)
def fetch_measurements_for_day(parent_post_hash):
    # Fetch all comments (replies) to the daily post using /get-single-post
    url = "https://node.deso.org/api/v0/get-single-post"
    # Dynamically determine expected number of measurement comments
    config = fetch_config_from_post(CONFIG_POST_HASH)
    nodes = config.get("NODES", ["https://node.deso.org"])
    if isinstance(nodes, str):
        nodes = [n.strip() for n in nodes.split(",") if n.strip()]
    schedule_interval = int(config.get("SCHEDULE_INTERVAL", 3600))
    # Measurements per day per node
    per_node_per_day = int(24 * 60 * 60 / schedule_interval)
    expected_comments = len(nodes) * per_node_per_day
    comment_limit = int(expected_comments * 1.2)  # 20% buffer
    payload = {"PostHashHex": parent_post_hash, "CommentOffset": 0, "CommentLimit": comment_limit}
    try:
        resp = requests.post(url, json=payload)
        resp.raise_for_status()
        post_data = resp.json()
    except Exception as e:
        print(f"Error fetching post: {e}")
        return []

    # Print all raw comments for debug
    comments = post_data.get("PostFound", {}).get("Comments", [])
    print(f"\n[DEBUG] Raw comments fetched from /get-single-post for post {parent_post_hash}:")
    for idx, c in enumerate(comments):
        body = c.get("Body", "")
        poster = c.get("PosterPublicKeyBase58Check", "")
        comment_hash = c.get("PostHashHex", "")
        parent_hash = c.get("ParentPostHashHex", "")
        print(f"  [{idx}] Poster: {poster}\n      PostHashHex: {comment_hash}\n      ParentPostHashHex: {parent_hash}\n      Body: {body}\n---")

    # Filter by measurement tag
    measurement_comments = [c for c in comments if "#desomonitormeasurement" in c.get("Body", "")]
    print(f"[DEBUG] Found {len(measurement_comments)} measurement comments with tag '#desomonitormeasurement'.")
    return measurement_comments



# Helper to find daily post hash for a given date
def find_daily_post_hash_for_date(date_str):
    client = DeSoDexClient(is_testnet=False, seed_phrase_or_hex=SEED_HEX)
    url = f"{client.node_url}/api/v0/get-posts-for-public-key"
    config = fetch_config_from_post(CONFIG_POST_HASH)
    nodes = config.get("NODES", ["https://node.deso.org"])
    if isinstance(nodes, str):
        nodes = [n.strip() for n in nodes.split(",") if n.strip()]
    schedule_interval = int(config.get("SCHEDULE_INTERVAL", 3600))
    graph_days = int(config.get("GRAPH_DAYS", 1))
    per_node_per_day = int(24 * 60 * 60 / schedule_interval)
    expected_posts = len(nodes) * per_node_per_day * graph_days
    num_to_fetch = int(expected_posts * 1.2)  # 20% buffer
    payload = {
        "PublicKeyBase58Check": PUBLIC_KEY,
        "NumToFetch": num_to_fetch,
        "MediaRequired": False
    }
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    posts = resp.json().get("Posts", [])
    target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    tagged_posts = []
    for post in posts:
        body = post.get("Body", "")
        if "#desomonitormeasurement" in body:
            post_timestamp = post.get("TimestampNanos")
            post_dt = datetime.datetime.utcfromtimestamp(post_timestamp / 1e9)
            tagged_posts.append((post_dt, post.get("PostHashHex")))
    # Sort by date descending
    tagged_posts.sort(reverse=True)
    # Try to find exact date
    for post_dt, post_hash in tagged_posts:
        if post_dt.date() == target_date.date():
            return post_hash, post_dt
    # If not found, find the closest previous post
    for post_dt, post_hash in tagged_posts:
        if post_dt.date() < target_date.date():
            print(f"No post found for {date_str}, using closest previous post from {post_dt.date()}.")
            return post_hash, post_dt
    # If nothing found, print available dates
    if tagged_posts:
        available_dates = sorted(set(dt.date() for dt, _ in tagged_posts))
        print(f"No post found for {date_str}. Available dates: {', '.join(str(d) for d in available_dates)}")
    return None, None

# Main logic

if __name__ == "__main__":
    config = fetch_config_from_post(CONFIG_POST_HASH)
    NODES = config.get("NODES", ["https://node.deso.org"])
    GRAPH_DAYS = int(config.get("GRAPH_DAYS", 1))

    # Prompt for date
    date_str = input("Enter the date for the daily graph (YYYY-MM-DD): ").strip()
    parent_post_hash, post_dt = find_daily_post_hash_for_date(date_str)
    if not parent_post_hash:
        print(f"Could not find daily post for {date_str} on-chain.")
        exit(1)
    print(f"Found daily post hash for {date_str}: {parent_post_hash}")

    comments = fetch_measurements_for_day(parent_post_hash)
    if not comments:
        print(f"No measurement comments found for post hash {parent_post_hash}.")
        # Debug: Try to fetch and print the raw API response for diagnosis
        print("Debug: Fetching raw API response for comments...")
        config = fetch_config_from_post(CONFIG_POST_HASH)
        nodes = config.get("NODES", ["https://node.deso.org"])
        if isinstance(nodes, str):
            nodes = [n.strip() for n in nodes.split(",") if n.strip()]
        schedule_interval = int(config.get("SCHEDULE_INTERVAL", 3600))
        per_node_per_day = int(24 * 60 * 60 / schedule_interval)
        comment_limit = int(len(nodes) * per_node_per_day * 1.2)
        client = DeSoDexClient(is_testnet=False, seed_phrase_or_hex=SEED_HEX)
        url = f"{client.node_url}/api/v0/get-posts-stateless"
        payload = {
            "PostHashHex": parent_post_hash,
            "FetchParents": False,
            "CommentOffset": 0,
            "CommentLimit": comment_limit
        }
        try:
            resp = requests.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            print("Raw API response for comments:")
            import json as _json
            print(_json.dumps(data, indent=2)[:5000])  # Print up to 5000 chars
        except Exception as e:
            print(f"Error fetching raw comments: {e}")
        exit(1)
    print(f"Fetched {len(comments)} measurement comment posts:")
    for i, comment in enumerate(comments, 1):
        print(f"--- Comment {i} ---")
        print(f"Body: {comment.get('Body','')}")
        print(f"Node: {comment.get('PostExtraData',{}).get('Node','')}")
        print(f"ParentStakeID: {comment.get('ParentStakeID','')}")
        print(f"-------------------")

    # Parse measurement data for POST and CONFIRM
    node_post = {node: [] for node in NODES}
    node_confirm = {node: [] for node in NODES}
    for comment in comments:
        body = comment.get("Body", "")
        node = comment.get("PostExtraData", {}).get("Node")
        post_time = None
        confirm_time = None
        timestamp = None
        # Try to parse POST, CONFIRM, and timestamp from body
        for line in body.splitlines():
            if line.startswith("POST:"):
                try:
                    post_time = float(line.split(":",1)[1].split()[0])
                except:
                    pass
            if line.startswith("CONFIRM:"):
                try:
                    confirm_time = float(line.split(":",1)[1].split()[0])
                except:
                    pass
            if line.startswith("Timestamp:"):
                try:
                    timestamp = line.split(":",1)[1].strip()
                except:
                    pass
        if node and timestamp:
            if post_time is not None:
                node_post[node].append((timestamp, post_time))
            if confirm_time is not None:
                node_confirm[node].append((timestamp, confirm_time))

    # Plot POST and CONFIRM speeds in subplots, line+marker style
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    cutoff = post_dt - datetime.timedelta(days=0)
    end_cutoff = post_dt + datetime.timedelta(days=GRAPH_DAYS)

    # POST Speed
    for node in NODES:
        filtered = [(t, e) for t, e in node_post[node]
                    if cutoff <= datetime.datetime.strptime(t, "%Y-%m-%d %H:%M:%S UTC") < end_cutoff]
        times = [datetime.datetime.strptime(t, "%Y-%m-%d %H:%M:%S UTC") for t, e in filtered]
        elapsed = [e for t, e in filtered]
        ax1.plot(times, elapsed, marker='o', markersize=3, linestyle='-', label=node)
        print(f"POST graph data for {node}: {len(elapsed)} measurements from {date_str} + {GRAPH_DAYS} days")
    ax1.set_ylabel("POST Speed (seconds)")
    ax1.set_title("DeSo Node POST Speed (Transaction Submission)")
    ax1.legend()
    ax1.grid(True, linestyle=':')

    # CONFIRM Speed
    for node in NODES:
        filtered = [(t, e) for t, e in node_confirm[node]
                    if cutoff <= datetime.datetime.strptime(t, "%Y-%m-%d %H:%M:%S UTC") < end_cutoff]
        times = [datetime.datetime.strptime(t, "%Y-%m-%d %H:%M:%S UTC") for t, e in filtered]
        elapsed = [e for t, e in filtered]
        ax2.plot(times, elapsed, marker='o', markersize=3, linestyle='-', label=node)
        print(f"CONFIRM graph data for {node}: {len(elapsed)} measurements from {date_str} + {GRAPH_DAYS} days")
    ax2.set_xlabel("Time")
    ax2.set_ylabel("CONFIRMATION Speed (seconds)")
    ax2.set_title("DeSo Node CONFIRMATION Speed (Transaction Commitment - Full Nodes Only)")
    ax2.legend()
    ax2.grid(True, linestyle=':')

    plt.tight_layout()
    plt.savefig("daily_performance.png")
    plt.close()
    print("Graph saved as daily_performance.png")
