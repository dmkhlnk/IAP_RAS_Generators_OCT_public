#!/usr/bin/env python3
"""
Simple test script for the API server.

This script tests the Virtual Scanner API endpoint.
"""

import requests
import sys
import argparse
from pathlib import Path

API_BASE_URL = "http://localhost:8000"

def test_health():
    """Test health check endpoint"""
    print("Testing health endpoint...")
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        if response.status_code == 200:
            print("✓ Health check passed")
            print(f"  Response: {response.json()}")
            return True
        else:
            print(f"✗ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Health check failed: {e}")
        return False

def test_scanner_process(dat_file_path):
    """Test scanner process endpoint"""
    print(f"\nTesting scanner process endpoint with {dat_file_path}...")
    
    if not Path(dat_file_path).exists():
        print(f"✗ File not found: {dat_file_path}")
        return False
    
    try:
        with open(dat_file_path, 'rb') as f:
            files = {'file': (Path(dat_file_path).name, f, 'application/octet-stream')}
            response = requests.post(f"{API_BASE_URL}/api/v1/scanner/process", files=files)
        
        if response.status_code == 200:
            result = response.json()
            print("✓ Scanner process successful")
            print(f"  Session ID: {result.get('session_id')}")
            print(f"  Images: {result.get('images')}")
            
            # Try to download the grayscale image
            if 'grayscale' in result.get('images', {}):
                download_url = f"{API_BASE_URL}{result['images']['grayscale']}"
                print(f"\n  Downloading grayscale image from: {download_url}")
                img_response = requests.get(download_url)
                if img_response.status_code == 200:
                    output_file = "test_output_grayscale.png"
                    with open(output_file, 'wb') as f:
                        f.write(img_response.content)
                    print(f"  ✓ Image saved to: {output_file}")
                else:
                    print(f"  ✗ Failed to download image: {img_response.status_code}")
            
            return True
        else:
            print(f"✗ Scanner process failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return False
    except Exception as e:
        print(f"✗ Scanner process failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function"""
    global API_BASE_URL
    
    parser = argparse.ArgumentParser(description="Test OCT Generators API Server")
    parser.add_argument("dat_file", nargs="?", help="Path to scatterers .dat file")
    parser.add_argument("--server", default="http://localhost:8000", 
                       help="API server URL (default: http://localhost:8000)")
    args = parser.parse_args()
    
    API_BASE_URL = args.server.rstrip('/')
    
    print("=" * 60)
    print("OCT Generators API Test")
    print("=" * 60)
    print(f"Server URL: {API_BASE_URL}")
    print("=" * 60)
    
    # Test health
    if not test_health():
        print("\n✗ Health check failed. Is the server running?")
        print(f"  Start server with: python3 api_server.py")
        print(f"  Or check if server is accessible at: {API_BASE_URL}")
        sys.exit(1)
    
    # Test scanner if dat file provided
    if args.dat_file:
        test_scanner_process(args.dat_file)
    else:
        print("\n⚠ No .dat file provided for scanner test")
        print("  Usage: python3 test_api.py <path_to_scatterers.dat> [--server URL]")
        print("  Example: python3 test_api.py test_scatterers.dat")
        print(f"  Example (remote): python3 test_api.py test_scatterers.dat --server http://192.168.1.100:8000")

if __name__ == "__main__":
    main()

