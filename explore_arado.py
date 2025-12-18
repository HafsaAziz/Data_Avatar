#!/usr/bin/env python3
"""
Explore ARADO website to find actual page URLs
"""

import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

def explore_arado():
    """Explore ARADO website to find actual URLs"""
    
    # Setup Chrome
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')
    
    print("Initializing browser...")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        # Load homepage
        print("\nLoading homepage: https://www.arado.org/")
        driver.get("https://www.arado.org/")
        
        # Wait for page to load
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Wait for Angular
        time.sleep(5)
        
        # Scroll to trigger content
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(3)
        
        # Get page source
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Find all links
        print("\n" + "="*70)
        print("Finding all links on the page...")
        print("="*70)
        
        links_found = set()
        
        # Find navigation links
        nav_links = soup.find_all('a', href=True)
        for link in nav_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            if href and 'arado.org' in href:
                links_found.add((href, text))
            elif href and href.startswith('/'):
                full_url = f"https://www.arado.org{href}"
                links_found.add((full_url, text))
            elif href and not href.startswith('http') and not href.startswith('#'):
                full_url = f"https://www.arado.org/{href}"
                links_found.add((full_url, text))
        
        # Also check JavaScript/Angular routes
        print("\nChecking for Angular routes...")
        if 'ng-view' in page_source or 'ui-view' in page_source:
            print("  Angular SPA detected")
        
        # Print found links
        print("\n" + "="*70)
        print("Found Links:")
        print("="*70)
        
        for url, text in sorted(links_found):
            if text and len(text) > 2:
                print(f"\n{text[:50]:<50} -> {url}")
        
        # Try to find menu items
        print("\n" + "="*70)
        print("Looking for menu items...")
        print("="*70)
        
        menu_items = soup.find_all(['nav', 'ul', 'li'], class_=lambda x: x and ('menu' in x.lower() or 'nav' in x.lower()))
        for item in menu_items[:20]:
            text = item.get_text(strip=True)
            if text and len(text) > 3:
                print(f"  - {text[:60]}")
        
        # Check for specific content sections
        print("\n" + "="*70)
        print("Checking for content sections...")
        print("="*70)
        
        # Try accessing common paths
        test_paths = [
            '/Content',
            '/About',
            '/Training',
            '/Events',
            '/Publications',
            '/Awards',
            '/News',
            '/Services',
            '/en',
            '/ar'
        ]
        
        for path in test_paths:
            test_url = f"https://www.arado.org{path}"
            print(f"\nTesting: {test_url}")
            try:
                driver.get(test_url)
                time.sleep(3)
                current_url = driver.current_url
                title = driver.title
                print(f"  -> Current URL: {current_url}")
                print(f"  -> Title: {title}")
                
                # Check if page has content
                page_text = driver.find_element(By.TAG_NAME, "body").text
                content_length = len(page_text.strip())
                print(f"  -> Content length: {content_length} chars")
                
                if content_length > 500:
                    print(f"  ✓ Has substantial content!")
                
            except Exception as e:
                print(f"  ✗ Error: {e}")
        
        # Get final page source to check structure
        print("\n" + "="*70)
        print("Page Structure Analysis:")
        print("="*70)
        
        driver.get("https://www.arado.org/")
        time.sleep(5)
        page_source = driver.page_source
        
        # Check for Angular routes in source
        import re
        routes = re.findall(r'#/([^"\'>\s]+)', page_source)
        if routes:
            print("\nFound Angular routes:")
            unique_routes = set(routes)
            for route in sorted(unique_routes):
                print(f"  - /{route}")
        
    finally:
        driver.quit()
        print("\n" + "="*70)
        print("Exploration complete!")
        print("="*70)

if __name__ == '__main__':
    explore_arado()

