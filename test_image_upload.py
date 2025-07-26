#!/usr/bin/env python3
"""
Test image upload with the JWT-enabled DeSo SDK
"""

import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deso-sdk-fork'))

from deso_sdk import DeSoDexClient

def test_image_upload():
    """Test image upload with both sample images"""
    
    # Load environment variables
    load_dotenv()
    SEED_HEX = os.getenv("DESO_SEED_HEX").replace('"','').replace("'","").strip()
    PUBLIC_KEY = os.getenv("DESO_PUBLIC_KEY").replace('"','').replace("'","").strip()
    
    # Initialize DeSo SDK
    deso = DeSoDexClient(is_testnet=False, seed_phrase_or_hex=SEED_HEX, node_url="https://node.deso.org")
    
    # Test both sample images
    test_images = [
        'sample_daily_performance.png',
        'sample_daily_gauge.png'
    ]
    
    for image_file in test_images:
        if os.path.exists(image_file):
            print(f"\nTesting upload of {image_file}...")
            try:
                image_url = deso.upload_image(image_file, PUBLIC_KEY)
                print(f"✅ SUCCESS: {image_file} uploaded successfully!")
                print(f"   Image URL: {image_url}")
                
                # Verify the URL is valid
                if image_url and image_url.startswith('http'):
                    print(f"   ✅ Valid URL format")
                else:
                    print(f"   ❌ Invalid URL format: {image_url}")
                    
            except Exception as e:
                print(f"❌ FAILED: {image_file} upload failed: {e}")
        else:
            print(f"⚠️  SKIPPED: {image_file} not found")

if __name__ == "__main__":
    print("Testing DeSo image upload with corrected field name...")
    test_image_upload()
    print("\nTest complete!")
