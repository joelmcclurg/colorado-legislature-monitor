"""Budget document scraper for Colorado Legislature."""
import re
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .pdf_extractor import extract_pdf_text, batch_extract_pdfs


# Budget documents portal URL
BUDGET_PORTAL_URL = "https://content.leg.colorado.gov/content/budget"
BASE_URL = "https://content.leg.colorado.gov"


# Department name normalization mapping
# Maps common abbreviations and variations to canonical names
DEPARTMENT_ALIASES = {
    # Abbreviations
    'doc': 'corrections',
    'cdoc': 'corrections',
    'dhs': 'human services',
    'cdhs': 'human services',
    'dola': 'local affairs',
    'doe': 'education',
    'cde': 'education',
    'cdphe': 'public health and environment',
    'cdps': 'public safety',
    'dps': 'public safety',
    'dor': 'revenue',
    'cdor': 'revenue',
    'dot': 'transportation',
    'cdot': 'transportation',
    'dnr': 'natural resources',
    'cdle': 'labor and employment',
    'dle': 'labor and employment',
    'dhcpf': 'health care policy and financing',
    'hcpf': 'health care policy and financing',
    'dpa': 'personnel',
    'doa': 'administration',
    'oit': 'information technology',
    'dmva': 'military and veterans affairs',
    'dora': 'regulatory agencies',
    'cda': 'agriculture',
    'ag': 'agriculture',
    'higher ed': 'higher education',
    'jud': 'judicial',
    'leg': 'legislative',
    'gov': 'governor',
    'lt gov': 'lieutenant governor',
    'sos': 'secretary of state',
    'treas': 'treasury',
    'atty gen': 'attorney general',

    # Common variations
    'corrections': 'corrections',
    'department of corrections': 'corrections',
    'human services': 'human services',
    'department of human services': 'human services',
    'education': 'education',
    'department of education': 'education',
    'public health': 'public health and environment',
    'public health and environment': 'public health and environment',
    'health care policy': 'health care policy and financing',
    'health care policy and financing': 'health care policy and financing',
    'medicaid': 'health care policy and financing',
    'transportation': 'transportation',
    'department of transportation': 'transportation',
    'revenue': 'revenue',
    'department of revenue': 'revenue',
    'public safety': 'public safety',
    'department of public safety': 'public safety',
    'natural resources': 'natural resources',
    'department of natural resources': 'natural resources',
    'labor': 'labor and employment',
    'labor and employment': 'labor and employment',
    'higher education': 'higher education',
    'local affairs': 'local affairs',
    'department of local affairs': 'local affairs',
    'personnel': 'personnel',
    'department of personnel': 'personnel',
    'agriculture': 'agriculture',
    'department of agriculture': 'agriculture',
    'regulatory agencies': 'regulatory agencies',
    'department of regulatory agencies': 'regulatory agencies',
    'military': 'military and veterans affairs',
    'military and veterans affairs': 'military and veterans affairs',
    'judicial': 'judicial',
    'judicial department': 'judicial',
    'legislative': 'legislative',
    'legislative department': 'legislative',
    'governor': 'governor',
    "governor's office": 'governor',
    'office of the governor': 'governor',
    'lt governor': 'lieutenant governor',
    'lieutenant governor': 'lieutenant governor',
    'secretary of state': 'secretary of state',
    'treasury': 'treasury',
    'state treasury': 'treasury',
    'attorney general': 'attorney general',
}


def normalize_department(dept_name):
    """
    Normalize a department name to its canonical form.

    Args:
        dept_name: Department name (may be abbreviation or full name)

    Returns:
        str: Normalized department name in lowercase
    """
    if not dept_name:
        return None

    # Convert to lowercase and strip
    normalized = dept_name.lower().strip()

    # Remove common prefixes
    prefixes = ['department of ', 'office of ', 'office of the ', 'division of ']
    for prefix in prefixes:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]

    # Check aliases
    if normalized in DEPARTMENT_ALIASES:
        return DEPARTMENT_ALIASES[normalized]

    # Return as-is if no match found
    return normalized


