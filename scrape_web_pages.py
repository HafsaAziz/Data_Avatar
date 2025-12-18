import os
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from typing import List, Dict, Optional
import time

# Try to load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Try to import Selenium for JavaScript-rendered pages
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        HAS_WEBDRIVER_MANAGER = True
    except ImportError:
        HAS_WEBDRIVER_MANAGER = False
    HAS_SELENIUM = True
except ImportError:
    HAS_SELENIUM = False
    HAS_WEBDRIVER_MANAGER = False
    print("⚠️  Selenium not installed. JavaScript-rendered pages may not work properly.")
    print("   Install with: pip install selenium webdriver-manager")


class WebPageScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }
        self.scraped_results: List[Dict] = []
        self.driver = None
        
        # Initialize Selenium if available
        if HAS_SELENIUM:
            try:
                chrome_options = Options()
                chrome_options.add_argument('--headless')  # Run in background
                chrome_options.add_argument('--no-sandbox')
                chrome_options.add_argument('--disable-dev-shm-usage')
                chrome_options.add_argument('--disable-gpu')
                chrome_options.add_argument('--window-size=1920,1080')
                chrome_options.add_argument(f'user-agent={self.headers["User-Agent"]}')
                
                # Use webdriver-manager if available, otherwise try direct Chrome
                if HAS_WEBDRIVER_MANAGER:
                    from selenium.webdriver.chrome.service import Service
                    service = Service(ChromeDriverManager().install())
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                else:
                    self.driver = webdriver.Chrome(options=chrome_options)
                print("  ✓ Selenium initialized for JavaScript-rendered pages")
            except Exception as e:
                print(f"  ⚠ Could not initialize Selenium: {e}")
                print("  Will use requests only (may miss JavaScript content)")
                self.driver = None
    
    def __del__(self):
        """Clean up Selenium driver"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
    
    def get_page_content(self, url: str) -> Optional[str]:
        """Get page content, trying Selenium if JavaScript is needed"""
        # First try with requests
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Check if page requires JavaScript
            page_text = soup.get_text().lower()
            js_indicators = ['javascript is disabled', 'please enable javascript', 'javascript required', 
                           'noscript', 'enable javascript to view']
            
            if any(indicator in page_text for indicator in js_indicators):
                print("  ⚠ Page requires JavaScript, trying Selenium...")
                if self.driver:
                    return self.get_page_with_selenium(url)
                else:
                    print("  ⚠ Selenium not available, cannot render JavaScript content")
                    return response.content
            else:
                return response.content
        except Exception as e:
            print(f"  ⚠ Requests failed: {e}")
            if self.driver:
                print("  Trying Selenium...")
                return self.get_page_with_selenium(url)
            raise
    
    def get_page_with_selenium(self, url: str) -> Optional[str]:
        """Get page content using Selenium for JavaScript rendering"""
        if not self.driver:
            return None
        
        try:
            print("  Loading page with Selenium...")
            self.driver.get(url)
            
            # Wait for page to load (wait for body or main content)
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            except:
                pass
            
            # Wait a bit more for dynamic content
            time.sleep(2)
            
            # Get page source
            page_source = self.driver.page_source
            return page_source.encode('utf-8')
        except Exception as e:
            print(f"  ✗ Selenium error: {e}")
            return None
    
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
    
    def extract_webpage_markdown(self, soup: BeautifulSoup, url: str) -> str:
        """Extract comprehensive content from webpage and convert to markdown"""
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
                    if len(rows) > 1:
                        header_sep = '| ' + ' | '.join(['---'] * len(rows[0].split('|')[1:-1])) + ' |'
                        markdown_parts.append('\n'.join([rows[0], header_sep] + rows[1:]) + '\n\n')
                    else:
                        markdown_parts.append('\n'.join(rows) + '\n\n')
        
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
    
    def scrape_webpage(self, url: str) -> Dict:
        """Scrape a single webpage"""
        result = {
            'url': url,
            'status': 'error',
            'webpage_content': None,
            'title': None
        }
        
        try:
            print(f"\n{'='*70}")
            print(f"Processing: {url}")
            print(f"{'='*70}")
            
            # Scrape webpage
            print("  Scraping webpage...")
            page_content = self.get_page_content(url)
            
            if not page_content:
                raise Exception("Could not fetch page content")
            
            soup = BeautifulSoup(page_content, 'html.parser')
            
            # Extract comprehensive webpage content
            webpage_markdown = self.extract_webpage_markdown(soup, url)
            
            title = soup.find('title')
            title_text = title.get_text().strip() if title else 'Untitled'
            
            result['webpage_content'] = webpage_markdown
            result['title'] = title_text
            result['status'] = 'success'
            
            print(f"  ✓ Scraped webpage content ({len(webpage_markdown)} chars)")
            
        except requests.exceptions.RequestException as e:
            print(f"  ✗ Error fetching webpage: {e}")
            result['error'] = str(e)
        except Exception as e:
            print(f"  ✗ Error processing webpage: {e}")
            result['error'] = str(e)
        
        return result
    
    def process_urls(self, urls: List[str]) -> List[Dict]:
        """Process a list of URLs"""
        print(f"\n{'='*70}")
        print(f"Processing {len(urls)} URL(s)")
        print(f"{'='*70}\n")
        
        for i, url in enumerate(urls, 1):
            print(f"\n[{i}/{len(urls)}]")
            try:
                result = self.scrape_webpage(url)
                self.scraped_results.append(result)
                
                # Save progress after each URL
                if result['status'] == 'success':
                    self.save_results()
                    print(f"  ✓ Progress saved")
                
                # Rate limiting between URLs
                if i < len(urls):
                    time.sleep(2)
            except KeyboardInterrupt:
                print(f"\n⚠ Process interrupted by user. Saving progress...")
                self.save_results()
                print(f"✓ Progress saved. Processed {i}/{len(urls)} URLs")
                raise
            except Exception as e:
                print(f"  ✗ Error processing URL: {e}")
                result = {
                    'url': url,
                    'status': 'error',
                    'error': str(e)
                }
                self.scraped_results.append(result)
        
        return self.scraped_results
    
    def save_results(self, output_dir: str = 'markdown_output'):
        """Save all results to markdown files"""
        os.makedirs(output_dir, exist_ok=True)
        
        for i, result in enumerate(self.scraped_results):
            if result['status'] != 'success':
                continue
            
            # Create filename from URL
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
                f.write(result['webpage_content'])
            
            print(f"  ✓ Saved: {filename}")


# Main execution
if __name__ == "__main__":
    # Single URL to scrape
    url_to_scrape = "https://u.ae/en/about-the-uae/strategies-initiatives-and-awards/strategies-plans-and-visions/innovation-and-future-shaping/we-the-uae-2031-vision"
    
    # Or load from file if it exists
    urls_file = 'urls_to_scrape.txt'
    urls_to_scrape = []
    
    if os.path.exists(urls_file):
        print(f"Loading URLs from {urls_file}...")
        with open(urls_file, 'r', encoding='utf-8') as f:
            urls_to_scrape = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    # If no file, use single URL
    if not urls_to_scrape:
        urls_to_scrape = [url_to_scrape]
    
    print(f"\n{'='*70}")
    print("Web Page Scraper")
    print(f"{'='*70}")
    print(f"Total URLs to process: {len(urls_to_scrape)}")
    
    # Create scraper
    scraper = WebPageScraper()
    
    # Process URLs
    results = scraper.process_urls(urls_to_scrape)
    
    # Final save
    print(f"\n{'='*70}")
    print("Saving results")
    print(f"{'='*70}")
    scraper.save_results()
    
    # Save JSON summary
    json_file = 'web_scraped_data.json'
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n✓ Saved JSON summary to: {json_file}")
    
    # Summary
    successful = len([r for r in results if r['status'] == 'success'])
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"✓ Processed {successful}/{len(results)} pages successfully")
    print(f"✓ Results saved to: markdown_output/")

