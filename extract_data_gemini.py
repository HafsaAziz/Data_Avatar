import os
import json
import base64
from pathlib import Path
from typing import List, Dict, Optional
import time
import io

# Try to import PyPDF2 for page splitting
try:
    import PyPDF2
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False
    print("⚠️  PyPDF2 not installed. Install with: pip install PyPDF2")
    print("   For now, processing entire PDFs (may truncate long documents)")

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # .env loading is optional

# Use the old API (google.generativeai) for better compatibility with PDFs
# The new google.genai API has file upload issues
try:
    from google import generativeai as genai
    USE_NEW_API = False
except ImportError:
    try:
        import google.genai as genai
        USE_NEW_API = True
        print("⚠️  Using google.genai API. Consider installing google-generativeai for better PDF support.")
    except ImportError:
        print("ERROR: Neither google.genai nor google.generativeai found!")
        print("Please install: pip install google-generativeai")
        exit(1)

# Configure Gemini API
# Set your API key as environment variable: export GEMINI_API_KEY="your-api-key"
# Or add it to .env file: GEMINI_API_KEY=your-api-key
# Or set it directly here (not recommended for production)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Use Gemini Pro model with vision capabilities
# Available models: gemini-1.5-pro, gemini-1.5-flash, gemini-2.0-flash-exp
MODEL_NAME = "gemini-pro-latest"  # Based on API endpoint format

# API client will be initialized after checking for API key in main block
client = None

def encode_pdf_to_base64(pdf_path: str) -> str:
    """Encode PDF file to base64 string"""
    with open(pdf_path, 'rb') as pdf_file:
        return base64.b64encode(pdf_file.read()).decode('utf-8')

def split_pdf_into_pages(pdf_path: str) -> List[bytes]:
    """Split PDF into individual pages and return as list of PDF bytes"""
    if not HAS_PYPDF2:
        return None
    
    try:
        pages = []
        with open(pdf_path, 'rb') as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            total_pages = len(pdf_reader.pages)
            
            for page_num in range(total_pages):
                # Create a new PDF with just this page
                pdf_writer = PyPDF2.PdfWriter()
                pdf_writer.add_page(pdf_reader.pages[page_num])
                
                # Write to bytes buffer
                page_buffer = io.BytesIO()
                pdf_writer.write(page_buffer)
                pages.append(page_buffer.getvalue())
        
        return pages
    except Exception as e:
        print(f"  ⚠ Warning: Could not split PDF into pages: {e}")
        return None

