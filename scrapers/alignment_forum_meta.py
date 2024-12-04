import os
import json
import re
from bs4 import BeautifulSoup
import requests
from pathlib import Path
from datetime import datetime
import argparse

class MetadataExtractor:
    def __init__(self):
        self.output_file = "metadata/alignment_forum.json"
        self.existing_data = self.load_existing_data()

    def load_existing_data(self):
        """Load existing metadata if the file exists"""
        if os.path.exists(self.output_file):
            with open(self.output_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def parse_date(self, date_str):
        """Convert date string to ISO format"""
        # Match patterns like "22nd Jan 2024" or "1st Nov 2024"
        pattern = r'(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(\d{4})'
        if match := re.search(pattern, date_str):
            day, month, year = match.groups()
            month_num = datetime.strptime(month[:3], '%b').month
            return f"{year}-{month_num:02d}-{int(day):02d}"
        return None

    def extract_metadata(self, url):
        """Extract metadata from a single URL"""
        try:
            response = requests.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract post ID from URL
            post_id = re.search(r'/posts/([^/]+)', url).group(1)

            # Get title
            title = ''
            if title_elem := soup.find(class_='LWPostsPageHeader-title'):
                title = re.sub(r'by\s+[\w\s,]+\d{1,2}(?:st|nd|rd|th)?\s+[A-Z][a-z]+\s+\d{4}.*$', '', 
                             title_elem.get_text().strip())
                title = re.sub(r'by\s+[\w\s,]+$', '', title).strip()

            # Get authors
            authors = []
            if author_elem := soup.find(class_='LWPostsPageHeader-authorInfo'):
                author_text = author_elem.get_text().strip()
                if author_match := re.search(r'by\s+([\w\s,]+)', author_text):
                    # Split on commas and clean up each author name
                    authors = [name.strip() for name in author_match.group(1).split(',')]
            
            # Get date
            published_date = None
            if date_elem := soup.find(class_='LWPostsPageHeader-date'):
                date_text = date_elem.get_text().strip()
                published_date = self.parse_date(date_text)
            
            metadata = {
                "title": title,
                "authors": authors,
                "published_date": published_date,
                "url": url
            }
            
            return post_id, metadata
            
        except Exception as e:
            print(f"Error processing {url}: {str(e)}")
            return None, None

    def process_url(self, url):
        """Process a single URL and update metadata"""
        if "alignmentforum.org" not in url:
            print(f"Error: URL {url} is not from alignmentforum.org")
            return

        print(f"Processing URL: {url}")
        post_id, metadata = self.extract_metadata(url)
        
        if post_id and metadata:
            self.existing_data[post_id] = metadata
            self.save_metadata()

    def process_urls_from_file(self, filepath="source_urls/alignment_forum.txt"):
        """Process URLs from a file"""
        try:
            with open(filepath, 'r') as f:
                urls = [line.strip() for line in f if line.strip()]
            
            for url in urls:
                self.process_url(url)
                
        except FileNotFoundError:
            print(f"File not found: {filepath}")
        except Exception as e:
            print(f"Error reading file: {str(e)}")

    def save_metadata(self):
        """Save metadata to JSON file"""
        # Sort the dictionary by post_id
        sorted_data = dict(sorted(self.existing_data.items()))
        
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(sorted_data, f, indent=2, ensure_ascii=False)

def main():
    parser = argparse.ArgumentParser(description='Extract metadata from Alignment Forum posts')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--url', help='Single URL to process')
    group.add_argument('--file', help='File containing URLs to process', 
                      default='source_urls/alignment_forum.txt')
    
    args = parser.parse_args()
    
    extractor = MetadataExtractor()
    
    if args.url:
        extractor.process_url(args.url)
    else:
        extractor.process_urls_from_file(args.file)

if __name__ == "__main__":
    main()
