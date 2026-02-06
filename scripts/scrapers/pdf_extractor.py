"""PDF content extraction for Colorado Legislature documents."""
import hashlib
import io
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from io import BytesIO
from typing import Dict, Any, List, Optional

import pdfplumber
import requests

# Suppress SSL and PDF warnings
warnings.filterwarnings('ignore', category=requests.urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore', message='Cannot set gray non-stroke color')


# Timeout for PDF downloads (seconds)
PDF_DOWNLOAD_TIMEOUT = 30

# Maximum PDF size to download (bytes) - 50MB
MAX_PDF_SIZE = 50 * 1024 * 1024

# Maximum concurrent PDF extractions
MAX_CONCURRENT_EXTRACTIONS = 3


def _url_to_cache_key(url: str) -> str:
    """
    Convert URL to a cache key.

    Args:
        url: PDF URL

    Returns:
        Cache key string
    """
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
    return f"pdf_content_{url_hash}"


def extract_pdf_text(pdf_url: str, cache_manager=None) -> Dict[str, Any]:
    """
    Extract text content from a PDF URL.

    Args:
        pdf_url: URL to the PDF file
        cache_manager: Optional cache manager for caching results

    Returns:
        Dictionary with:
            - url: Original PDF URL
            - text: Extracted text content
            - pages: Number of pages
            - extracted_at: ISO timestamp of extraction
            - error: Error message if extraction failed, None otherwise
    """
    result = {
        'url': pdf_url,
        'text': '',
        'pages': 0,
        'extracted_at': datetime.now().isoformat(),
        'error': None
    }

    # Check cache first
    if cache_manager:
        cache_key = _url_to_cache_key(pdf_url)
        cached = cache_manager.get(cache_key)
        if cached:
            return cached

    try:
        # Download PDF with timeout
        response = requests.get(
            pdf_url,
            timeout=PDF_DOWNLOAD_TIMEOUT,
            stream=True,
            verify=False  # SSL verification disabled per MEMORY.md
        )
        response.raise_for_status()

        # Check file size
        content_length = response.headers.get('content-length')
        if content_length and int(content_length) > MAX_PDF_SIZE:
            result['error'] = f"PDF too large: {int(content_length) / 1024 / 1024:.1f}MB"
            return result

        # Read content
        pdf_content = response.content

        # Extract text with pdfplumber
        raw_text = ""
        with pdfplumber.open(BytesIO(pdf_content)) as pdf:
            result['pages'] = len(pdf.pages)

            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    raw_text += text + "\n"

        result['text'] = raw_text.strip()

        # Cache result
        if cache_manager:
            cache_key = _url_to_cache_key(pdf_url)
            cache_manager.set(cache_key, result, subdirectory='pdf_content')

    except requests.exceptions.Timeout:
        result['error'] = "Download timeout"
    except requests.exceptions.RequestException as e:
        result['error'] = f"Download failed: {str(e)}"
    except Exception as e:
        result['error'] = f"Extraction failed: {str(e)}"

    return result


def batch_extract_pdfs(
    pdf_urls: List[str],
    cache_manager=None,
    progress_callback=None
) -> Dict[str, Dict[str, Any]]:
    """
    Extract text from multiple PDFs efficiently using parallel processing.

    Args:
        pdf_urls: List of PDF URLs to extract
        cache_manager: Optional cache manager for caching results
        progress_callback: Optional callback function(completed, total, url)
                          called after each PDF is processed

    Returns:
        Dictionary mapping URL -> extraction result dict
    """
    results = {}
    total = len(pdf_urls)
    completed = 0

    # Filter out already-cached URLs
    urls_to_fetch = []
    if cache_manager:
        for url in pdf_urls:
            cache_key = _url_to_cache_key(url)
            cached = cache_manager.get(cache_key)
            if cached:
                results[url] = cached
                completed += 1
                if progress_callback:
                    progress_callback(completed, total, url, from_cache=True)
            else:
                urls_to_fetch.append(url)
    else:
        urls_to_fetch = pdf_urls

    # Extract remaining PDFs in parallel
    if urls_to_fetch:
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_EXTRACTIONS) as executor:
            # Submit all extraction tasks
            future_to_url = {
                executor.submit(extract_pdf_text, url, cache_manager): url
                for url in urls_to_fetch
            }

            # Process results as they complete
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result()
                    results[url] = result
                    completed += 1

                    if progress_callback:
                        progress_callback(completed, total, url, from_cache=False)

                except Exception as e:
                    # Should not happen since extract_pdf_text catches exceptions
                    results[url] = {
                        'url': url,
                        'text': '',
                        'pages': 0,
                        'extracted_at': datetime.now().isoformat(),
                        'error': f"Unexpected error: {str(e)}"
                    }
                    completed += 1

                    if progress_callback:
                        progress_callback(completed, total, url, from_cache=False)

    return results


def extract_text_from_bytes(pdf_bytes: bytes) -> Dict[str, Any]:
    """
    Extract text from PDF bytes (for PDFs already downloaded).

    Args:
        pdf_bytes: PDF file content as bytes

    Returns:
        Dictionary with:
            - text: Extracted text content
            - pages: Number of pages
            - error: Error message if extraction failed, None otherwise
    """
    result = {
        'text': '',
        'pages': 0,
        'error': None
    }

    try:
        raw_text = ""
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            result['pages'] = len(pdf.pages)

            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    raw_text += text + "\n"

        result['text'] = raw_text.strip()

    except Exception as e:
        result['error'] = f"Extraction failed: {str(e)}"

    return result