def extract_text_from_pdf_gemini(pdf_path: str, process_by_pages: bool = True) -> Optional[Dict]:
    """Extract text from PDF using Gemini VLM, optionally processing page-by-page"""
    try:
        print(f"Processing PDF: {os.path.basename(pdf_path)}")
        
        # Try to split into pages if requested and PyPDF2 is available
        pages = None
        if process_by_pages and HAS_PYPDF2:
            print(f"  Splitting PDF into pages...")
            pages = split_pdf_into_pages(pdf_path)
            if pages:
                print(f"  ✓ Split into {len(pages)} pages, processing page-by-page...")
            else:
                print(f"  ⚠ Could not split pages, processing entire PDF...")
        
        # Create prompt for text extraction
        page_prompt = """You are a document extraction tool. Extract EVERY SINGLE WORD from these PDF pages. 

ABSOLUTE REQUIREMENTS - NO EXCEPTIONS:
1. Extract EVERY word, sentence, paragraph, section, table, chart from these pages
2. Do NOT summarize ANYTHING - extract verbatim text where possible
3. Do NOT use phrases like "and so on", "continues for", "would exceed", "demonstrates the methodology"
4. Do NOT skip sections - EXTRACT EVERYTHING
5. For charts/graphs: Extract ALL numerical values, percentages, categories, and data points
6. For tables: Extract ALL rows and columns completely

CHARTS AND VISUALIZATIONS - EXTRACT ALL DATA:
- Read every number, percentage, and value shown in charts
- List every category and its exact value
- Example: "Egypt: 65%, Turkey: 72%, KSA: 68%, Korea: 85%, UAE: 78%, China: 82%"
- Do NOT say "the document includes charts" - EXTRACT THE ACTUAL DATA VALUES
- Convert all visual data into text with specific numbers

FORMAT:
- Use # for main headings, ## for subheadings
- Extract tables as markdown tables with ALL data
- Preserve structure and organization

CRITICAL: Extract ALL content from these pages. Do not summarize. Do not skip. Do not use placeholders."""

        full_prompt = """You are a document extraction tool. Your ONLY job is to extract EVERY SINGLE WORD from this PDF document. 

ABSOLUTE REQUIREMENTS - NO EXCEPTIONS:
1. Extract EVERY word, sentence, paragraph, section, table, chart, and appendix
2. Do NOT summarize ANYTHING - extract verbatim text where possible
3. Do NOT use phrases like "and so on", "continues for", "would exceed", "demonstrates the methodology"
4. Do NOT skip sections saying "the extraction will continue" - ACTUALLY EXTRACT THEM
5. Extract ALL content from beginning to end - NO SKIPPING
6. If the document is long, extract it ALL - do not stop or summarize
7. For charts/graphs: Extract ALL numerical values, percentages, categories, and data points
8. For tables: Extract ALL rows and columns completely
9. For appendices: Extract EVERYTHING completely

CHARTS AND VISUALIZATIONS - EXTRACT ALL DATA:
- Read every number, percentage, and value shown in charts
- List every category and its exact value
- Example: "Egypt: 65%, Turkey: 72%, KSA: 68%, Korea: 85%, UAE: 78%, China: 82%"
- Do NOT say "the document includes charts" - EXTRACT THE ACTUAL DATA VALUES
- Convert all visual data into text with specific numbers

FORMAT:
- Use # for main headings, ## for subheadings
- Extract tables as markdown tables with ALL data
- Preserve structure and organization
- Include ALL metadata

CRITICAL: Extract the ENTIRE document from start to finish. Every section, every paragraph, every table, every chart, every appendix must be included. Do not summarize. Do not skip. Do not use placeholders."""

        # Process page-by-page if pages are available
        if pages and len(pages) > 0:
            print(f"  Processing {len(pages)} pages in batches...")
            all_extracted_texts = []
            batch_size = 5  # Process 5 pages at a time to avoid token limits
            
            model_names_to_try = ["gemini-pro-latest", "gemini-1.5-pro-latest", "gemini-1.5-pro", "gemini-pro", "gemini-1.5-flash"]
            working_model = None
            
            # Find a working model first
            for model_name in model_names_to_try:
                try:
                    test_model = genai.GenerativeModel(model_name)
                    working_model = test_model
                    print(f"  Using model: {model_name}")
                    break
                except:
                    continue
            
            if not working_model:
                raise Exception("No working model found")
            
            # Process pages in batches
            for batch_start in range(0, len(pages), batch_size):
                batch_end = min(batch_start + batch_size, len(pages))
                batch_pages = pages[batch_start:batch_end]
                print(f"  Processing pages {batch_start+1}-{batch_end} of {len(pages)}...")
                
                # Combine batch pages into a single PDF
                combined_pdf_writer = PyPDF2.PdfWriter()
                for page_bytes in batch_pages:
                    page_reader = PyPDF2.PdfReader(io.BytesIO(page_bytes))
                    combined_pdf_writer.add_page(page_reader.pages[0])
                
                combined_buffer = io.BytesIO()
                combined_pdf_writer.write(combined_buffer)
                batch_pdf_data = combined_buffer.getvalue()
                batch_pdf_base64 = base64.b64encode(batch_pdf_data).decode('utf-8')
                
                # Retry logic for failed batches
                max_retries = 3
                batch_text = None
                
                for retry in range(max_retries):
                    try:
                        # Use streaming for batch
                        full_text_parts = []
                        response_stream = working_model.generate_content(
                            [
                                page_prompt,
                                {
                                    "mime_type": "application/pdf",
                                    "data": batch_pdf_base64
                                }
                            ],
                            stream=True
                        )
                        
                        for chunk in response_stream:
                            if chunk.text:
                                full_text_parts.append(chunk.text)
                        
                        batch_text = "".join(full_text_parts)
                        
                        # Check if we got valid content
                        if batch_text and len(batch_text.strip()) > 0:
                            all_extracted_texts.append(batch_text)
                            print(f"    ✓ Extracted {len(batch_text)} chars from pages {batch_start+1}-{batch_end}")
                            break  # Success, exit retry loop
                        else:
                            raise Exception("Empty response received")
                    
                    except Exception as e:
                        error_msg = str(e)
                        if retry < max_retries - 1:
                            wait_time = (retry + 1) * 2  # Exponential backoff: 2s, 4s, 6s
                            print(f"    ⚠ Error processing batch {batch_start+1}-{batch_end} (attempt {retry+1}/{max_retries}): {error_msg}")
                            print(f"    Retrying in {wait_time} seconds...")
                            time.sleep(wait_time)
                        else:
                            # Last retry failed, try processing pages individually
                            print(f"    ⚠ Batch failed after {max_retries} attempts. Trying individual pages...")
                            individual_texts = []
                            
                            for page_idx, page_bytes in enumerate(batch_pages):
                                page_num = batch_start + page_idx + 1
                                try:
                                    page_base64 = base64.b64encode(page_bytes).decode('utf-8')
                                    
                                    response_stream = working_model.generate_content(
                                        [
                                            page_prompt,
                                            {
                                                "mime_type": "application/pdf",
                                                "data": page_base64
                                            }
                                        ],
                                        stream=True
                                    )
                                    
                                    page_text_parts = []
                                    for chunk in response_stream:
                                        if chunk.text:
                                            page_text_parts.append(chunk.text)
                                    
                                    page_text = "".join(page_text_parts)
                                    if page_text and len(page_text.strip()) > 0:
                                        individual_texts.append(page_text)
                                        print(f"      ✓ Extracted page {page_num} ({len(page_text)} chars)")
                                    else:
                                        print(f"      ⚠ Page {page_num} returned empty response")
                                    
                                    time.sleep(0.5)  # Small delay between individual pages
                                    
                                except Exception as page_error:
                                    print(f"      ⚠ Page {page_num} failed: {page_error}")
                                    continue
                            
                            if individual_texts:
                                combined_individual = "\n\n---\n\n".join(individual_texts)
                                all_extracted_texts.append(combined_individual)
                                print(f"    ✓ Extracted {len(combined_individual)} chars from {len(individual_texts)} individual pages")
                            else:
                                print(f"    ✗ Failed to extract any content from pages {batch_start+1}-{batch_end}")
                            
                            break  # Exit retry loop
                
                # Rate limiting between batches
                time.sleep(1)
            
            # Combine all extracted texts
            extracted_text = "\n\n---\n\n".join(all_extracted_texts)
            print(f"  ✓ Combined extraction: {len(extracted_text)} total characters from {len(pages)} pages")
        
        else:
            # Fallback: process entire PDF
            print(f"  Processing entire PDF (page-by-page not available)...")
            
            # Read PDF file
            with open(pdf_path, 'rb') as pdf_file:
                pdf_data = pdf_file.read()
            
            # Use new or old API
            if USE_NEW_API:
                # New API - google.genai - use base64 format
                pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')
                try:
                    response = client.models.generate_content(
                        model=MODEL_NAME,
                        contents=[full_prompt, {"mime_type": "application/pdf", "data": pdf_base64}]
                    )
                    extracted_text = str(response.text) if response.text else ""
                except Exception as e:
                    try:
                        uploaded_file = client.files.upload(path=pdf_path)
                        response = client.models.generate_content(
                            model=MODEL_NAME,
                            contents=[full_prompt, uploaded_file]
                        )
                        extracted_text = str(response.text) if response.text else ""
                        client.files.delete(name=uploaded_file.name)
                    except:
                        raise e
            else:
                # Old API - google.generativeai - try multiple model names
                model_names_to_try = ["gemini-pro-latest", "gemini-1.5-pro-latest", "gemini-1.5-pro", "gemini-pro", "gemini-1.5-flash"]
                extracted_text = ""
                last_error = None
                
                for model_name in model_names_to_try:
                    try:
                        model = genai.GenerativeModel(model_name)
                        pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')
                        
                        print(f"  Using streaming to get complete response...")
                        full_text_parts = []
                        
                        try:
                            response_stream = model.generate_content(
                                [
                                    full_prompt,
                                    {
                                        "mime_type": "application/pdf",
                                        "data": pdf_base64
                                    }
                                ],
                                stream=True
                            )
                            
                            for chunk in response_stream:
                                if chunk.text:
                                    full_text_parts.append(chunk.text)
                            
                            extracted_text = "".join(full_text_parts)
                            
                            if not extracted_text:
                                response = model.generate_content([
                                    full_prompt,
                                    {
                                        "mime_type": "application/pdf",
                                        "data": pdf_base64
                                    }
                                ])
                                extracted_text = response.text if response.text else ""
                        except Exception as stream_error:
                            print(f"  Streaming not available, using standard method...")
                            response = model.generate_content([
                                full_prompt,
                                {
                                    "mime_type": "application/pdf",
                                    "data": pdf_base64
                                }
                            ])
                            extracted_text = response.text if response.text else ""
                        
                        if "and so on" in extracted_text.lower() or "would exceed" in extracted_text.lower() or "demonstrates the methodology" in extracted_text.lower() or "the extraction will continue" in extracted_text.lower():
                            print(f"  ⚠ Warning: Response appears to be summarized/truncated ({len(extracted_text)} chars)")
                        else:
                            print(f"  ✓ Extracted {len(extracted_text)} characters")
                        
                        break
                    except Exception as e:
                        last_error = e
                        continue
                
                if not extracted_text:
                    raise Exception(f"All models failed. Last error: {str(last_error)}")
        
        return {
            'source_type': 'pdf',
            'source': os.path.basename(pdf_path),
            'filepath': pdf_path,
            'markdown': extracted_text,
            'status': 'success',
            'model': MODEL_NAME
        }
        
    except Exception as e:
        print(f"Error processing {pdf_path}: {str(e)}")
        return {
            'source_type': 'pdf',
            'source': os.path.basename(pdf_path),
            'filepath': pdf_path,
            'status': 'error',
            'error': str(e)
        }

