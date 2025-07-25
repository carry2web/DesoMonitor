#!/usr/bin/env python3
"""
Test script to check which DeSo nodes have TxIndex enabled.
This helps identify nodes suitable for monitoring with wait_for_commitment.
"""

import time
import requests
import json
from dotenv import load_dotenv
import os

load_dotenv()

# Test nodes - remove port 17000 (protocol port) and use standard HTTP
TEST_NODES = [
    "https://node.deso.org",  # Main DeSo node - known to work
    "https://lazynina.org",
    "https://desocialworld.desovalidator.net", 
    "https://staketomeorelse.com",
    "https://revolutionarystaking.com",
    "https://notanagi.com"
]

def test_node_accessibility(node_url):
    """Test basic node accessibility and API responses"""
    print(f"\n🔍 Testing node: {node_url}")
    
    # Test 1: Basic API accessibility using get-app-state with empty body
    try:
        response = requests.post(f"{node_url}/api/v0/get-app-state", 
                              json={}, 
                              timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ API accessible: {response.status_code}")
            # Check if TxIndex info is available in app state
            if 'IsPortfolio' in data or 'IsTxIndex' in data:
                print(f"  📊 App state includes indexing info")
            return True
        else:
            print(f"  ❌ API error: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Connection failed: {e}")
        return False

def test_txindex_capability(node_url):
    """
    Test if node has TxIndex enabled by checking if we can query transactions.
    We'll try to get a known transaction - if TxIndex is disabled, this should fail.
    """
    print(f"  📊 Testing TxIndex capability...")
    
    # Test: Try to get a recent transaction to see if TxIndex is working
    try:
        # First, try to get recent posts to find a transaction hash
        response = requests.post(f"{node_url}/api/v0/get-posts-stateless", 
                               json={
                                   "NumToFetch": 5,
                                   "PostContent": "",
                                   "PostHashHex": "",
                                   "PublicKeyBase58Check": ""
                               }, 
                               timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("PostsFound"):
                # Try to get transaction info for one of these posts
                post_hash = data["PostsFound"][0]["PostHashHex"]
                print(f"    🔍 Testing transaction lookup with PostHash: {post_hash[:8]}...")
                
                # Try to get single post (this uses TxIndex)
                tx_response = requests.post(f"{node_url}/api/v0/get-single-post", 
                                          json={
                                              "PostHashHex": post_hash,
                                              "FetchParents": False,
                                              "CommentLimit": 0,
                                              "AddGlobalFeedBool": False
                                          }, 
                                          timeout=10)
                
                if tx_response.status_code == 200:
                    tx_data = tx_response.json()
                    if tx_data.get("PostFound"):
                        print(f"    ✅ TxIndex appears functional - can query transactions")
                        return True
                    else:
                        print(f"    ⚠️  TxIndex might be limited - post not found in lookup")
                        return False
                else:
                    print(f"    ❌ TxIndex lookup failed: {tx_response.status_code}")
                    return False
            else:
                print(f"    ⚠️  No posts found to test TxIndex")
                return None
        else:
            print(f"    ❌ Failed to get posts for TxIndex test: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"    ❌ TxIndex test failed: {e}")
        return None

def test_mempool_info(node_url):
    """Test if we can get mempool information which might indicate full node capabilities"""
    print(f"  🔄 Testing mempool access...")
    
    try:
        # Try to get mempool stats
        response = requests.post(f"{node_url}/api/v0/get-txn", 
                               json={
                                   "TxnHashHex": "0000000000000000000000000000000000000000000000000000000000000000"  # dummy hash
                               }, 
                               timeout=5)
        
        # Even if transaction doesn't exist, a 400 "transaction not found" is better than 404 "endpoint not found"
        if response.status_code in [200, 400]:
            print(f"    ✅ Transaction query endpoint accessible")
            return True
        elif response.status_code == 404:
            print(f"    ❌ Transaction query endpoint not found (TxIndex likely disabled)")
            return False
        else:
            print(f"    ⚠️  Unclear transaction query status: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"    ⚠️  Mempool test inconclusive: {e}")
        return None

def main():
    print("🚀 DeSo Node TxIndex Detection Tool")
    print("=" * 50)
    
    working_nodes = []
    txindex_nodes = []
    
    for node in TEST_NODES:
        # Test basic accessibility
        if test_node_accessibility(node):
            working_nodes.append(node)
            
            # Test TxIndex capability
            txindex_result = test_txindex_capability(node)
            mempool_result = test_mempool_info(node)
            
            # Determine TxIndex status
            if txindex_result is True and mempool_result is not False:
                print(f"  🟢 TxIndex Status: ENABLED - Good for monitoring")
                txindex_nodes.append(node)
            elif txindex_result is False or mempool_result is False:
                print(f"  🔴 TxIndex Status: DISABLED - Not suitable for wait_for_commitment")
            else:
                print(f"  🟡 TxIndex Status: UNCLEAR - May need manual testing")
        
        time.sleep(1)  # Be nice to the nodes
    
    print("\n" + "=" * 50)
    print("📊 SUMMARY")
    print("=" * 50)
    print(f"✅ Working nodes: {len(working_nodes)}/{len(TEST_NODES)}")
    print(f"🟢 TxIndex enabled nodes: {len(txindex_nodes)}")
    
    if txindex_nodes:
        print("\n🎯 RECOMMENDED NODES FOR DESOMONITOR:")
        for node in txindex_nodes:
            print(f"  - {node}")
        
        print(f"\n📝 Update your deso_monitor.py NODES list with these {len(txindex_nodes)} nodes")
    else:
        print("\n⚠️  No nodes with confirmed TxIndex found. You may need to:")
        print("   1. Test with smaller timeouts")
        print("   2. Use nodes without wait_for_commitment")
        print("   3. Contact node operators about TxIndex status")

if __name__ == "__main__":
    main()