def fetch_budget_documents(cache_manager=None, max_age_hours=6, extract_content=False, progress_callback=None):
    """
    Fetch all budget documents from the Colorado Legislature budget portal.

    Scrapes the budget content page for document links including:
    - Staff briefings
    - Figure setting documents
    - Budget requests
    - Decision items

    Args:
        cache_manager: Optional CacheManager for caching
        max_age_hours: Cache TTL in hours (default 6hr)
        extract_content: If True, extract PDF content for PDFs
        progress_callback: Optional callback(completed, total, url, from_cache) for progress

    Returns:
        list: List of document dicts with keys:
            - title: str (document title)
            - department: str (normalized department name)
            - doc_type: str ('briefing', 'figure_setting', 'request', 'decision', 'other')
            - url: str (full URL to document)
            - year: str (fiscal year if detected)
            - pdf_content: str (extracted text, if extract_content=True and URL is PDF)
            - pdf_pages: int (number of pages, if extract_content=True and URL is PDF)
    """
    # Determine cache key based on whether we're extracting content
    cache_key = "budget_documents_with_content" if extract_content else "budget_documents"

    # Check cache first
    if cache_manager:
        cached = cache_manager.get(cache_key, max_age_hours=max_age_hours)
        if cached:
            return cached

    try:
        response = requests.get(BUDGET_PORTAL_URL, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Warning: Could not fetch budget documents: {e}")
        return []

    documents = _parse_budget_page(response.text)

    # Extract PDF content if requested
    if extract_content and cache_manager:
        pdf_urls = [doc['url'] for doc in documents if doc['url'].lower().endswith('.pdf')]

        if pdf_urls:
            # Extract all PDFs in parallel
            extraction_results = batch_extract_pdfs(
                pdf_urls,
                cache_manager=cache_manager,
                progress_callback=progress_callback
            )

            # Add extracted content to document objects
            for doc in documents:
                if doc['url'] in extraction_results:
                    result = extraction_results[doc['url']]
                    doc['pdf_content'] = result.get('text', '')
                    doc['pdf_pages'] = result.get('pages', 0)
                    if result.get('error'):
                        doc['pdf_error'] = result['error']

    # Cache results
    if cache_manager and documents:
        cache_manager.set(cache_key, documents, subdirectory="documents")

    return documents


def _parse_budget_page(html):
    """
    Parse the budget portal HTML to extract document links.

    Args:
        html: Raw HTML from budget portal

    Returns:
        list: List of document dicts
    """
    soup = BeautifulSoup(html, 'lxml')
    documents = []

    # Find all PDF and document links
    doc_pattern = re.compile(r'\.(pdf|doc|docx|xls|xlsx)$', re.IGNORECASE)

    for link in soup.find_all('a', href=doc_pattern):
        href = link.get('href', '')
        if not href:
            continue

        # Make URL absolute
        url = urljoin(BASE_URL, href)

        # Get title from link text or filename
        title = link.get_text(strip=True)
        if not title:
            title = href.split('/')[-1]

        # Detect document type
        doc_type = _detect_document_type(title, href)

        # Extract department from title or context
        department = _extract_department_from_context(link, title)

        # Extract fiscal year if present
        year = _extract_fiscal_year(title, href)

        documents.append({
            'title': title,
            'department': department,
            'doc_type': doc_type,
            'url': url,
            'year': year
        })

    # Also look for links in content areas
    content_areas = soup.find_all(['div', 'section'], class_=re.compile(r'content|main|body', re.I))
    for area in content_areas:
        for link in area.find_all('a', href=True):
            href = link.get('href', '')

            # Skip if not a document or already processed
            if not doc_pattern.search(href):
                continue

            url = urljoin(BASE_URL, href)
            if any(d['url'] == url for d in documents):
                continue

            title = link.get_text(strip=True) or href.split('/')[-1]
            doc_type = _detect_document_type(title, href)
            department = _extract_department_from_context(link, title)
            year = _extract_fiscal_year(title, href)

            documents.append({
                'title': title,
                'department': department,
                'doc_type': doc_type,
                'url': url,
                'year': year
            })

    return documents


def _detect_document_type(title, href):
    """
    Detect the type of budget document from its title/URL.

    Args:
        title: Document title
        href: Document URL

    Returns:
        str: Document type
    """
    text = f"{title} {href}".lower()

    if 'briefing' in text or 'brief' in text:
        return 'briefing'
    elif 'figure' in text or 'setting' in text:
        return 'figure_setting'
    elif 'request' in text or 'r-' in text:
        return 'request'
    elif 'decision' in text or 'di-' in text:
        return 'decision'
    elif 'summary' in text:
        return 'summary'
    elif 'overview' in text:
        return 'overview'
    elif 'analysis' in text:
        return 'analysis'
    else:
        return 'other'


def _extract_department_from_context(link_element, title):
    """
    Extract department name from link context or title.

    Args:
        link_element: BeautifulSoup link element
        title: Document title

    Returns:
        str: Normalized department name or None
    """
    # First try to extract from title
    dept = _extract_department_from_text(title)
    if dept:
        return normalize_department(dept)

    # Look at parent elements for context
    for parent in link_element.parents:
        if parent.name in ['tr', 'li', 'div', 'section', 'article']:
            # Look for headers
            header = parent.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'b'])
            if header:
                dept = _extract_department_from_text(header.get_text())
                if dept:
                    return normalize_department(dept)

            # Look for department-like text in the parent
            parent_text = parent.get_text()
            dept = _extract_department_from_text(parent_text)
            if dept:
                return normalize_department(dept)

        # Stop at reasonable parent depth
        if parent.name in ['body', 'html']:
            break

    return None


