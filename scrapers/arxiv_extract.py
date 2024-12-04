import os
import json
import re
from pathlib import Path
from datetime import datetime
import arxiv
from typing import Optional, Dict, List, Tuple
import logging
import requests
import pdfplumber
from io import BytesIO

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TextCleaner:
    def __init__(self):
        # Common academic paper sections
        self.section_headers = r"^(abstract|introduction|background|methodology|methods|results|discussion|conclusion|references|acknowledgments)"
        self.figure_pattern = r"(Figure|Fig\.|Table)\s+\d+"
        self.citation_pattern = r"\[\d+(?:,\s*\d+)*\]"
        
    def dehyphenate(self, text: str) -> str:
        """Remove hyphenation from wrapped lines"""
        return re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)
    
    def fix_spacing(self, text: str) -> str:
        """Fix various spacing issues"""
        # Remove multiple spaces
        text = re.sub(r' +', ' ', text)
        # Fix spacing after periods
        text = re.sub(r'\.(?=[A-Z])', '. ', text)
        # Remove spaces before punctuation
        text = re.sub(r'\s+([.,;:?\)])', r'\1', text)
        # Add space after punctuation if missing
        text = re.sub(r'([.,;:?!])([A-Z])', r'\1 \2', text)
        return text

    def merge_columns(self, text: str) -> str:
        """Merge text from multiple columns"""
        lines = text.split('\n')
        merged_lines = []
        buffer = ''
        
        for line in lines:
            # If line starts with significant indentation, it might be from another column
            if line.startswith('    '):
                buffer += ' ' + line.strip()
            else:
                if buffer:
                    merged_lines.append(buffer)
                buffer = line.strip()
        
        if buffer:
            merged_lines.append(buffer)
            
        return '\n'.join(merged_lines)

    def format_section(self, section_text: str, level: int = 1) -> str:
        """Format a section with proper spacing and structure"""
        return f"\n{'#' * level} {section_text.strip()}\n"

    def clean_text(self, text: str) -> str:
        """Main cleaning function"""
        # Initial cleaning
        text = text.strip()
        text = self.dehyphenate(text)
        
        # Split into lines for processing
        lines = text.split('\n')
        processed_lines = []
        current_section = ""
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            # Check if this is a section header
            if re.match(self.section_headers, line.lower()):
                if current_section:
                    processed_lines.append('')  # Add spacing between sections
                current_section = line
                processed_lines.append(self.format_section(line))
                continue
                
            # Handle figures and tables
            if re.match(self.figure_pattern, line):
                processed_lines.extend(['', line, ''])
                continue
                
            # Regular text processing
            line = self.fix_spacing(line)
            
            # Merge with previous line if it's a continuation
            if processed_lines and not line[0].isupper() and not line[0].isdigit():
                processed_lines[-1] = processed_lines[-1] + ' ' + line
            else:
                processed_lines.append(line)
        
        # Join lines and do final cleaning
        text = '\n'.join(processed_lines)
        
        # Clean up excessive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text

