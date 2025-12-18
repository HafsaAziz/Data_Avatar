import os
import json
from pathlib import Path
from docling.document_converter import DocumentConverter
from typing import List, Dict, Optional
import time

# Initialize the converter
converter = DocumentConverter()


def process_pdf_url(pdf_url: str) -> Optional[Dict]:
    """Process a PDF from URL"""
    try:
        print(f"Processing PDF URL: {pdf_url}")
        result = converter.convert(pdf_url)
        
        if result.document:
            document = result.document
            return {
                'source_type': 'pdf_url',
                'source': pdf_url,
                'markdown': document.export_to_markdown(),
                'json': document.export_to_dict(),
                'status': 'success'
            }
        else:
            return {
                'source_type': 'pdf_url',
                'source': pdf_url,
                'status': 'failed',
                'error': 'No document extracted'
            }
    except Exception as e:
        print(f"Error processing {pdf_url}: {str(e)}")
        return {
            'source_type': 'pdf_url',
            'source': pdf_url,
            'status': 'error',
            'error': str(e)
        }

def process_web_url(url: str) -> Optional[Dict]:
    """Process a web page URL"""
    try:
        print(f"Processing web URL: {url}")
        result = converter.convert(url)
        
        if result.document:
            document = result.document
            return {
                'source_type': 'web',
                'source': url,
                'markdown': document.export_to_markdown(),
                'json': document.export_to_dict(),
                'status': 'success'
            }
        else:
            return {
                'source_type': 'web',
                'source': url,
                'status': 'failed',
                'error': 'No document extracted'
            }
    except Exception as e:
        print(f"Error processing {url}: {str(e)}")
        return {
            'source_type': 'web',
            'source': url,
            'status': 'error',
            'error': str(e)
        }

def process_local_document(doc_path: str) -> Optional[Dict]:
    """Process a local document file (PDF, DOCX, etc.) using Docling"""
    try:
        file_ext = Path(doc_path).suffix.lower()
        doc_type = 'pdf' if file_ext == '.pdf' else 'docx' if file_ext in ['.docx', '.doc'] else 'document'
        
        print(f"Processing {doc_type.upper()}: {os.path.basename(doc_path)}")
        result = converter.convert(doc_path)
        
        if result.document:
            document = result.document
            return {
                'source_type': doc_type,
                'source': os.path.basename(doc_path),
                'filepath': doc_path,
                'markdown': document.export_to_markdown(),
                'json': document.export_to_dict(),
                'status': 'success'
            }
        else:
            return {
                'source_type': doc_type,
                'source': os.path.basename(doc_path),
                'filepath': doc_path,
                'status': 'failed',
                'error': 'No document extracted'
            }
    except Exception as e:
        print(f"Error processing {doc_path}: {str(e)}")
        return {
            'source_type': 'document',
            'source': os.path.basename(doc_path),
            'filepath': doc_path,
            'status': 'error',
            'error': str(e)
        }

def process_all_local_documents(directory_path: str = ".") -> List[Dict]:
    """Process all PDF and DOCX files in a directory"""
    pdf_files = list(Path(directory_path).glob("*.pdf"))
    docx_files = list(Path(directory_path).glob("*.docx"))
    doc_files = list(Path(directory_path).glob("*.doc"))
    
    all_files = pdf_files + docx_files + doc_files
    results = []
    
    print(f"Found {len(pdf_files)} PDF files, {len(docx_files)} DOCX files, {len(doc_files)} DOC files")
    
    for doc_file in all_files:
        result = process_local_document(str(doc_file))
        if result:
            results.append(result)
        # Small delay to avoid overwhelming the system
        time.sleep(0.5)
    
    return results

def load_urls_from_file(file_path: str) -> List[str]:
    """Load URLs from a text file (one per line)"""
    urls = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                urls.append(line)
    return urls

def process_urls_from_file(urls_file: str) -> List[Dict]:
    """Process all URLs from a file"""
    urls = load_urls_from_file(urls_file)
    results = []
    
    print(f"Found {len(urls)} URLs to process")
    
    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{len(urls)}] Processing: {url}")
        
        # Determine if it's a PDF or web page
        if url.lower().endswith('.pdf') or '/pdf' in url.lower():
            result = process_pdf_url(url)
        else:
            result = process_web_url(url)
        
        if result:
            results.append(result)
        
        # Rate limiting - be respectful
        if i < len(urls):
            time.sleep(2)  # 2 second delay between requests
    
    return results

def save_results(results: List[Dict], output_file: str = 'extracted_data.json'):
    """Save all results to a JSON file"""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved {len(results)} results to {output_file}")