def _extract_department_from_text(text):
    """
    Extract department name from text.

    Args:
        text: Text that may contain department reference

    Returns:
        str: Raw department name or None
    """
    if not text:
        return None

    # Pattern for "Department of X" or "Office of X"
    dept_pattern = r'(?:Department of|Office of|Division of)\s+([A-Za-z\s&]+?)(?:\s*[-–—\(,]|\s*$)'
    match = re.search(dept_pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Check for known department names
    text_lower = text.lower()
    for alias, canonical in DEPARTMENT_ALIASES.items():
        if alias in text_lower:
            return canonical

    return None


def _extract_fiscal_year(title, href):
    """
    Extract fiscal year from title or URL.

    Args:
        title: Document title
        href: Document URL

    Returns:
        str: Fiscal year (e.g., "FY 2025-26") or None
    """
    text = f"{title} {href}"

    # Pattern for fiscal year like "FY 2025-26" or "FY2025-26" or "FY 25-26"
    fy_pattern = r'FY\s*(\d{2,4})[-–]?(\d{2,4})?'
    match = re.search(fy_pattern, text, re.IGNORECASE)
    if match:
        year1 = match.group(1)
        year2 = match.group(2)
        if year2:
            return f"FY {year1}-{year2}"
        return f"FY {year1}"

    # Pattern for just year
    year_pattern = r'20\d{2}'
    match = re.search(year_pattern, text)
    if match:
        return match.group(0)

    return None


def get_briefing_for_department(dept_name, cache_manager=None):
    """
    Find the staff briefing document for a specific department.

    Args:
        dept_name: Department name (will be normalized)
        cache_manager: Optional CacheManager

    Returns:
        dict: Document dict if found, None otherwise
    """
    documents = fetch_budget_documents(cache_manager)
    normalized = normalize_department(dept_name)

    if not normalized:
        return None

    # Filter to briefings for this department
    briefings = [
        doc for doc in documents
        if doc['doc_type'] == 'briefing' and doc['department'] == normalized
    ]

    # Return most recent (first in list, assuming sorted by date)
    return briefings[0] if briefings else None


def get_documents_for_department(dept_name, doc_type=None, cache_manager=None):
    """
    Get all budget documents for a specific department.

    Args:
        dept_name: Department name (will be normalized)
        doc_type: Optional filter by document type
        cache_manager: Optional CacheManager

    Returns:
        list: List of document dicts
    """
    documents = fetch_budget_documents(cache_manager)
    normalized = normalize_department(dept_name)

    if not normalized:
        return []

    # Filter by department
    filtered = [doc for doc in documents if doc['department'] == normalized]

    # Optionally filter by type
    if doc_type:
        filtered = [doc for doc in filtered if doc['doc_type'] == doc_type]

    return filtered


def get_documents_by_type(doc_type, cache_manager=None):
    """
    Get all budget documents of a specific type.

    Args:
        doc_type: Document type ('briefing', 'figure_setting', etc.)
        cache_manager: Optional CacheManager

    Returns:
        list: List of document dicts
    """
    documents = fetch_budget_documents(cache_manager)
    return [doc for doc in documents if doc['doc_type'] == doc_type]


def list_departments(cache_manager=None):
    """
    List all departments that have budget documents.

    Args:
        cache_manager: Optional CacheManager

    Returns:
        list: Sorted list of department names
    """
    documents = fetch_budget_documents(cache_manager)
    departments = set()

    for doc in documents:
        if doc['department']:
            departments.add(doc['department'])

    return sorted(departments)


def extract_document_content(document, cache_manager=None):
    """
    Extract PDF content from a specific document.

    Args:
        document: Document dict (must have 'url' key)
        cache_manager: Optional CacheManager for caching

    Returns:
        dict: Document dict with added 'pdf_content' and 'pdf_pages' fields
    """
    if not document.get('url', '').lower().endswith('.pdf'):
        return document

    # Extract content
    result = extract_pdf_text(document['url'], cache_manager=cache_manager)

    # Add to document
    document['pdf_content'] = result.get('text', '')
    document['pdf_pages'] = result.get('pages', 0)
    if result.get('error'):
        document['pdf_error'] = result['error']

    return document
