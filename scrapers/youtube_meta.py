#!/usr/bin/env python3
import json
import subprocess
import argparse
from pathlib import Path
from typing import List, Dict, Optional
import sys
from time import sleep

def read_urls_from_file(file_path: str) -> List[str]:
    """Read URLs from a file, one URL per line."""
    try:
        with open(file_path, 'r') as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found")
        sys.exit(1)

def extract_metadata(url: str) -> Optional[Dict]:
    """Extract only essential metadata from a YouTube video"""
    try:
        cmd = ["yt-dlp", "--skip-download", "--print", 
               "{\"id\":%(id)j,\"title\":%(title)j,\"thumbnail\":%(thumbnail)j,\"url\":%(webpage_url)j,\"channel\":%(channel)j}", 
               url]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error extracting metadata from {url}: {e.stderr}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON output for {url}: {e}")
        return None

def save_metadata(metadata: List[Dict], output_file: str):
    """Save metadata to a JSON file."""
    try:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        print(f"Metadata saved to {output_file}")
    except Exception as e:
        print(f"Error saving metadata: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='Extract basic metadata from YouTube videos')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--url', help='Single YouTube video URL')
    group.add_argument('--file', help='File containing YouTube URLs (one per line)')
    parser.add_argument('--output', default='metadata/youtube.json',
                       help='Output JSON file path (default: metadata/youtube.json)')
    parser.add_argument('--delay', type=float, default=1.0, 
                       help='Delay between requests in seconds (default: 1.0)')
    args = parser.parse_args()
    
    all_metadata = []
    
    if args.url:
        metadata = extract_metadata(args.url)
        if metadata:
            all_metadata.append(metadata)
    else:
        urls = read_urls_from_file(args.file)
        total_urls = len(urls)
        
        print(f"Processing {total_urls} URLs...")
        for i, url in enumerate(urls, 1):
            print(f"Processing URL {i}/{total_urls}: {url}")
            metadata = extract_metadata(url)
            if metadata:
                all_metadata.append(metadata)
            if i < total_urls:
                sleep(args.delay)
    
    if all_metadata:
        save_metadata(all_metadata, args.output)
        print(f"Successfully processed {len(all_metadata)} videos")
    else:
        print("No metadata was extracted")

if __name__ == "__main__":
    main()
