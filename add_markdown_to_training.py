"""
Script to add markdown files to chatbot training data
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

def add_markdown_file_to_training(markdown_file: str, training_data_file: str = 'chatbot_training_data.json'):
    """Add a markdown file to chatbot training data"""
    
    # Check if markdown file exists
    if not os.path.exists(markdown_file):
        print(f"⚠ Error: {markdown_file} not found!")
        return
    
    # Load existing training data
    existing_training_data = []
    if os.path.exists(training_data_file):
        print(f"\nLoading existing training data from {training_data_file}...")
        with open(training_data_file, 'r', encoding='utf-8') as f:
            existing_training_data = json.load(f)
        print(f"  Found {len(existing_training_data)} existing entries")
    else:
        print(f"\n⚠ Warning: {training_data_file} not found. Creating new file...")
    
    # Read markdown file
    print(f"\nReading markdown file: {markdown_file}")
    with open(markdown_file, 'r', encoding='utf-8') as f:
        markdown_content = f.read()
    
    if not markdown_content or len(markdown_content.strip()) < 50:
        print("⚠ Warning: Markdown file is empty or too short!")
        return
    
    print(f"  Content length: {len(markdown_content)} characters")
    
    # Extract source name from filename
    source_name = os.path.basename(markdown_file)
    source_path = markdown_file.replace('\\', '/')  # Normalize path separators
    
    # Check if this source already exists
    existing_sources = {entry.get('source', '') for entry in existing_training_data}
    
    if source_path in existing_sources or f"markdown/{source_name}" in existing_sources:
        print(f"⚠ Warning: Source already exists in training data. Skipping...")
        return
    
    # Split into chunks
    print("\nSplitting into chunks...")
    chunks = split_markdown_into_chunks(markdown_content, max_length=2000)
    print(f"  Created {len(chunks)} chunks")
    
    # Create training entries
    print("\nCreating training entries...")
    new_training_entries = []
    for i, chunk in enumerate(chunks):
        new_training_entries.append({
            'id': f"markdown_{hash(source_path)}_{i}",
            'source_type': 'markdown',
            'source': source_path,
            'chunk_index': i,
            'text': chunk,
            'metadata': {
                'source': source_path,
                'source_type': 'markdown',
                'filename': source_name
            }
        })
    
    # Combine with existing data
    print("\nCombining with existing training data...")
    final_training_data = existing_training_data + new_training_entries
    
    # Save updated training data
    print("\nSaving updated training data...")
    with open(training_data_file, 'w', encoding='utf-8') as f:
        json.dump(final_training_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ Successfully updated {training_data_file}")
    print(f"  Total entries: {len(final_training_data)}")
    print(f"  Existing entries: {len(existing_training_data)}")
    print(f"  New markdown entries: {len(new_training_entries)}")

if __name__ == "__main__":
    markdown_file = 'markdown_output/speech_Mohammed_Al_Gergawi_Global_Future_Councils_2018.md'
    add_markdown_file_to_training(markdown_file)

