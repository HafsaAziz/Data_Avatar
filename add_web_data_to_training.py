"""
Script to add web scraped data to chatbot training data
"""
import json
import os
from typing import List, Dict

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

def load_web_scraped_data(file_path: str) -> List[Dict]:
    """Load web scraped data from JSON file"""
    if not os.path.exists(file_path):
        print(f"⚠ Warning: {file_path} not found, skipping...")
        return []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return data

def extract_content_from_web_entry(entry: Dict) -> str:
    """Extract markdown content from web scraped entry"""
    # Try different field names that might contain the content
    if 'markdown_content' in entry:
        return entry['markdown_content']
    elif 'webpage_content' in entry:
        return entry['webpage_content']
    elif 'markdown' in entry:
        return entry['markdown']
    elif 'content' in entry:
        return entry['content']
    else:
        return ""

def process_web_scraped_files(web_files: List[str]) -> List[Dict]:
    """Process all web scraped JSON files and convert to training data format"""
    all_web_data = []
    
    for file_path in web_files:
        print(f"\nProcessing: {file_path}")
        web_data = load_web_scraped_data(file_path)
        
        if not web_data:
            continue
        
        for entry in web_data:
            # Skip failed entries
            if entry.get('status') != 'success' and 'status' in entry:
                continue
            
            # Extract content
            content = extract_content_from_web_entry(entry)
            
            if not content or len(content.strip()) < 50:  # Skip very short content
                continue
            
            # Get URL
            url = entry.get('url', 'unknown')
            
            # Create result entry similar to PDF extraction format
            result_entry = {
                'status': 'success',
                'source_type': 'web',
                'source': url,
                'markdown': content,
                'title': entry.get('title', ''),
                'url': url
            }
            
            all_web_data.append(result_entry)
            print(f"  ✓ Added: {url[:80]}... ({len(content)} chars)")
    
    return all_web_data

def add_web_data_to_training(web_files: List[str], training_data_file: str = 'chatbot_training_data.json'):
    """Add web scraped data to existing chatbot training data"""
    
    # Load existing training data
    existing_training_data = []
    if os.path.exists(training_data_file):
        print(f"\nLoading existing training data from {training_data_file}...")
        with open(training_data_file, 'r', encoding='utf-8') as f:
            existing_training_data = json.load(f)
        print(f"  Found {len(existing_training_data)} existing entries")
    else:
        print(f"\n⚠ Warning: {training_data_file} not found. Creating new file...")
    
    # Process web scraped files
    print("\n" + "=" * 70)
    print("Processing web scraped data files")
    print("=" * 70)
    web_results = process_web_scraped_files(web_files)
    
    if not web_results:
        print("\n⚠ No web data to add!")
        return
    
    # Convert web results to training data format
    print("\n" + "=" * 70)
    print("Converting web data to training format")
    print("=" * 70)
    
    new_training_entries = []
    for result in web_results:
        if result['status'] == 'success' and 'markdown' in result:
            markdown_content = result['markdown']
            
            # Split into chunks
            chunks = split_markdown_into_chunks(markdown_content, max_length=2000)
            
            for i, chunk in enumerate(chunks):
                new_training_entries.append({
                    'id': f"web_{hash(result['source'])}_{i}",
                    'source_type': 'web',
                    'source': result['source'],
                    'chunk_index': i,
                    'text': chunk,
                    'metadata': {
                        'source': result['source'],
                        'source_type': 'web',
                        'title': result.get('title', ''),
                        'url': result.get('url', result['source'])
                    }
                })
    
    print(f"  Created {len(new_training_entries)} new training chunks from web data")
    
    # Combine with existing data
    print("\n" + "=" * 70)
    print("Combining with existing training data")
    print("=" * 70)
    
    # Check for duplicates based on source URL
    existing_sources = {entry.get('source', '') for entry in existing_training_data}
    duplicates = 0
    
    final_training_data = existing_training_data.copy()
    for entry in new_training_entries:
        if entry['source'] not in existing_sources:
            final_training_data.append(entry)
        else:
            duplicates += 1
    
    if duplicates > 0:
        print(f"  Skipped {duplicates} duplicate entries")
    
    # Save updated training data
    print("\n" + "=" * 70)
    print("Saving updated training data")
    print("=" * 70)
    
    with open(training_data_file, 'w', encoding='utf-8') as f:
        json.dump(final_training_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ Successfully updated {training_data_file}")
    print(f"  Total entries: {len(final_training_data)}")
    print(f"  Existing entries: {len(existing_training_data)}")
    print(f"  New web entries: {len(new_training_entries) - duplicates}")
    print(f"  Duplicates skipped: {duplicates}")

if __name__ == "__main__":
    # List of web scraped data files to process
    web_files = [
        'web_scraped_data_arado.json',
        'web_scraped_data.json',
        'web_scraped_data_leagueofarabstates.json',
        'web_scraped_data_uae.json'
    ]
    
    add_web_data_to_training(web_files)

