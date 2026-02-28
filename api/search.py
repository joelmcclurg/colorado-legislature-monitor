"""
Vercel serverless function: proxies bill search to leg.colorado.gov.

GET /api/search?q=food+assistance&session=2026+Regular+Session
Returns JSON array of bill results from the legislature's Turbo Stream API.
"""
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import re
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://leg.colorado.gov"
SEARCH_FORM_URL = f"{BASE_URL}/bill-search"
BILLS_SEARCH_URL = f"{BASE_URL}/bills/bill-search"


def _search_bills(query, session_name="2026 Regular Session", max_pages=5):
    """Search bills via Turbo Stream POST API."""
    # Step 1: GET search form for CSRF token + cookies
    form_resp = requests.get(SEARCH_FORM_URL, verify=False, timeout=15)
    form_resp.raise_for_status()
    soup = BeautifulSoup(form_resp.text, 'html.parser')
    token_input = soup.find('input', {'name': 'authenticity_token'})
    if not token_input:
        return []
    csrf_token = token_input['value']
    cookies = form_resp.cookies

    # Step 2: Paginate POST results
    all_bills = []
    seen = set()

    for page in range(1, max_pages + 1):
        post_data = {
            'authenticity_token': csrf_token,
            'sessions[]': session_name,
            'sort': 'Most Relevant',
            'page': str(page),
            'q': query,
        }
        resp = requests.post(
            BILLS_SEARCH_URL,
            data=post_data,
            headers={'Accept': 'text/vnd.turbo-stream.html, text/html'},
            cookies=cookies,
            verify=False,
            timeout=15
        )
        resp.raise_for_status()

        # Extract from <template> tags
        templates = re.findall(r'<template>(.*?)</template>', resp.text, re.DOTALL)
        page_bills = []

        for tmpl in templates:
            if 'bill-result' not in tmpl:
                continue
            inner = BeautifulSoup(tmpl, 'html.parser')
            for div in inner.find_all('div', class_='bill-result'):
                bill = _parse_result(div)
                if bill and bill['bill_number'] not in seen:
                    seen.add(bill['bill_number'])
                    page_bills.append(bill)

        if not page_bills:
            break
        all_bills.extend(page_bills)
        if len(page_bills) < 20:
            break

    return all_bills


def _parse_result(div):
    """Parse a single div.bill-result."""
    bill = {
        'bill_number': None,
        'title': None,
        'url': None,
        'last_action': None,
        'subjects': [],
        'sponsors': []
    }

    h2 = div.find('h2')
    if not h2:
        return None
    bill['bill_number'] = h2.get_text(strip=True).upper()

    h3 = div.find('h3')
    if h3:
        link = h3.find('a')
        if link:
            bill['title'] = link.get_text(strip=True)
            href = link.get('href', '')
            bill['url'] = f"{BASE_URL}{href}" if href.startswith('/') else href

    el = div.find('span', class_=re.compile(r'last.?action', re.I))
    if el:
        bill['last_action'] = el.get_text(strip=True)

    el = div.find('span', class_=re.compile(r'sponsor', re.I))
    if el:
        text = el.get_text(strip=True)
        if text:
            bill['sponsors'] = [s.strip() for s in text.split(',') if s.strip()]

    el = div.find('span', class_=re.compile(r'subject', re.I))
    if el:
        text = el.get_text(strip=True)
        if text:
            bill['subjects'] = [s.strip() for s in text.split(',') if s.strip()]

    return bill


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        query = params.get('q', [''])[0].strip()
        session = params.get('session', ['2026 Regular Session'])[0]

        if not query:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Missing q parameter'}).encode())
            return

        try:
            bills = _search_bills(query, session_name=session)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'public, max-age=300')
            self.end_headers()
            self.wfile.write(json.dumps(bills).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())