class ArxivExtractor:
    def __init__(self):
        self.base_url = "https://arxiv.org"
        self.text_cleaner = TextCleaner()
    
    def clean_title(self, text: str) -> str:
        """Clean the title by removing any special characters and extra whitespace"""
        cleaned = re.sub(r'\s+', ' ', text)
        return cleaned.strip()

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

    def format_authors(self, authors: List[arxiv.Result.Author]) -> str:
        """Format author list with proper separators"""
        author_names = [author.name for author in authors]
        if len(author_names) > 5:
            return f"{', '.join(author_names[:5])} et al."
        return ', '.join(author_names)

    def clean_abstract(self, text: str) -> str:
        """Clean abstract text by removing newlines and extra spaces"""
        cleaned = re.sub(r'\s+', ' ', text)
        return cleaned.strip()

    def format_categories(self, categories: List[str]) -> str:
        """Format ArXiv categories into a readable string"""
        return ', '.join(categories)

    def download_pdf(self, pdf_url: str) -> Optional[bytes]:
        """Download PDF content from URL"""
        try:
            response = requests.get(pdf_url)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Error downloading PDF: {str(e)}")
            return None

    def extract_text_from_pdf(self, pdf_content: bytes) -> str:
        """Extract and clean text from PDF"""
        try:
            with pdfplumber.open(BytesIO(pdf_content)) as pdf:
                # Skip potential cover pages and extra metadata pages
                start_page = 0
                text_content = []
                
                # Process each page
                for i, page in enumerate(pdf.pages):
                    # Extract text with better layout preservation
                    text = page.extract_text(
                        x_tolerance=3,  # Adjust tolerance for better column detection
                        y_tolerance=3
                    )
                    
                    if text:
                        # Skip if page appears to be a cover page or references
                        if i == 0 and ('abstract' in text.lower()[:100] or 
                                     'introduction' in text.lower()[:100]):
                            start_page = i
                            
                        # Clean and format the text
                        cleaned_text = self.text_cleaner.merge_columns(text)
                        text_content.append(cleaned_text)
                
                # Join all pages and do final cleaning
                full_text = '\n'.join(text_content)
                return self.text_cleaner.clean_text(full_text)
                
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            return ""

    def get_paper_content(self, paper: arxiv.Result, full_text: Optional[str] = None) -> str:
        """Format paper metadata and content into a structured text"""
        sections = []
        
        # Title
        sections.append(f"# {self.clean_title(paper.title)}\n")
        
        # Authors and metadata section
        metadata = []
        metadata.append(f"Authors: {self.format_authors(paper.authors)}")
        metadata.append(f"Published: {paper.published.strftime('%d %B %Y')}")
        if paper.updated:
            metadata.append(f"Last Updated: {paper.updated.strftime('%d %B %Y')}")
        if paper.doi:
            metadata.append(f"DOI: {paper.doi}")
        if paper.journal_ref:
            metadata.append(f"Journal Reference: {paper.journal_ref}")
        
        sections.append('\n'.join(metadata))
        
        # Categories
        if paper.categories:
            sections.append(f"Categories: {self.format_categories(paper.categories)}")
        
        # Abstract
        sections.append("\n## Abstract\n")
        sections.append(self.clean_abstract(paper.summary))
        
        # Full text
        if full_text:
            sections.append("\n## Full Text\n")
            sections.append(full_text)

        return '\n\n'.join(sections)

    def save_content(self, content: str, arxiv_id: str) -> Optional[Path]:
        """Save content to a file with the ArXiv ID as name"""
        try:
            filename = f"arxiv_{arxiv_id.replace('.', '_')}.txt"
            filepath = Path('extracted_papers') / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return filepath
        except Exception as e:
            logger.error(f"Error saving content: {str(e)}")
            return None

    def process_url(self, url: str, include_full_text: bool = True) -> Optional[Dict]:
        """Process a single ArXiv URL and extract paper information"""
        if "arxiv.org" not in url and "arxiv:" not in url:
            logger.error(f"Error: URL {url} is not from arxiv.org")
            return None

        try:
            logger.info(f"Processing URL: {url}")
            arxiv_id = self.extract_id(url)
            
            if not arxiv_id:
                logger.error(f"Could not extract ArXiv ID from {url}")
                return None
            
            # Fetch paper metadata using arxiv API
            search = arxiv.Search(id_list=[arxiv_id])
            paper = next(search.results())
            
            logger.info(f"Found paper: {paper.title}")
            
            # Download and extract full text if requested
            full_text = None
            if include_full_text:
                logger.info("Downloading PDF...")
                pdf_content = self.download_pdf(paper.pdf_url)
                if pdf_content:
                    logger.info("Extracting text from PDF...")
                    full_text = self.extract_text_from_pdf(pdf_content)
                    if full_text:
                        full_text = self.text_cleaner.clean_text(full_text)
            
            content = self.get_paper_content(paper, full_text)
            
            if content.strip():
                filepath = self.save_content(content, arxiv_id)
                if filepath:
                    logger.info(f"Saved content to {filepath}")
                    return {
                        "arxiv_id": arxiv_id,
                        "title": paper.title,
                        "authors": [author.name for author in paper.authors],
                        "published": paper.published.isoformat(),
                        "abstract": paper.summary,
                        "categories": paper.categories,
                        "pdf_url": paper.pdf_url,
                        "filepath": str(filepath),
                        "has_full_text": bool(full_text)
                    }
            else:
                logger.warning("No content extracted")
                
        except Exception as e:
            logger.error(f"Error processing {url}: {str(e)}")
        
        return None

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Extract papers from ArXiv')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--url', help='URL to process')
    group.add_argument('--file', help='File containing URLs to process')
    group.add_argument('--id', help='ArXiv ID to process')
    parser.add_argument('--no-full-text', action='store_true', 
                       help='Skip downloading and extracting full text')
    
    args = parser.parse_args()
    
    extractor = ArxivExtractor()
    
    if args.url:
        extractor.process_url(args.url, not args.no_full_text)
    elif args.id:
        url = f"https://arxiv.org/abs/{args.id}"
        extractor.process_url(url, not args.no_full_text)
    else:
        with open(args.file, 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
            results = []
            for url in urls:
                if result := extractor.process_url(url, not args.no_full_text):
                    results.append(result)
            
            # Save batch results
            if results:
                with open('batch_results.json', 'w') as f:
                    json.dump(results, f, indent=2)

if __name__ == "__main__":
    main()
