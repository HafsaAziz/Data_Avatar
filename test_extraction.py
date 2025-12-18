import os
import json
import base64
import tempfile
from pathlib import Path
from typing import Dict, Optional

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Use the old API (google.generativeai) for better compatibility with PDFs
# The new google.genai API has file upload issues
try:
    from google import generativeai as genai
    USE_NEW_API = False
    print("Using google.generativeai API (recommended for PDF processing)")
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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# Try different model names - common ones for old API
MODEL_NAME = "gemini-pro-latest"  # Based on API endpoint format
# Alternative model names to try:
# "gemini-pro-latest", "gemini-1.5-pro-latest", "gemini-1.5-pro", "gemini-pro", "gemini-1.5-flash"

if not GEMINI_API_KEY:
    print("\n" + "=" * 70)
    print("ERROR: GEMINI_API_KEY not configured!")
    print("=" * 70)
    print("Please set your Gemini API key in .env file or as environment variable")
    exit(1)

# Initialize API client
if USE_NEW_API:
    client = genai.Client(api_key=GEMINI_API_KEY)
else:
    genai.configure(api_key=GEMINI_API_KEY)
    client = None

def test_pdf_extraction(pdf_path: str):
    """Test extracting text from one PDF"""
    print("\n" + "=" * 70)
    print(f"TEST 1: Processing PDF - {os.path.basename(pdf_path)}")
    print("=" * 70)
    
    try:
        print(f"Reading PDF: {pdf_path}")
        with open(pdf_path, 'rb') as pdf_file:
            pdf_data = pdf_file.read()
        
        prompt = """Extract all text content from this PDF document. 
        
Please extract:
1. All text content preserving the structure (headings, paragraphs, lists, tables)
2. Maintain the logical flow and organization
3. Preserve important formatting markers like headings (use # for main headings, ## for subheadings)
4. Extract tables as markdown tables if possible
5. Include all metadata if available (title, author, date, etc.)

Return the extracted content in clean markdown format suitable for a conversational chatbot training dataset."""

        print("Sending to Gemini API...")
        if USE_NEW_API:
            # New API - upload file first, then use it
            try:
                print("  Uploading file to Gemini...")
                # Try uploading with file path
                try:
                    uploaded_file = client.files.upload(pdf_path)
                except TypeError:
                    # If path doesn't work, try with file data
                    uploaded_file = client.files.upload(data=pdf_data, mime_type="application/pdf")
                
                print(f"  File uploaded: {uploaded_file.name}")
                
                print("  Generating content...")
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=[prompt, uploaded_file]
                )
                extracted_text = str(response.text) if response.text else ""
                
                # Clean up uploaded file
                print("  Cleaning up uploaded file...")
                client.files.delete(name=uploaded_file.name)
            except Exception as upload_error:
                print(f"  File upload failed: {str(upload_error)}")
                print("  Note: The new google.genai API requires file upload.")
                print("  Consider using the old google.generativeai API for base64 support.")
                raise upload_error
        else:
            # Old API - use base64 directly
            # Try different model names if one fails
            model_names_to_try = ["gemini-pro-latest", "gemini-1.5-pro-latest", "gemini-1.5-pro", "gemini-pro", "gemini-1.5-flash"]
            extracted_text = ""
            last_error = None
            
            for model_name in model_names_to_try:
                try:
                    print(f"  Trying model: {model_name}")
                    model = genai.GenerativeModel(model_name)
                    pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')
                    response = model.generate_content([
                        prompt,
                        {
                            "mime_type": "application/pdf",
                            "data": pdf_base64
                        }
                    ])
                    extracted_text = response.text if response.text else ""
                    print(f"  ✓ Success with model: {model_name}")
                    break
                except Exception as e:
                    last_error = e
                    print(f"  ✗ Failed with {model_name}: {str(e)[:100]}")
                    continue
            
            if not extracted_text:
                raise Exception(f"All models failed. Last error: {str(last_error)}")
        
        print(f"✓ Success! Extracted {len(extracted_text)} characters")
        print(f"\nFirst 500 characters:")
        print("-" * 70)
        print(extracted_text[:500])
        print("-" * 70)
        
        # Save to file
        output_file = f"test_output_{os.path.basename(pdf_path).replace('.pdf', '')}.md"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# Source: {pdf_path}\n\n")
            f.write(extracted_text)
        print(f"\n✓ Saved full output to: {output_file}")
        
        return {
            'status': 'success',
            'text_length': len(extracted_text),
            'output_file': output_file
        }
        
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }


if __name__ == "__main__":
    print("=" * 70)
    print("TEST MODE: Processing One PDF Document")
    print("=" * 70)
    
    # Test with first PDF in data folder
    data_folder = "data"
    pdf_files = list(Path(data_folder).glob("*.pdf"))
    
    if not pdf_files:
        print(f"✗ No PDF files found in {data_folder} folder")
        exit(1)
    
    # Test PDF
    test_pdf = str(pdf_files[1])
    pdf_result = test_pdf_extraction(test_pdf)
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"PDF Test: {pdf_result.get('status', 'unknown')}")
    if pdf_result.get('status') == 'success':
        print(f"  - Extracted {pdf_result.get('text_length', 0)} characters")
        print(f"  - Output: {pdf_result.get('output_file', 'N/A')}")
    else:
        print(f"  - Error: {pdf_result.get('error', 'Unknown error')}")
    print("\n" + "=" * 70)

