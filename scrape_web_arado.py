import os
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse
from typing import List, Dict, Set, Optional
import time
import re

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class WebScraper:
    def __init__(self, base_url: str, max_pages: int = 50, same_domain_only: bool = True):
        """
        Initialize web scraper
        
        Args:
            base_url: Starting URL to scrape
            max_pages: Maximum number of pages to scrape
            same_domain_only: Only scrape pages from the same domain
        """
        self.base_url = base_url
        self.base_domain = urlparse(base_url).netloc
        self.max_pages = max_pages
        self.same_domain_only = same_domain_only
        self.visited_urls: Set[str] = set()
        self.scraped_content: List[Dict] = []
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',  # Support Arabic
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
        }
    
    def normalize_url(self, url: str) -> str:
        """Normalize URL by removing fragments and sorting query parameters"""
        parsed = urlparse(url)
        # Remove fragment
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            ''  # Remove fragment
        ))
        return normalized.rstrip('/')
    
    def is_same_domain(self, url: str) -> bool:
        """Check if URL belongs to the same domain"""
        parsed = urlparse(url)
        return parsed.netloc == self.base_domain or parsed.netloc.endswith('.' + self.base_domain)
    
    def should_scrape(self, url: str) -> bool:
        """Determine if URL should be scraped"""
        # Normalize URL
        normalized = self.normalize_url(url)
        
        # Skip if already visited
        if normalized in self.visited_urls:
            return False
        
        # Skip if max pages reached
        if len(self.visited_urls) >= self.max_pages:
            return False
        
        # Check domain restriction
        if self.same_domain_only and not self.is_same_domain(normalized):
            return False
        
        # Skip non-HTML content
        parsed = urlparse(normalized)
        path = parsed.path.lower()
        skip_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', 
                          '.zip', '.rar', '.jpg', '.jpeg', '.png', '.gif', '.svg',
                          '.css', '.js', '.json', '.xml']
        if any(path.endswith(ext) for ext in skip_extensions):
            return False
        
        return True
    
    def extract_text_content(self, soup: BeautifulSoup) -> str:
        """Extract clean text content from BeautifulSoup object"""
        # Remove script and style elements
        for script in soup(["script", "style", "meta", "link", "noscript"]):
            script.decompose()
        
        # Get text
        text = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return text
    
    def extract_markdown(self, soup: BeautifulSoup, url: str) -> str:
        """Extract content and convert to markdown format"""
        markdown_parts = []
        
        # Extract title
        title = soup.find('title')
        if title:
            markdown_parts.append(f"# {title.get_text().strip()}\n")
        
        # Extract meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            markdown_parts.append(f"**Description:** {meta_desc.get('content')}\n")
        
        markdown_parts.append(f"**Source URL:** {url}\n")
        markdown_parts.append("---\n\n")
        
        # Extract main content
        # Try to find main content area
        main_content = None
        content_selectors = [
            'main',
            'article',
            '[role="main"]',
            '.main-content',
            '.content',
            '#content',
            '#main',
            'body'
        ]
        
        for selector in content_selectors:
            main_content = soup.select_one(selector)
            if main_content:
                break
        
        if not main_content:
            main_content = soup.find('body')
        
        if main_content:
            # Process headings
            for heading in main_content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                level = int(heading.name[1])
                text = heading.get_text().strip()
                if text:
                    markdown_parts.append(f"{'#' * level} {text}\n\n")
            
            # Process paragraphs
            for para in main_content.find_all('p'):
                text = para.get_text().strip()
                if text and len(text) > 10:  # Skip very short paragraphs
                    markdown_parts.append(f"{text}\n\n")
            
            # Process lists
            for ul in main_content.find_all(['ul', 'ol']):
                list_items = []
                for li in ul.find_all('li', recursive=False):
                    item_text = li.get_text().strip()
                    if item_text:
                        list_items.append(f"- {item_text}")
                
                if list_items:
                    markdown_parts.append('\n'.join(list_items) + '\n\n')
            
            # Process tables
            for table in main_content.find_all('table'):
                rows = []
                for tr in table.find_all('tr'):
                    cells = []
                    for td in tr.find_all(['td', 'th']):
                        cell_text = td.get_text().strip()
                        cells.append(cell_text)
                    if cells:
                        rows.append('| ' + ' | '.join(cells) + ' |')
                
                if rows:
                    # Add header separator for first row if it's a header
                    if len(rows) > 1:
                        header_sep = '| ' + ' | '.join(['---'] * len(rows[0].split('|')[1:-1])) + ' |'
                        markdown_parts.append('\n'.join([rows[0], header_sep] + rows[1:]) + '\n\n')
                    else:
                        markdown_parts.append('\n'.join(rows) + '\n\n')
            
            # Process links (limit to avoid clutter)
            links_section = []
            for link in main_content.find_all('a', href=True):
                link_text = link.get_text().strip()
                link_url = link.get('href')
                if link_text and link_url and len(link_text) > 3:
                    absolute_url = urljoin(url, link_url)
                    links_section.append(f"- [{link_text}]({absolute_url})")
            
            if links_section:
                markdown_parts.append("## Links\n\n")
                markdown_parts.append('\n'.join(links_section[:50]) + '\n\n')  # Limit to 50 links
        
        # If markdown is too short, fall back to plain text extraction
        markdown_text = ''.join(markdown_parts)
        if len(markdown_text.strip()) < 500:
            plain_text = self.extract_text_content(soup)
            if len(plain_text) > len(markdown_text):
                markdown_parts = [f"# {soup.find('title').get_text().strip() if soup.find('title') else 'Webpage'}\n\n"]
                markdown_parts.append(f"**Source URL:** {url}\n\n---\n\n")
                markdown_parts.append(plain_text)
                markdown_text = '\n'.join(markdown_parts)
        
        return markdown_text
    
    def scrape_page(self, url: str, max_retries: int = 3) -> Optional[Dict]:
        """Scrape a single page with retry logic"""
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    wait_time = attempt * 2  # Exponential backoff: 2s, 4s
                    print(f"  Retrying (attempt {attempt + 1}/{max_retries}) after {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"  Scraping: {url}")
                
                # Try with longer timeout and different connection settings
                response = requests.get(
                    url, 
                    headers=self.headers, 
                    timeout=(10, 30),  # (connect timeout, read timeout)
                    allow_redirects=True,
                    verify=True
                )
                response.raise_for_status()
                
                # Parse HTML
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract markdown content
                markdown_content = self.extract_markdown(soup, url)
                
                # Extract plain text for reference
                plain_text = self.extract_text_content(soup)
                
                # Find all links on the page
                links = []
                for link in soup.find_all('a', href=True):
                    href = link.get('href')
                    if href:
                        absolute_url = urljoin(url, href)
                        links.append(absolute_url)
                
                result = {
                    'url': url,
                    'title': soup.find('title').get_text().strip() if soup.find('title') else '',
                    'markdown': markdown_content,
                    'plain_text': plain_text[:1000],  # Store first 1000 chars of plain text
                    'links_found': len(links),
                    'status': 'success'
                }
                
                self.visited_urls.add(self.normalize_url(url))
                return result
                
            except requests.exceptions.Timeout as e:
                if attempt < max_retries - 1:
                    continue  # Retry on timeout
                print(f"  ✗ Connection timeout after {max_retries} attempts: {e}")
                return {
                    'url': url,
                    'status': 'error',
                    'error': f'Connection timeout: {str(e)}'
                }
            except requests.exceptions.ConnectionError as e:
                if attempt < max_retries - 1:
                    continue  # Retry on connection error
                print(f"  ✗ Connection error after {max_retries} attempts: {e}")
                return {
                    'url': url,
                    'status': 'error',
                    'error': f'Connection error: {str(e)}'
                }
            except requests.exceptions.RequestException as e:
                print(f"  ✗ Error fetching {url}: {e}")
                return {
                    'url': url,
                    'status': 'error',
                    'error': str(e)
                }
            except Exception as e:
                print(f"  ✗ Error processing {url}: {e}")
                return {
                    'url': url,
                    'status': 'error',
                    'error': str(e)
                }
        
        # If all retries failed
        return {
            'url': url,
            'status': 'error',
            'error': f'Failed after {max_retries} attempts'
        }
    
    def scrape_all(self) -> List[Dict]:
        """Scrape the website starting from base_url"""
        print(f"\n{'=' * 70}")
        print(f"Starting web scraping: {self.base_url}")
        print(f"Max pages: {self.max_pages}, Same domain only: {self.same_domain_only}")
        print(f"{'=' * 70}\n")
        
        # Start with base URL
        urls_to_visit = [self.base_url]
        
        while urls_to_visit and len(self.visited_urls) < self.max_pages:
            current_url = urls_to_visit.pop(0)
            
            if not self.should_scrape(current_url):
                continue
            
            # Scrape the page
            result = self.scrape_page(current_url)
            
            if result and result['status'] == 'success':
                self.scraped_content.append(result)
                
                # Extract links from the page to visit next
                if 'links_found' in result:
                    # Re-scrape the page to get links (we already have soup)
                    try:
                        response = requests.get(current_url, headers=self.headers, timeout=30)
                        soup = BeautifulSoup(response.content, 'html.parser')
                        
                        for link in soup.find_all('a', href=True):
                            href = link.get('href')
                            if href:
                                absolute_url = urljoin(current_url, href)
                                normalized = self.normalize_url(absolute_url)
                                
                                if self.should_scrape(normalized):
                                    if normalized not in urls_to_visit:
                                        urls_to_visit.append(normalized)
                    except:
                        pass
                
                print(f"  ✓ Scraped successfully ({len(result['markdown'])} chars)")
            else:
                print(f"  ✗ Failed to scrape")
            
            # Rate limiting
            time.sleep(1)
            
            # Progress update
            if len(self.visited_urls) % 5 == 0:
                print(f"\n  Progress: {len(self.visited_urls)}/{self.max_pages} pages scraped\n")
        
        print(f"\n{'=' * 70}")
        print(f"Scraping complete! Scraped {len(self.scraped_content)} pages")
        print(f"{'=' * 70}\n")
        
        return self.scraped_content

def save_results(results: List[Dict], output_dir: str = 'markdown_output', single_file: bool = True):
    """Save scraped results to markdown file(s)"""
    os.makedirs(output_dir, exist_ok=True)
    
    successful_results = [r for r in results if r['status'] == 'success']
    
    if single_file:
        # Combine all pages into one markdown file
        base_domain = urlparse(results[0]['url']).netloc if results else 'website'
        safe_domain = ''.join(c if c.isalnum() or c in ('-', '_', '.') else '_' for c in base_domain)
        filename = f"web_{safe_domain}.md"
        filepath = os.path.join(output_dir, filename)
        
        combined_markdown = []
        combined_markdown.append(f"# Website Content: {base_domain}\n\n")
        combined_markdown.append(f"**Base URL:** {results[0]['url'] if results else 'N/A'}\n\n")
        combined_markdown.append(f"**Total Pages Scraped:** {len(successful_results)}\n\n")
        combined_markdown.append("---\n\n")
        
        for i, result in enumerate(successful_results, 1):
            combined_markdown.append(f"\n\n{'=' * 70}\n")
            combined_markdown.append(f"## Page {i}: {result.get('title', 'Untitled')}\n\n")
            combined_markdown.append(f"**URL:** {result['url']}\n\n")
            combined_markdown.append("---\n\n")
            combined_markdown.append(result['markdown'])
            combined_markdown.append("\n\n")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(''.join(combined_markdown))
        
        print(f"  ✓ Saved all content to: {filename} ({len(''.join(combined_markdown))} chars)")
    else:
        # Save each page as separate file (original behavior)
        for i, result in enumerate(successful_results):
            url_path = urlparse(result['url']).path
            if not url_path or url_path == '/':
                url_path = urlparse(result['url']).netloc
            
            filename = url_path.replace('/', '_').replace('\\', '_')
            filename = ''.join(c if c.isalnum() or c in ('-', '_', '.') else '_' for c in filename)
            filename = filename[:100]
            
            if not filename:
                filename = f"page_{i+1}"
            
            filename = f"web_{filename}.md"
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(result['markdown'])
            
            print(f"  ✓ Saved: {filename}")

# Main execution
if __name__ == "__main__":
    # Configuration
    BASE_URL = "https://www.arado.org/"
    MAX_PAGES = 50  # Maximum number of pages to scrape
    SAME_DOMAIN_ONLY = True  # Only scrape pages from the same domain
    
    print("\n" + "=" * 70)
    print("Web Scraper - ARADO (Arab Administrative Development Organization)")
    print("=" * 70)
    
    # Create scraper
    scraper = WebScraper(
        base_url=BASE_URL,
        max_pages=MAX_PAGES,
        same_domain_only=SAME_DOMAIN_ONLY
    )
    
    # Scrape all pages
    results = scraper.scrape_all()
    
    # Save markdown files (combined into one file)
    print("\n" + "=" * 70)
    print("Saving markdown file")
    print("=" * 70)
    save_results(results, single_file=True)
    
    # Save JSON summary
    output_file = 'web_scraped_data_arado.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n✓ Saved results summary to: {output_file}")
    print(f"✓ Total pages scraped: {len([r for r in results if r['status'] == 'success'])}")