def extract_text_from_docx_gemini(docx_path: str) -> Optional[Dict]:
    """Extract text from DOCX using Gemini VLM"""
    try:
        print(f"Processing DOCX: {os.path.basename(docx_path)}")
        
        # Read DOCX file
        with open(docx_path, 'rb') as docx_file:
            docx_data = docx_file.read()
        
        # Create prompt for text extraction
        prompt = """Extract ALL text content from this Word document. Do NOT summarize, do NOT skip any content, do NOT use placeholders like "(...and so on)".

CRITICAL REQUIREMENTS:
1. Extract EVERY word, sentence, paragraph, and section from the document
2. Include ALL tables, lists, and structured data in full detail
3. Preserve the complete structure (headings, paragraphs, lists, tables)
4. Maintain the logical flow and organization
5. Use # for main headings, ## for subheadings, ### for sub-subheadings
6. Extract tables as complete markdown tables with ALL rows and columns
7. Include ALL metadata (title, author, date, etc.)
8. Do NOT abbreviate, do NOT summarize, do NOT skip any content
9. If there are appendices, tables, or long sections, extract them COMPLETELY

SPECIAL INSTRUCTIONS FOR CHARTS, GRAPHS, AND VISUALIZATIONS:
- When you encounter charts, graphs, bar charts, pie charts, line graphs, or any visual data representations:
  * Extract ALL numerical values, percentages, and statistics shown in the chart
  * List ALL categories, labels, and data points
  * Describe the exact values for each element (e.g., "Egypt: 65%, Turkey: 72%, KSA: 68%")
  * Include ALL comparisons and relationships shown
  * Do NOT just say "the document includes charts" - extract the actual data
  * Convert visual data into structured text format with specific numbers
  * If there are multiple charts, extract data from EACH one completely

Example format for charts:
### Chart Title
- Category 1: [exact value/percentage]
- Category 2: [exact value/percentage]
- Category 3: [exact value/percentage]
[All comparisons and relationships]

Return the COMPLETE extracted content in clean markdown format suitable for a conversational chatbot training dataset. Every piece of text and all data from visualizations must be included."""

        # Use new or old API
        if USE_NEW_API:
            # New API - google.genai - use base64 format
            docx_base64 = base64.b64encode(docx_data).decode('utf-8')
            try:
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=[prompt, {"mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "data": docx_base64}]
                )
                extracted_text = str(response.text) if response.text else ""
            except Exception as e:
                # If that doesn't work, try file upload approach
                try:
                    uploaded_file = client.files.upload(path=docx_path)
                    response = client.models.generate_content(
                        model=MODEL_NAME,
                        contents=[prompt, uploaded_file]
                    )
                    extracted_text = str(response.text) if response.text else ""
                    client.files.delete(name=uploaded_file.name)
                except:
                    raise e
        else:
            # Old API - google.generativeai
            model = genai.GenerativeModel(MODEL_NAME)
            docx_base64 = base64.b64encode(docx_data).decode('utf-8')
            response = model.generate_content([
                prompt,
                {
                    "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "data": docx_base64
                }
            ])
            extracted_text = response.text if response.text else ""
        
        return {
            'source_type': 'docx',
            'source': os.path.basename(docx_path),
            'filepath': docx_path,
            'markdown': extracted_text,
            'status': 'success',
            'model': MODEL_NAME
        }
        
    except Exception as e:
        print(f"Error processing {docx_path}: {str(e)}")
        return {
            'source_type': 'docx',
            'source': os.path.basename(docx_path),
            'filepath': docx_path,
            'status': 'error',
            'error': str(e)
        }

def process_all_local_documents(directory_path: str = "data") -> List[Dict]:
    """Process all PDF and DOCX files in a directory"""
    pdf_files = list(Path(directory_path).glob("*.pdf"))
    docx_files = list(Path(directory_path).glob("*.docx"))
    doc_files = list(Path(directory_path).glob("*.doc"))
    
    all_files = pdf_files + docx_files + doc_files
    results = []
    
    print(f"Found {len(pdf_files)} PDF files, {len(docx_files)} DOCX files, {len(doc_files)} DOC files")
    
    # Create markdown output directory
    markdown_output_dir = 'markdown_output'
    os.makedirs(markdown_output_dir, exist_ok=True)
    
    for i, doc_file in enumerate(all_files[5:], 6):
        print(f"\n[{i}/{len(all_files)}] Processing: {doc_file.name}")
        
        file_ext = doc_file.suffix.lower()
        if file_ext == '.pdf':
            result = extract_text_from_pdf_gemini(str(doc_file))
        elif file_ext in ['.docx', '.doc']:
            result = extract_text_from_docx_gemini(str(doc_file))
        else:
            continue
            
        if result:
            results.append(result)
            
            # Save markdown immediately if successful
            if result.get('status') == 'success' and 'markdown' in result:
                # Create safe filename
                source_name = result['source'].replace('.pdf', '').replace('.docx', '').replace('.doc', '')
                source_name = ''.join(c if c.isalnum() or c in ('-', '_', '.', ' ') else '_' for c in source_name)
                source_name = source_name[:100]  # Limit length
                
                filename = f"{result['source_type']}_{source_name}.md"
                filepath = os.path.join(markdown_output_dir, filename)
                
                try:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(f"# Source: {result['source']}\n\n")
                        f.write(f"**Type:** {result['source_type']}\n\n")
                        f.write("---\n\n")
                        f.write(result['markdown'])
                    
                    print(f"  ✓ Saved markdown: {filename} ({len(result['markdown'])} chars)")
                except Exception as save_error:
                    print(f"  ⚠ Failed to save markdown: {str(save_error)}")
            else:
                # Show error if extraction failed
                error_msg = result.get('error', 'Unknown error')
                print(f"  ✗ Extraction failed: {error_msg[:100]}")
        
        # Rate limiting - Gemini API has rate limits
        if i < len(all_files):
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
    if not GEMINI_API_KEY:
        print("\n" + "=" * 70)
        print("ERROR: GEMINI_API_KEY not configured!")
        print("=" * 70)
        print("Please set your Gemini API key:")
        print("  1. Get API key from: https://aistudio.google.com/app/apikey")
        print("  2. Add to .env file: GEMINI_API_KEY=your-key-here")
        print("  3. Or set environment variable:")
        print("     PowerShell: $env:GEMINI_API_KEY='your-key-here'")
        print("     CMD: set GEMINI_API_KEY=your-key-here")
        print("     Linux/Mac: export GEMINI_API_KEY='your-key-here'")
        print("  4. Or edit the script and set GEMINI_API_KEY directly")
        exit(1)
    
    # Initialize API client after API key is confirmed
    if USE_NEW_API:
        # New API - google.genai
        client = genai.Client(api_key=GEMINI_API_KEY)
    else:
        # Old API - google.generativeai (deprecated)
        genai.configure(api_key=GEMINI_API_KEY)
        client = None  # Old API doesn't use client object
    
    all_results = []
    
    # Process all local documents (PDFs, DOCX, DOC)
    print("=" * 70)
    print("Processing local documents (PDFs, DOCX, DOC)")
    print("=" * 70)
    data_folder = "data"
    if not os.path.exists(data_folder):
        print(f"⚠ Warning: '{data_folder}' folder not found. Creating it...")
        os.makedirs(data_folder, exist_ok=True)
    
    doc_results = process_all_local_documents(data_folder)
    all_results.extend(doc_results)
    print(f"✓ Processed {len(doc_results)} document files")
    
    # Save raw results
    print("\n" + "=" * 70)
    print("Saving raw results")
    print("=" * 70)
    save_results(all_results, 'extracted_data.json')
    
    # Export markdown files
    print("\n" + "=" * 70)
    print("Exporting markdown files")
    print("=" * 70)
    export_markdown_files(all_results)
    
    # Prepare chatbot training data
    print("\n" + "=" * 70)
    print("Preparing chatbot training data")
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

