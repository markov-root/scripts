import re
from pathlib import Path
from datetime import datetime
import arxiv
from typing import Optional, Dict, List
import logging
import json
from dataclasses import dataclass, asdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ArxivPaper:
    """Minimal data class for paper information"""
    arxiv_id: str
    title: str
    authors: List[str]
    abstract: str
    published_date: str
    updated_date: Optional[str]
    arxiv_url: str

class ArxivExtractor:
    def __init__(self):
        self.output_dir = Path('metadata')
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.output_file = self.output_dir / 'arxiv.json'
        self.client = arxiv.Client()
    
    def extract_id(self, url: str) -> Optional[str]:
        """Extract ArXiv ID from URL or text"""
        patterns = [
            r'arxiv.org/abs/(\d+\.\d+)',
            r'arxiv.org/pdf/(\d+\.\d+)',
            r'arxiv:(\d+\.\d+)'
        ]
        
        for pattern in patterns:
            if match := re.search(pattern, url):
                return match.group(1)
        return None

    def format_date(self, date: datetime) -> str:
        """Format datetime to YYYY-MM-DD"""
        return date.strftime('%Y-%m-%d') if date else None

    def create_paper_object(self, paper: arxiv.Result, arxiv_id: str) -> ArxivPaper:
        """Create a minimal paper object"""
        return ArxivPaper(
            arxiv_id=arxiv_id,
            title=paper.title,
            authors=[author.name for author in paper.authors],
            abstract=paper.summary,
            published_date=self.format_date(paper.published),
            updated_date=self.format_date(paper.updated),
            arxiv_url=f"https://arxiv.org/abs/{arxiv_id}"
        )

    def save_json(self, paper_obj: ArxivPaper) -> None:
        """Save or update paper data in the JSON file"""
        data = {}
        
        # Load existing data if file exists
        if self.output_file.exists():
            with open(self.output_file, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    # If file is corrupted, start fresh
                    data = {}
        
        # Update or add new paper data
        data[paper_obj.arxiv_id] = asdict(paper_obj)
        
        # Save updated data
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def process_url(self, url: str) -> Optional[ArxivPaper]:
        """Process a single ArXiv URL"""
        if "arxiv.org" not in url and "arxiv:" not in url:
            logger.error(f"Error: URL {url} is not from arxiv.org")
            return None

        try:
            logger.info(f"Processing URL: {url}")
            arxiv_id = self.extract_id(url)
            
            if not arxiv_id:
                logger.error(f"Could not extract ArXiv ID from {url}")
                return None
            
            search = arxiv.Search(id_list=[arxiv_id])
            paper = next(self.client.results(search))
            
            logger.info(f"Found paper: {paper.title}")
            
            paper_obj = self.create_paper_object(paper, arxiv_id)
            self.save_json(paper_obj)
            
            logger.info(f"Updated metadata/arxiv.json with paper data")
            return paper_obj
                
        except Exception as e:
            logger.error(f"Error processing {url}: {str(e)}")
            raise

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Extract papers from ArXiv')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--url', help='URL to process')
    group.add_argument('--file', help='File containing URLs to process')
    group.add_argument('--id', help='ArXiv ID to process')
    
    args = parser.parse_args()
    
    extractor = ArxivExtractor()
    
    try:
        if args.url:
            extractor.process_url(args.url)
        elif args.id:
            url = f"https://arxiv.org/abs/{args.id}"
            extractor.process_url(url)
        else:
            with open(args.file, 'r') as f:
                for url in f:
                    if url := url.strip():
                        extractor.process_url(url)
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()
