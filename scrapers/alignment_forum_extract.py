import os
import json
import re
from bs4 import BeautifulSoup
import requests
from pathlib import Path
from datetime import datetime

class ArticleExtractor:
    def __init__(self):
        self.base_url = "https://www.alignmentforum.org"
    
    def clean_title(self, text):
        """Clean the title by removing author and metadata"""
        # Remove everything after variations of "by" followed by names and dates
        cleaned = re.sub(r'by\s+[\w\s,]+\d{1,2}(?:st|nd|rd|th)?\s+[A-Z][a-z]+\s+\d{4}.*$', '', text)
        # Remove just the "by Author" part if it exists
        cleaned = re.sub(r'by\s+[\w\s,]+$', '', cleaned)
        # Remove any "X min read" and numbers at the end
        cleaned = re.sub(r'\d+\s*min read\d*$', '', cleaned)
        return cleaned.strip()

    def clean_content(self, soup):
        """Extract all content from the page in a structured way"""
        article_data = {
            'title': '',
            'metadata': '',
            'content': []
        }
        
        # Get and clean title
        if title_elem := soup.find(class_='LWPostsPageHeader-title'):
            article_data['title'] = self.clean_title(title_elem.get_text().strip())
        
        # Get metadata (author and date)
        metadata_parts = []
        
        # Get author
        if author_elem := soup.find(class_='LWPostsPageHeader-authorInfo'):
            author_text = author_elem.get_text().strip()
            author_match = re.search(r'by\s+([\w\s,]+)', author_text)
            if author_match:
                metadata_parts.append(f"by {author_match.group(1).strip()}")
        
        # Get date
        if date_elem := soup.find(class_='LWPostsPageHeader-date'):
            date_text = date_elem.get_text().strip()
            # Extract date with year using regex
            date_match = re.search(r'(\d{1,2}(?:st|nd|rd|th)?\s+[A-Z][a-z]+\s+\d{4})', date_text)
            if date_match:
                metadata_parts.append(date_match.group(1))
        
        article_data['metadata'] = ' | '.join(metadata_parts)
        
        # Get main content
        content_area = soup.find(class_='PostsPage-postContent') or \
                      soup.find(class_='ContentStyles-postBody') or \
                      soup.find(class_='PostsPage-centralColumn')
        
        if content_area:
            # Remove unwanted elements
            for unwanted in content_area.find_all(['script', 'style', 'iframe']):
                unwanted.decompose()
            
            for unwanted_class in [
                'CommentsSection', 'PostsVote', 'PostsPageCommentThread',
                'ArticleNavigationLinks', 'PostsPageHeaderTags'
            ]:
                for elem in content_area.find_all(class_=unwanted_class):
                    elem.decompose()
            
            # Extract main content
            last_text = None
            for elem in content_area.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'li']):
                text = elem.get_text().strip()
                
                # Skip empty or unwanted content
                if not text or any(x in text.lower() for x in [
                    'new comment',
                    'mentioned in',
                    'load more',
                    'karma',
                    'vote',
                    'share',
                    'find out when',
                    'read the full post',
                    'this is a linkpost'
                ]):
                    continue
                
                # Avoid duplicate consecutive text
                if text != last_text:
                    # Add bullet points for list items
                    if elem.name == 'li':
                        text = f"• {text}"
                    
                    # Add extra newline before headers
                    if elem.name.startswith('h') and article_data['content']:
                        article_data['content'].append('')
                    
                    article_data['content'].append(text)
                    last_text = text
        
        # Format the final output
        output_parts = []
        
        if article_data['title']:
            output_parts.append(article_data['title'])
        
        if article_data['metadata']:
            output_parts.append(article_data['metadata'])
        
        if article_data['content']:
            output_parts.extend(article_data['content'])
        
        # Join with double newlines and clean up
        full_text = '\n\n'.join(filter(None, output_parts))
        full_text = re.sub(r'\n{3,}', '\n\n', full_text)
        
        return full_text

    def save_content(self, content, url):
        """Save content to a file with a meaningful name"""
        try:
            # Extract post ID or use timestamp
            post_id = re.search(r'/posts/([^/]+)', url)
            filename = f"post_{post_id.group(1)}.txt" if post_id else \
                      f"post_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            
            filepath = Path('extract/alignment_forum') / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return filepath
        except Exception as e:
            print(f"Error saving content: {str(e)}")
            return None

    def process_url(self, url):
        """Process a single URL"""
        if "alignmentforum.org" not in url:
            print(f"Error: URL {url} is not from alignmentforum.org")
            return

        try:
            print(f"Processing URL: {url}")
            response = requests.get(url)
            response.raise_for_status()
            
            print("Got response, parsing content...")
            soup = BeautifulSoup(response.text, 'html.parser')
            content = self.clean_content(soup)
            
            if content.strip():
                filepath = self.save_content(content, url)
                if filepath:
                    print(f"Saved content to {filepath}")
            else:
                print("No content extracted")
                
        except Exception as e:
            print(f"Error processing {url}: {str(e)}")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Extract articles from Alignment Forum')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--url', help='URL to process')
    group.add_argument('--file', help='File containing URLs to process')
    
    args = parser.parse_args()
    
    extractor = ArticleExtractor()
    
    if args.url:
        extractor.process_url(args.url)
    else:
        with open(args.file, 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
            for url in urls:
                extractor.process_url(url)

if __name__ == "__main__":
    main()
