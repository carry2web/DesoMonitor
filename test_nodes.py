#!/usr/bin/env python3
"""
Test script to check if DeSo nodes can accept posts
Integrates with NodeManager for configuration management
"""

import time
import datetime
import logging
from dotenv import load_dotenv
import os
from deso_sdk import DeSoDexClient
from node_manager import NodeManager, update_nodes_from_test_results

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('node_test.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

load_dotenv()
PUBLIC_KEY = os.getenv("DESO_PUBLIC_KEY").replace('"','').replace("'","").strip()
SEED_HEX = os.getenv("DESO_SEED_HEX").replace('"','').replace("'","").strip()

def test_node_post_capability(node_url):
    """
    Test if a node can accept and process posts
    Returns: (success, post_time, confirm_time, error_msg)
    """
    logging.info(f"🔍 Testing node: {node_url}")
    
    try:
        # Test connection and post submission
        start_time = time.time()
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        client = DeSoDexClient(is_testnet=False, seed_phrase_or_hex=SEED_HEX, node_url=node_url)
        
        # Test post content
        test_body = f"🧪 Node Test\nTesting post capability for DesoMonitor\nTimestamp: {timestamp}\nNode: {node_url}\n#nodetesting"
        
        # Submit test post
        post_start = time.time()
        post_resp = client.submit_post(
            updater_public_key_base58check=PUBLIC_KEY,
            body=test_body,
            parent_post_hash_hex=None,  # Top-level post
            title="",
            image_urls=[],
            video_urls=[],
            post_extra_data={"NodeTest": "true", "TestNode": node_url},
            min_fee_rate_nanos_per_kb=1000,
            is_hidden=False,
            in_tutorial=False
        )
        
        submit_resp = client.sign_and_submit_txn(post_resp)
        txn_hash = submit_resp.get("TxnHashHex")
        post_time = time.time() - post_start
        
        logging.info(f"✅ POST successful for {node_url} in {post_time:.2f}s (TxnHash: {txn_hash[:8]}...)")
        
        # Test transaction confirmation
        confirm_start = time.time()
        try:
            client.wait_for_commitment_with_timeout(txn_hash, 30.0)  # 30 second timeout for testing
            confirm_time = time.time() - confirm_start
            logging.info(f"✅ CONFIRMATION successful for {node_url} in {confirm_time:.2f}s")
            return True, post_time, confirm_time, None
            
        except Exception as confirm_err:
            confirm_time = time.time() - confirm_start
            logging.warning(f"⚠️ CONFIRMATION failed for {node_url} after {confirm_time:.2f}s: {confirm_err}")
            return True, post_time, None, f"Confirmation timeout: {confirm_err}"
            
    except Exception as e:
        total_time = time.time() - start_time
        logging.error(f"❌ POST failed for {node_url} after {total_time:.2f}s: {e}")
        return False, None, None, str(e)

def test_node_api_endpoints(node_url):
    """
    Test if node has required API endpoints
    """
    import requests
    
    endpoints_to_test = [
        "/api/v0/get-single-post",
        "/api/v0/submit-post", 
        "/api/v0/get-txn",
        "/api/v0/health-check"
    ]
    
    working_endpoints = []
    failed_endpoints = []
    
    for endpoint in endpoints_to_test:
        try:
            # Simple GET request to test endpoint existence
            response = requests.get(f"{node_url.rstrip('/')}{endpoint}", timeout=10)
            if response.status_code in [200, 400, 405]:  # 400/405 means endpoint exists but needs POST
                working_endpoints.append(endpoint)
                logging.info(f"✅ {node_url}{endpoint} - Available (Status: {response.status_code})")
            else:
                failed_endpoints.append(endpoint)
                logging.warning(f"⚠️ {node_url}{endpoint} - Unexpected status: {response.status_code}")
                
        except Exception as e:
            failed_endpoints.append(endpoint)
            logging.error(f"❌ {node_url}{endpoint} - Error: {e}")
    
    return working_endpoints, failed_endpoints

def test_all_nodes():
    """
    Test all nodes from configuration and generate report
    """
    logging.info("🚀 Starting comprehensive node testing...")
    
    # Load node manager
    node_manager = NodeManager()
    all_nodes = node_manager.get_all_nodes()
    
    if not all_nodes:
        logging.error("❌ No nodes found in configuration")
        return []
    
    results = []
    
    for node_config in all_nodes:
        node_url = node_config["url"]
        node_name = node_config.get("name", "Unknown")
        
        logging.info(f"\n{'='*60}")
        logging.info(f"Testing: {node_name} ({node_url})")
        logging.info(f"{'='*60}")
        
        # Test API endpoints
        working_endpoints, failed_endpoints = test_node_api_endpoints(node_url)
        
        # Test post capability  
        can_post, post_time, confirm_time, error = test_node_post_capability(node_url)
        
        # Determine node type based on capabilities
        node_type = "Unknown"
        if can_post and confirm_time is not None:
            node_type = "Full Node (TxIndex enabled)"
        elif can_post and confirm_time is None:
            if "txindex" in str(error).lower():
                node_type = "Validator (TxIndex disabled/syncing)"
            else:
                node_type = "Validator (No TxIndex)"
        else:
            node_type = "Offline/Broken"
        
        result = {
            "node": node_url,
            "name": node_name,
            "can_post": can_post,
            "post_time": post_time,
            "confirm_time": confirm_time,
            "error": error,
            "node_type": node_type,
            "working_endpoints": working_endpoints,
            "failed_endpoints": failed_endpoints,
            "recommended": can_post and confirm_time is not None  # Only recommend nodes with TxIndex
        }
        
        results.append(result)
        
        # Brief pause between tests
        time.sleep(2)
    
    return results

def generate_test_report(results):
    """
    Generate and log comprehensive test report
    """
    logging.info(f"\n{'='*60}")
    logging.info("📊 NODE TEST SUMMARY REPORT")
    logging.info(f"{'='*60}")
    
    full_nodes = []
    validators = []
    broken_nodes = []
    
    for result in results:
        node = result["node"]
        name = result["name"]
        node_type = result.get("node_type", "Unknown")
        
        if "Full Node" in node_type:
            full_nodes.append((node, name, result))
            status = "✅ FULL NODE (TxIndex)"
            details = f"POST: {result['post_time']:.2f}s, CONFIRM: {result['confirm_time']:.2f}s"
        elif "Validator" in node_type:
            validators.append((node, name, result))
            status = "⚠️ VALIDATOR (No TxIndex)"
            details = f"POST: {result['post_time']:.2f}s, CONFIRM: Not available"
        else:
            broken_nodes.append((node, name, result))
            status = "❌ OFFLINE/BROKEN"
            details = result['error'] or "Connection failed"
        
        logging.info(f"{status:25} {name}")
        logging.info(f"{'':25} {node}")
        logging.info(f"{'':25} {details}")
        logging.info(f"{'':25} Type: {node_type}")
        logging.info("")
    
    # Summary by type
    logging.info("🎯 SUMMARY BY NODE TYPE:")
    logging.info(f"   Full Nodes (TxIndex enabled): {len(full_nodes)}")
    for node_url, name, result in full_nodes:
        logging.info(f"   ✅ {name} - Suitable for DesoMonitor")
    
    if validators:
        logging.info(f"   Validators (No TxIndex): {len(validators)}")
        for node_url, name, result in validators:
            logging.info(f"   ⚠️ {name} - Can POST but can't confirm transactions")
    
    if broken_nodes:
        logging.info(f"   Broken/Offline: {len(broken_nodes)}")
        for node_url, name, result in broken_nodes:
            logging.info(f"   ❌ {name} - Not accessible")
    
    logging.info("\n💡 EXPLANATION:")
    logging.info("   • Full Nodes: Run complete blockchain with TxIndex for transaction lookup")
    logging.info("   • Validators: Focus on consensus, may not have TxIndex enabled")
    logging.info("   • DesoMonitor needs TxIndex to confirm transaction commitment")
    logging.info("   • Validators can accept posts but can't provide confirmation timing")
    
    return results

if __name__ == "__main__":
    print("🧪 DeSo Node Testing Script")
    print("Testing nodes for DesoMonitor compatibility...")
    print("This will make test posts to verify functionality.\n")
    
    # Test all nodes and generate report
    results = test_all_nodes()
    
    if results:
        # Generate detailed report
        generate_test_report(results)
        
        # Update node configuration with test results
        update_nodes_from_test_results(results)
        
        print("\n" + "="*60)
        print("✅ Node testing complete!")
        print(f"✅ Updated configuration with {len(results)} node test results")
        print("✅ Check 'node_test.log' for detailed results.")
        print("✅ Configuration updated in 'nodes_config.json'")
        print("="*60)
    else:
        print("❌ No nodes tested. Check configuration and try again.")
