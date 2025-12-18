#!/usr/bin/env python3
"""
ARADO Website Scraper
Specialized scraper for https://www.arado.org/ (Angular/SPA site)
"""

import os
import json
import time
import re
from typing import Dict, List, Optional
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from datetime import datetime

# Selenium imports for JavaScript rendering
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
    print("⚠ Warning: Selenium not installed. This script requires Selenium for ARADO.")
    print("Install with: pip install selenium webdriver-manager")


class ARADOScraper:
    """Scraper specifically designed for ARADO website (Angular SPA)"""
    
    def __init__(self):
        self.base_url = "https://www.arado.org/"
        self.driver = None
        self.results = []
        
    def init_selenium(self):
        """Initialize Selenium WebDriver"""
        if not HAS_SELENIUM:
            print("✗ Selenium is required for this scraper")
            return False
        
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            chrome_options.add_argument('--lang=ar,en')  # Support Arabic and English
            
            if HAS_WEBDRIVER_MANAGER:
                print("  Initializing Chrome WebDriver with webdriver-manager...")
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                print("  Initializing Chrome WebDriver...")
                self.driver = webdriver.Chrome(options=chrome_options)
            
            print("  ✓ Selenium initialized successfully")
            return True
        except Exception as e:
            print(f"  ✗ Failed to initialize Selenium: {e}")
            return False
    
    def extract_content_from_dom(self) -> str:
        """Extract content directly from DOM using JavaScript"""
        try:
            # JavaScript to extract all visible text content
            js_code = """
            function extractContent() {
                // Find main content container
                var mainContent = document.querySelector('main') || 
                                 document.querySelector('#content') ||
                                 document.querySelector('.content') ||
                                 document.querySelector('.main-content') ||
                                 document.querySelector('.container') ||
                                 document.querySelector('[class*="Content"]') ||
                                 document.querySelector('[id*="Content"]') ||
                                 document.body;
                
                // Clone to avoid modifying original
                var clone = mainContent.cloneNode(true);
                
                // Remove unwanted elements
                var unwanted = clone.querySelectorAll('script, style, nav, header, .navbar, .menu, .login-form, .footer, .header, [class*="nav"], [class*="menu"], [class*="login"], [id*="login"]');
                unwanted.forEach(el => el.remove());
                
                // Extract structured content
                var sections = [];
                
                // Extract headings and their content
                var headings = clone.querySelectorAll('h1, h2, h3, h4, h5, h6');
                headings.forEach(function(heading) {
                    var text = heading.textContent.trim();
                    if (text.length > 2 && !text.includes('{{')) {
                        var level = parseInt(heading.tagName.charAt(1));
                        var prefix = '#'.repeat(level) + ' ';
                        sections.push(prefix + text);
                        
                        // Get content after heading
                        var next = heading.nextElementSibling;
                        var content = [];
                        var count = 0;
                        while (next && count < 5) {
                            if (next.tagName.match(/^H[1-6]$/)) break;
                            var nextText = next.textContent.trim();
                            if (nextText.length > 20) {
                                content.push(nextText);
                            }
                            next = next.nextElementSibling;
                            count++;
                        }
                        if (content.length > 0) {
                            sections.push(content.join('\\n\\n'));
                        }
                    }
                });
                
                // Extract paragraphs
                var paragraphs = clone.querySelectorAll('p');
                paragraphs.forEach(function(p) {
                    var text = p.textContent.trim();
                    if (text.length > 30 && !text.includes('{{') && !text.includes('تسجيل دخول')) {
                        sections.push(text);
                    }
                });
                
                // Extract list items
                var lists = clone.querySelectorAll('ul li, ol li');
                lists.forEach(function(li) {
                    var text = li.textContent.trim();
                    if (text.length > 20 && !text.includes('{{')) {
                        sections.push('- ' + text);
                    }
                });
                
                // Extract divs with substantial content
                var divs = clone.querySelectorAll('div');
                divs.forEach(function(div) {
                    var text = div.textContent.trim();
                    // Only include if it's substantial and not nested in another div we already got
                    if (text.length > 100 && !text.includes('{{')) {
                        var parent = div.parentElement;
                        var isNested = false;
                        while (parent && parent !== clone) {
                            if (parent.tagName === 'DIV' && parent.textContent.trim().includes(text)) {
                                isNested = true;
                                break;
                            }
                            parent = parent.parentElement;
                        }
                        if (!isNested) {
                            sections.push(text);
                        }
                    }
                });
                
                // Remove duplicates
                var seen = new Set();
                var unique = [];
                sections.forEach(function(section) {
                    var key = section.substring(0, 50);
                    if (!seen.has(key)) {
                        seen.add(key);
                        unique.push(section);
                    }
                });
                
                return unique.join('\\n\\n');
            }
            
            return extractContent();
            """
            
            content = self.driver.execute_script(js_code)
            return content if content else ""
        except Exception as e:
            print(f"  ⚠ DOM extraction error: {e}")
            return ""
    
    def wait_for_content_load(self, timeout=30):
        """Wait for actual content to load"""
        try:
            # Wait for document ready
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script("return document.readyState === 'complete'")
            )
            
            # Wait for jQuery/AJAX to complete
            print("  Waiting for AJAX requests to complete...")
            try:
                WebDriverWait(self.driver, timeout).until(
                    lambda driver: driver.execute_script("return typeof jQuery === 'undefined' || jQuery.active === 0")
                )
            except:
                pass
            
            # Multiple scrolls to trigger lazy loading
            print("  Scrolling to trigger content loading...")
            # Get page height first
            page_height = self.driver.execute_script("return document.body.scrollHeight")
            for i in range(3):
                scroll_position = int((i + 1) * (page_height / 4))
                self.driver.execute_script(f"window.scrollTo(0, {scroll_position});")
                time.sleep(2)
            
            # Scroll to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            
            # Scroll back to top
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)
            
            # Wait for content containers to appear
            print("  Waiting for content elements...")
            content_selectors = [
                ".content",
                "#content",
                "main",
                "article",
                ".main-content",
                ".container",
                "[class*='Content']",
                "[id*='Content']"
            ]
            
            content_found = False
            for selector in content_selectors:
                try:
                    elements = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                    )
                    if elements:
                        for elem in elements[:5]:
                            text = elem.text.strip()
                            # Check for substantial content (not just navigation)
                            if len(text) > 200 and not any(skip in text[:100].lower() for skip in ['تسجيل دخول', 'login', 'cookie']):
                                content_found = True
                                print(f"  ✓ Found content in {selector}")
                                break
                        if content_found:
                            break
                except:
                    continue
            
            # Additional wait for dynamic content
            if not content_found:
                print("  ⚠ Waiting longer for content to load...")
                time.sleep(8)
            
            # Final wait
            time.sleep(3)
            
            return True
        except Exception as e:
            print(f"  ⚠ Content load wait issue: {e}")
            time.sleep(8)
            return True
    
    def scrape_page(self, url: str, page_name: str) -> Dict:
        """Scrape a single page from ARADO"""
        result = {
            'url': url,
            'page_name': page_name,
            'title': '',
            'markdown_content': '',
            'status': 'pending',
            'error': None,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            print(f"\n  Scraping: {url}")
            print("  Loading page with Selenium...")
            
            self.driver.get(url)
            
            # Wait for page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Wait for actual content to load
            print("  Waiting for content to load...")
            self.wait_for_content_load()
            
            # Try to extract content directly from DOM using JavaScript
            print("  Extracting content from rendered DOM...")
            dom_content = self.extract_content_from_dom()
            
            # Get page source for parsing
            print("  Getting rendered page source...")
            page_source = self.driver.page_source
            
            # Debug: Check if we have actual content
            if '{{' in page_source and '}}' in page_source:
                print("  ⚠ Warning: Template variables still present, waiting longer...")
                time.sleep(5)
                page_source = self.driver.page_source
            
            # Additional wait and scroll to ensure content is loaded
            print("  Performing final content check...")
            time.sleep(3)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)
            page_source = self.driver.page_source  # Get fresh page source
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # If DOM extraction got good content, store it for use in extract_content
            if dom_content and len(dom_content) > 500:
                print(f"  ✓ Extracted {len(dom_content)} chars from DOM")
                # Store in a custom attribute for later use
                soup._dom_text_content = dom_content
            
            # Extract title
            title_tag = soup.find('title')
            if title_tag:
                result['title'] = title_tag.get_text().strip()
            else:
                result['title'] = page_name
            
            print(f"  Title: {result['title']}")
            
            # Extract content
            print("  Extracting content...")
            # Pass DOM content if available
            dom_text = getattr(soup, 'dom_text_content', None)
            markdown_content = self.extract_content(soup, url, dom_text=dom_text)
            
            result['markdown_content'] = markdown_content
            result['status'] = 'success'
            
            print(f"  ✓ Extracted {len(markdown_content)} characters")
            
        except Exception as e:
            error_msg = str(e)
            print(f"  ✗ Error: {error_msg}")
            result['status'] = 'error'
            result['error'] = error_msg
        
        return result
    
    def extract_content(self, soup: BeautifulSoup, url: str, dom_text: Optional[str] = None) -> str:
        """Extract content from ARADO page and convert to markdown"""
        markdown_parts = []
        
        # Add header
        markdown_parts.append(f"# ARADO Website Content\n")
        markdown_parts.append(f"\n**Source URL:** {url}\n")
        markdown_parts.append(f"**Scraped:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        markdown_parts.append("\n---\n\n")
        
        # Remove script, style, and navigation elements
        for tag in soup(['script', 'style', 'meta', 'link', 'noscript']):
            tag.decompose()
        
        # Remove navigation, header, footer, login forms
        for nav in soup.find_all(['nav', 'header']):
            nav.decompose()
        
        # Remove login forms and modals
        for login_form in soup.find_all(['form', 'div'], class_=lambda x: x and ('login' in str(x).lower() or 'modal' in str(x).lower())):
            login_form.decompose()
        
        # Remove elements with login-related IDs or classes
        for elem in soup.find_all(id=lambda x: x and ('login' in str(x).lower() or 'modal' in str(x).lower())):
            elem.decompose()
        
        # Remove footer but check if it has useful content first
        footer = soup.find('footer')
        if footer:
            footer_text = footer.get_text(strip=True)
            # Only remove if it's just links/contact info
            if len(footer_text) < 100:
                footer.decompose()
        
        # Extract main content area
        main_content = soup.find('main') or soup.find('div', class_='container') or soup.body
        
        if not main_content:
            # Fallback to body
            main_content = soup.body
        
        # First, try to find main content containers
        content_containers = main_content.find_all(['section', 'article', 'main', 'div'], 
                                                   class_=re.compile(r'content|main|body|section|article|news|activity|service|training|publication|award', re.I))
        
        # If no specific containers found, use all content
        if not content_containers:
            content_containers = [main_content]
        
        # Extract headings and content
        seen_texts = set()  # Avoid duplicates
        
        for container in content_containers:
            for element in container.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div', 'ul', 'ol', 'li', 'section', 'article']):
                text = element.get_text(separator=' ', strip=True)
                
                if not text or len(text) < 3:
                    continue
                
                # Skip duplicates
                text_key = text[:50]  # Use first 50 chars as key
                if text_key in seen_texts:
                    continue
                seen_texts.add(text_key)
                
                # Skip navigation, login, and template variables - comprehensive list
                skip_patterns = [
                    'تسجيل دخول', 'نسيت كلمة السر', 'cookie', 'javascript',
                    '{{', '}}', 'ng-', 'ui-view', 'login', 'register',
                    'خطأ في عملية التسجيل', 'ادخل بريد الكتروني صحيح',
                    'جارى معالجة البيانات', 'مستخدم جديد',
                    'عذرا ، لا يوجد لدينا هذا البريد الالكتروني',
                    'عذرا ، كلمة السر غير متطابقة',
                    'هذا البريد الالكتروني لم يتم تفعيله',
                    'يرجى المحاولة مرة أخري', 'المحاولة مرة أخري',
                    'خطأ في عملية', 'عملية التسجيل'
                ]
                
                # Check if text matches skip patterns (check if ANY part matches)
                text_lower = text.lower()
                should_skip = False
                for pattern in skip_patterns:
                    if pattern.lower() in text_lower or pattern in text:
                        should_skip = True
                        break
                
                # Also check if text contains login-related Arabic phrases
                login_phrases = ['تسجيل', 'دخول', 'كلمة السر', 'البريد الالكتروني', 'خطأ']
                if any(phrase in text for phrase in login_phrases) and len(text) < 100:
                    # If it's short and contains login words, skip it
                    should_skip = True
                
                if should_skip:
                    continue
                
                # Skip single words that are navigation (AR, EN, etc.)
                if len(text.split()) <= 2 and any(word in text for word in ['AR', 'EN']):
                    continue
                
                # Skip if it's just a single word or very short
                if len(text.split()) < 3 and len(text) < 20:
                    continue
                
                tag_name = element.name
                
                if tag_name == 'h1':
                    markdown_parts.append(f"\n# {text}\n")
                elif tag_name == 'h2':
                    markdown_parts.append(f"\n## {text}\n")
                elif tag_name == 'h3':
                    markdown_parts.append(f"\n### {text}\n")
                elif tag_name == 'h4':
                    markdown_parts.append(f"\n#### {text}\n")
                elif tag_name == 'h5':
                    markdown_parts.append(f"\n##### {text}\n")
                elif tag_name == 'h6':
                    markdown_parts.append(f"\n###### {text}\n")
                elif tag_name in ['p', 'div']:
                    # Only add if it's substantial content
                    if len(text) > 20:
                        markdown_parts.append(f"\n{text}\n")
                elif tag_name == 'ul':
                    items = element.find_all('li', recursive=False)
                    if items:
                        for item in items:
                            item_text = item.get_text(strip=True)
                            if item_text:
                                markdown_parts.append(f"- {item_text}\n")
                        markdown_parts.append("\n")
                elif tag_name == 'ol':
                    items = element.find_all('li', recursive=False)
                    if items:
                        for i, item in enumerate(items, 1):
                            item_text = item.get_text(strip=True)
                            if item_text:
                                markdown_parts.append(f"{i}. {item_text}\n")
                        markdown_parts.append("\n")
        
        # Extract news/articles if present
        news_items = soup.find_all(['article', 'div'], class_=re.compile(r'news|article|post|item'))
        if news_items:
            markdown_parts.append("\n## الأخبار والمقالات / News & Articles\n\n")
            for item in news_items[:10]:  # Limit to 10 items
                title = item.find(['h1', 'h2', 'h3', 'h4', 'h5'])
                content = item.find(['p', 'div'], class_=re.compile(r'content|description|text'))
                
                if title:
                    markdown_parts.append(f"### {title.get_text(strip=True)}\n\n")
                if content:
                    markdown_parts.append(f"{content.get_text(strip=True)}\n\n")
        
        # If we have DOM-extracted content, prioritize it
        if dom_text and len(dom_text) > 500:
            current_length = len(''.join(markdown_parts))
            # Use DOM content if we got less than 1000 chars from HTML parsing
            if current_length < 1000:
                print("  Using DOM-extracted content as primary source...")
                # Keep header but replace content
                markdown_parts = [markdown_parts[0]]  # Keep header
                markdown_parts.append("\n## Content\n\n")
                markdown_parts.append(dom_text)
                markdown_text = ''.join(markdown_parts)
                return markdown_text
        
        # If we didn't get much content, extract all visible text
        markdown_text = ''.join(markdown_parts)
        if len(markdown_text) < 500:
            print("  ⚠ Low content extracted, using full text extraction...")
            text = main_content.get_text(separator='\n', strip=True)
            lines = [line.strip() for line in text.split('\n') if line.strip() and len(line.strip()) > 3]
            # Remove duplicates while preserving order
            seen = set()
            unique_lines = []
            for line in lines:
                if line not in seen and len(line) > 10:
                    # Skip template variables and navigation
                    if '{{' not in line and '}}' not in line:
                        if not any(skip in line.lower() for skip in ['تسجيل دخول', 'login', 'cookie', 'javascript']):
                            seen.add(line)
                            unique_lines.append(line)
            
            if unique_lines:
                markdown_text = f"# ARADO Website Content\n\n**Source URL:** {url}\n\n---\n\n"
                markdown_text += '\n\n'.join(unique_lines)
        
        # Post-process to remove any remaining login messages
        markdown_text = self.clean_login_messages(markdown_text)
        
        return markdown_text
    
    def clean_login_messages(self, text: str) -> str:
        """Remove login error messages and navigation text from final output"""
        lines = text.split('\n')
        cleaned_lines = []
        
        # Patterns to skip
        skip_patterns = [
            'خطأ في عملية التسجيل',
            'عذرا ، لا يوجد لدينا هذا البريد الالكتروني',
            'عذرا ، كلمة السر غير متطابقة',
            'هذا البريد الالكتروني لم يتم تفعيله',
            'جارى معالجة البيانات',
            'ادخل بريد الكتروني صحيح',
            'نسيت كلمة السر',
            'مستخدم جديد',
            'يرجى المحاولة مرة أخري',
            'المحاولة مرة أخري'
        ]
        
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue
            
            # Skip if line matches any skip pattern
            should_skip = False
            for pattern in skip_patterns:
                if pattern in line_stripped:
                    should_skip = True
                    break
            
            # Skip if it's just "AR" or "EN" or similar navigation
            if len(line_stripped) <= 3 and line_stripped in ['AR', 'EN', '- AR', '- EN']:
                should_skip = True
            
            # Skip if line contains login-related words and is short
            if len(line_stripped) < 50 and any(word in line_stripped for word in ['تسجيل', 'دخول', 'كلمة السر']):
                should_skip = True
            
            if not should_skip:
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def scrape_all(self):
        """Scrape all important sections of ARADO website"""
        
        # Define pages to scrape (based on actual website structure)
        pages_to_scrape = [
            # Home Page
            {
                'url': 'https://www.arado.org/',
                'name': 'Home Page - الصفحة الرئيسية'
            },
            
            # About ARADO Section
            {
                'url': 'https://www.arado.org/Content/Details?s3=2160',
                'name': 'About ARADO - من نحن'
            },
            {
                'url': 'https://www.arado.org/Content/Details?s3=10511',
                'name': 'Director General - المدير العام'
            },
            {
                'url': 'https://www.arado.org/Content/Details?s2=1094',
                'name': 'Organizational Structure - الهيكل التنظيمي'
            },
            {
                'url': 'https://www.arado.org/Content/Details?s2=1082',
                'name': 'Strategic Framework - الإطار الاستراتيجي'
            },
            {
                'url': 'https://www.arado.org/Content/Details?s2=1083',
                'name': 'Membership - العضوية'
            },
            {
                'url': 'https://www.arado.org/Content/Details?s3=219880',
                'name': 'Organization Units - أجهزة المنظمة'
            },
            
            # Training Programs
            {
                'url': 'https://www.arado.org/Training/List',
                'name': 'All Training Programs - جميع البرامج التدريبية'
            },
            {
                'url': 'https://www.arado.org/Training/List?type=P,1081',
                'name': 'Administrative Programs - البرامج الإدارية'
            },
            {
                'url': 'https://www.arado.org/Training/List?type=FP,1125',
                'name': 'Financial & Accounting Programs - البرامج المالية والمحاسبية'
            },
            {
                'url': 'https://www.arado.org/Training/List?type=IT,1082',
                'name': 'IT Programs - برامج تكنولوجيا المعلومات'
            },
            {
                'url': 'https://www.arado.org/Training/List?type=PM,2146',
                'name': 'Project Management Programs - برامج إدارة المشروعات'
            },
            {
                'url': 'https://www.arado.org/Training/List?type=DP,2147',
                'name': 'Professional Diplomas - الدبلومات المهنية'
            },
            {
                'url': 'https://www.arado.org/Training/List?type=SH,1080',
                'name': 'Professional Certificates - الشهادات المهنية'
            },
            
            # Events & Activities
            {
                'url': 'https://www.arado.org/Activity/List',
                'name': 'All Events - جميع الفعاليات'
            },
            {
                'url': 'https://www.arado.org/Activity/List?type=C,13',
                'name': 'Conferences - المؤتمرات'
            },
            {
                'url': 'https://www.arado.org/Activity/List?type=M,15',
                'name': 'Meetings - الملتقيات'
            },
            {
                'url': 'https://www.arado.org/Activity/List?type=N,14',
                'name': 'Seminars - الندوات'
            },
            {
                'url': 'https://www.arado.org/Activity/List?type=MN,17',
                'name': 'Forums - المنتديات'
            },
            {
                'url': 'https://www.arado.org/Activity/List?type=W,16',
                'name': 'Workshops - ورش العمل'
            },
            {
                'url': 'https://www.arado.org/Activity/List?type=OE,4336',
                'name': 'Online Events - فعاليات عن بعد'
            },
            
            # Publications
            {
                'url': 'https://www.arado.org/Publication/List',
                'name': 'All Publications - جميع الإصدارات'
            },
            {
                'url': 'https://www.arado.org/Content/Details?s2=1009',
                'name': 'Scientific Publications - النشر العلمي'
            },
            {
                'url': 'https://www.arado.org/Content/Details?s2=1039',
                'name': 'Arab Management Journal - المجلة العربية للإدارة'
            },
            {
                'url': 'https://www.arado.org/Content/Details?s2=1099',
                'name': 'Translation & Distribution - الترجمة وتوزيع المطبوعات'
            },
            {
                'url': 'https://www.arado.org/Content/Details?s2=1135',
                'name': 'Specialized Studies - الدراسات المتخصصة'
            },
            
            # Awards
            {
                'url': 'https://www.arado.org/Content/Details?s2=1066',
                'name': 'Awards Overview - الجوائز المتخصصة'
            },
            {
                'url': 'https://www.arado.org/Content/Details?s3=1051',
                'name': 'Sharjah Award for Best PhD Thesis - جائزة الشارقة لأفضل أطروحة دكتوراه'
            },
            {
                'url': 'https://www.arado.org/Content/Details?s3=1057',
                'name': 'Prince Mohammed bin Fahd Award for Best Charitable Performance - جائزة الأمير محمد بن فهد'
            },
            {
                'url': 'https://www.arado.org/Content/Details?s3=2139',
                'name': 'Sharjah Award in Public Finance - جائزة الشارقة في المالية العامة'
            },
            {
                'url': 'https://www.arado.org/Content/Details?s3=2142',
                'name': 'Prince Mohammed bin Fahd Award for Best Book - جائزة الأمير محمد بن فهد لأفضل كتاب'
            },
            {
                'url': 'https://www.arado.org/Content/Details?s3=2150',
                'name': 'Arab Government Excellence Award - جائزة التميّز الحكومي العربي'
            },
            
            # Consulting Services
            {
                'url': 'https://www.arado.org/Content/Details?s3=2154',
                'name': 'Consulting Services Overview - الخدمات الإستشارية'
            },
            {
                'url': 'https://www.arado.org/Content/Details?s3=3330',
                'name': 'Information & Digital Transformation Consulting - استشارات المعلومات والتحول الرقمي'
            },
            {
                'url': 'https://www.arado.org/Content/Details?s3=2298',
                'name': 'Information Security Consulting - استشارات قطاع أمن المعلومات'
            },
            {
                'url': 'https://www.arado.org/Content/Details?s3=2303',
                'name': 'Governance Studies - دراسات استشارية في الحوكمة'
            },
            {
                'url': 'https://www.arado.org/Content/Details?s3=2305',
                'name': 'Sustainable Development Consulting - استشارات التنمية المستدامة'
            },
            {
                'url': 'https://www.arado.org/Content/Details?s3=2307',
                'name': 'Strategic Studies - الدراسات الاستراتيجية'
            },
            {
                'url': 'https://www.arado.org/Content/Details?s3=2310',
                'name': 'Evaluation Studies - الدراسات التقييمية'
            },
            {
                'url': 'https://www.arado.org/Content/Details?s3=2318',
                'name': 'Organizational Studies - الدراسات التنظيمية ونظم العمل'
            },
            {
                'url': 'https://www.arado.org/Content/Details?s3=2',
                'name': 'Training Consulting - التدريب'
            },
            {
                'url': 'https://www.arado.org/Content/Details?s3=1123',
                'name': 'Contractual Programs - البرامج التعاقدية'
            },
            
            # Digital Library
            {
                'url': 'https://www.arado.org/Content/Details?s2=1070',
                'name': 'Digital Library Overview - المكتبة الرقمية'
            },
            {
                'url': 'https://www.arado.org/Content/Details?s2=1072',
                'name': 'Arab Administrative Information Base - قاعدة المعلومات الإدارية - إبداع'
            },
            {
                'url': 'https://www.arado.org/Content/Details?s2=1080',
                'name': 'Knowledge Base - قاعدة بيانات'
            },
            {
                'url': 'https://www.arado.org/Content/Details?s3=2238',
                'name': 'Library Services - خدمات المكتبة'
            },
            {
                'url': 'https://www.arado.org/Content/Details?s3=2173',
                'name': 'About Digital Library - عن المكتبة الرقمية'
            },
            {
                'url': 'https://www.arado.org/Content/Details?s3=2159',
                'name': 'Arab Management News Bulletin - نشرة أخبار الإدارة العربية'
            },
            
            # News
            {
                'url': 'https://www.arado.org/News/List',
                'name': 'All News - أخبار المنظمة'
            },
            
            # Other Services
            {
                'url': 'https://www.arado.org/Content/Details?s3=2152',
                'name': 'Events Services - الفعاليات'
            },
            {
                'url': 'https://www.arado.org/Job/List',
                'name': 'Jobs - الوظائف'
            },
            {
                'url': 'https://www.arado.org/Tender/List',
                'name': 'Tenders - المناقصات والممارسات'
            },
            {
                'url': 'https://www.arado.org/Contact/Index',
                'name': 'Contact Us - الاتصال بنا'
            },
            {
                'url': 'https://www.arado.org/Staff/List',
                'name': 'Departments & Units - الإدارات والوحدات'
            },
        ]
        
        print("="*70)
        print("ARADO Website Scraper (Angular/SPA)")
        print("="*70)
        print(f"Total pages to scrape: {len(pages_to_scrape)}")
        print("="*70)
        
        # Initialize Selenium
        if not self.init_selenium():
            print("✗ Cannot proceed without Selenium")
            return
        
        try:
            # Scrape each page
            for i, page in enumerate(pages_to_scrape, 1):
                print(f"\n[{i}/{len(pages_to_scrape)}] {page['name']}")
                print("="*70)
                
                result = self.scrape_page(page['url'], page['name'])
                self.results.append(result)
                
                # Rate limiting
                if i < len(pages_to_scrape):
                    print("  Waiting 3 seconds before next page...")
                    time.sleep(3)
            
        finally:
            # Clean up
            if self.driver:
                print("\nClosing browser...")
                self.driver.quit()
        
        # Save all content in one markdown file
        self.save_combined_markdown()
        
        # Save final results
        self.save_results()
        
        print("\n" + "="*70)
        print("Scraping complete!")
        print("="*70)
        
        # Summary
        successful = sum(1 for r in self.results if r['status'] == 'success')
        failed = sum(1 for r in self.results if r['status'] == 'error')
        print(f"✓ Successfully scraped: {successful} pages")
        if failed > 0:
            print(f"✗ Failed: {failed} pages")
    
    def save_combined_markdown(self):
        """Save all scraped content in one combined markdown file"""
        output_dir = 'markdown_output'
        os.makedirs(output_dir, exist_ok=True)
        
        filename = 'arado_website_complete.md'
        filepath = os.path.join(output_dir, filename)
        
        # Combine all successful results
        combined_content = []
        combined_content.append("# ARADO Website - Complete Content\n")
        combined_content.append(f"\n**Scraped:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        combined_content.append(f"**Total Pages:** {len([r for r in self.results if r['status'] == 'success'])}\n")
        combined_content.append("\n---\n\n")
        
        # Add table of contents
        combined_content.append("## Table of Contents\n\n")
        for i, result in enumerate(self.results, 1):
            if result['status'] == 'success':
                # Create anchor link (extract regex outside f-string)
                anchor = re.sub(r'[^\w\s-]', '', result['page_name'].lower().replace(' ', '-'))
                combined_content.append(f"{i}. [{result['page_name']}](#{anchor})\n")
        combined_content.append("\n---\n\n")
        
        # Add each page's content
        for i, result in enumerate(self.results, 1):
            if result['status'] == 'success':
                combined_content.append(f"\n{'='*70}\n")
                combined_content.append(f"## {i}. {result['page_name']}\n\n")
                combined_content.append(f"**URL:** {result['url']}\n\n")
                combined_content.append("---\n\n")
                
                # Extract content without the header (since we're combining)
                content = result['markdown_content']
                # Remove the header if it exists
                if content.startswith('# ARADO Website Content'):
                    # Find the first --- separator and skip everything before it
                    parts = content.split('---', 1)
                    if len(parts) > 1:
                        content = parts[1].strip()
                
                combined_content.append(content)
                combined_content.append("\n\n")
            else:
                combined_content.append(f"\n{'='*70}\n")
                combined_content.append(f"## {i}. {result['page_name']} - FAILED\n\n")
                combined_content.append(f"**URL:** {result['url']}\n\n")
                combined_content.append(f"**Error:** {result.get('error', 'Unknown error')}\n\n")
        
        # Write combined file
        full_content = ''.join(combined_content)
        
        # Clean login messages from final output
        full_content = self.clean_login_messages(full_content)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(full_content)
        
        print(f"\n✓ Saved combined markdown: {filepath} ({len(full_content)} chars)")
    
    def save_results(self):
        """Save results summary to JSON"""
        output_file = 'web_scraped_data_arado.json'
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        
        print(f"\n✓ Saved results summary: {output_file}")


def main():
    scraper = ARADOScraper()
    scraper.scrape_all()


if __name__ == '__main__':
    main()