def prepare_chatbot_training_data(results: List[Dict], output_file: str = 'chatbot_training_data.json'):
    """Prepare data in a format suitable for chatbot training"""
    training_data = []
    
    for result in results:
        if result['status'] == 'success' and 'markdown' in result:
            # Split markdown into chunks if needed
            markdown_content = result['markdown']
            
            # Split into chunks if content is too long
            chunks = split_markdown_into_chunks(markdown_content, max_length=2000)
            
            for i, chunk in enumerate(chunks):
                training_data.append({
                    'id': f"{result['source_type']}_{hash(result['source'])}_{i}",
                    'source_type': result['source_type'],
                    'source': result['source'],
                    'chunk_index': i,
                    'text': chunk,
                    'metadata': {
                        'source': result['source'],
                        'source_type': result['source_type']
                    }
                })
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(training_data, f, ensure_ascii=False, indent=2)
    
    print(f"\nPrepared {len(training_data)} training chunks for chatbot!")
    return training_data

def split_markdown_into_chunks(text: str, max_length: int = 2000) -> List[str]:
    """Split markdown text into smaller chunks"""
    # Split by double newlines (paragraphs)
    paragraphs = text.split('\n\n')
    chunks = []
    current_chunk = []
    current_length = 0
    
    for para in paragraphs:
        para_length = len(para)
        
        if current_length + para_length > max_length and current_chunk:
            chunks.append('\n\n'.join(current_chunk))
            # Overlap: keep last 3 paragraphs for context
            overlap_paras = current_chunk[-3:] if len(current_chunk) > 3 else current_chunk
            current_chunk = overlap_paras
            current_length = sum(len(p) + 2 for p in current_chunk)
        
        current_chunk.append(para)
        current_length += para_length + 2  # +2 for '\n\n'
    
    if current_chunk:
        chunks.append('\n\n'.join(current_chunk))
    
    return chunks if chunks else [text]

def export_markdown_files(results: List[Dict], output_dir: str = 'markdown_output'):
    """Export markdown files for each successful extraction"""
    os.makedirs(output_dir, exist_ok=True)
    
    for result in results:
        if result['status'] == 'success' and 'markdown' in result:
            # Create safe filename
            source_name = result['source'].replace('https://', '').replace('http://', '')
            source_name = ''.join(c if c.isalnum() or c in ('-', '_', '.') else '_' for c in source_name)
            source_name = source_name[:100]  # Limit length
            
            filename = f"{result['source_type']}_{source_name}.md"
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"# Source: {result['source']}\n\n")
                f.write(f"**Type:** {result['source_type']}\n\n")
                f.write("---\n\n")
                f.write(result['markdown'])
            
            print(f"Exported markdown: {filename}")

# Main execution
if __name__ == "__main__":
    all_results = []
    
    # Step 1: Process all local documents (PDFs, DOCX, DOC)
    print("=" * 70)
    print("STEP 1: Processing local documents (PDFs, DOCX, DOC)")
    print("=" * 70)
    data_folder = "data"
    if not os.path.exists(data_folder):
        print(f"⚠ Warning: '{data_folder}' folder not found. Creating it...")
        os.makedirs(data_folder, exist_ok=True)
    
    doc_results = process_all_local_documents(data_folder)
    all_results.extend(doc_results)
    print(f"✓ Processed {len(doc_results)} document files")
    
    # Step 2: Process URLs from file (if exists)
    urls_file = "urls.txt"
    if os.path.exists(urls_file):
        print("\n" + "=" * 70)
        print("STEP 2: Processing URLs from file")
        print("=" * 70)
        url_results = process_urls_from_file(urls_file)
        all_results.extend(url_results)
        print(f"✓ Processed {len(url_results)} URLs")
    else:
        print(f"\n⚠ No {urls_file} found. Create a urls.txt file with one URL per line to scrape web pages.")
    
    # Step 3: Save raw results
    print("\n" + "=" * 70)
    print("STEP 3: Saving raw results")
    print("=" * 70)
    save_results(all_results, 'extracted_data.json')
    
    # Step 4: Export markdown files
    print("\n" + "=" * 70)
    print("STEP 4: Exporting markdown files")
    print("=" * 70)
    export_markdown_files(all_results)
    
    # Step 5: Prepare chatbot training data
    print("\n" + "=" * 70)
    print("STEP 5: Preparing chatbot training data")
    print("=" * 70)
    training_data = prepare_chatbot_training_data(all_results)
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    successful = sum(1 for r in all_results if r['status'] == 'success')
    failed = len(all_results) - successful
    print(f"Total processed: {len(all_results)}")
    print(f"✓ Successful: {successful}")
    print(f"✗ Failed: {failed}")
    print(f"📄 Training chunks created: {len(training_data)}")
    print(f"\nOutput files:")
    print(f"  - extracted_data.json (raw extracted data)")
    print(f"  - chatbot_training_data.json (formatted for chatbot)")
    print(f"  - markdown_output/ (individual markdown files)")

