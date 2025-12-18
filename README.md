# Data Preparation for Conversational Chatbot

This project extracts content from PDF documents and web pages to prepare training data for a conversational chatbot using Google's Gemini Vision Language Model (VLM).

## Features

- ✅ Extract text from local PDF files using Gemini VLM
- ✅ Extract text from DOCX/DOC files using Gemini VLM
- ✅ Scrape content from web URLs
- ✅ Export to Markdown format (preserves document structure)
- ✅ Export to JSON format for programmatic use
- ✅ Prepare training data chunks for chatbot
- ✅ Handle both PDFs and HTML/web pages

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Get your Gemini API key:
   - Visit: https://makersuite.google.com/app/apikey
   - Create a new API key
   - Set it as an environment variable:
     ```bash
     # Windows PowerShell
     $env:GEMINI_API_KEY="your-api-key-here"
     
     # Windows CMD
     set GEMINI_API_KEY=your-api-key-here
     
     # Linux/Mac
     export GEMINI_API_KEY="your-api-key-here"
     ```
   - Or edit `extract_data_gemini.py` and set `GEMINI_API_KEY` directly (not recommended)

## Scripts

- **`extract_data_gemini.py`** - Main script using Google Gemini VLM (recommended)
- **`extract_data.py`** - Alternative script using Docling (if you prefer that approach)

## Usage

### Step 1: Organize Documents

Place all your PDF, DOCX, and DOC files in the `data/` folder. The script will automatically process all documents in this folder.

### Step 2: Prepare URLs (Optional)

If you have web URLs to scrape, add them to `urls.txt` (one URL per line):
```
https://example.com/page1
https://example.com/page2
```

### Step 3: Run the Extraction Script

```bash
python extract_data_gemini.py
```

The script will:
1. Process all PDF, DOCX, and DOC files in the `data/` folder using Gemini VLM
2. Process all URLs from `urls.txt` (if it exists)
3. Save extracted data to `extracted_data.json`
4. Export individual markdown files to `markdown_output/` folder
5. Create `chatbot_training_data.json` with formatted chunks

**Note:** The script includes rate limiting (2-3 seconds between requests) to respect API limits. Processing many documents may take some time.

## Output Files

- **extracted_data.json**: Raw extracted data with markdown and JSON formats
- **chatbot_training_data.json**: Formatted data chunks ready for chatbot training
- **markdown_output/**: Individual markdown files for each source

## Data Format

Each entry in `chatbot_training_data.json` contains:
```json
{
  "id": "unique_id",
  "source_type": "pdf|web|pdf_url",
  "source": "filename or URL",
  "chunk_index": 0,
  "text": "extracted content chunk",
  "metadata": {
    "source": "source identifier",
    "source_type": "type of source"
  }
}
```

## Notes

- Uses Google Gemini 1.5 Pro model for document extraction (supports vision capabilities)
- The script includes rate limiting (2-3 seconds between requests) to respect API limits
- Failed extractions are logged with error messages
- Long documents are automatically split into chunks (max 2000 characters) with overlap for context
- Markdown format preserves document structure (headings, tables, lists, etc.)
- Gemini API has usage limits - check your quota at Google Cloud Console

## Troubleshooting

- **API Key Error**: Make sure `GEMINI_API_KEY` is set correctly
- **Rate Limit Errors**: The script includes delays, but you may need to increase them for high-volume processing
- **PDF Extraction Fails**: Check if PDF is corrupted or too large (Gemini has file size limits)
- **URL Scraping Fails**: Verify URL is accessible and not behind authentication
- **Token Limits**: Very large documents may exceed token limits - consider splitting them manually

## API Costs

- Gemini API usage may incur costs depending on your Google Cloud plan
- Check pricing at: https://ai.google.dev/pricing
- Consider using `gemini-2.0-flash-exp` model for faster/cheaper processing (change `MODEL_NAME` in script)

