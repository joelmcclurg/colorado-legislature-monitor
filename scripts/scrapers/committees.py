#!/usr/bin/env python3
"""
Committee scraper for Colorado Legislature.

Fetches and parses committee information from colorado.leg.gov including:
- Committee listings by type (year-round, house, senate, interim)
- Committee member lists
- Meeting schedules
- Staff contacts
"""
import re
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Any
from datetime import datetime
from .sessions import get_current_session


BASE_URL = "https://leg.colorado.gov"
COMMITTEES_URL = f"{BASE_URL}/committees"


def get_committee_types() -> Dict[str, str]:
    """
    Return mapping of committee type keys to display names.

    Returns:
        Dict mapping type keys to display names
    """
    return {
        'house': 'House Committees of Reference',
        'senate': 'Senate Committees of Reference',
        'year-round': 'Year-Round Committees',
        'interim': 'Interim Committees',
        'other': 'Other Committees'
    }


def list_committees(
    committee_type: str = 'all',
    session: Optional[str] = None,
    cache_manager=None
) -> List[Dict[str, Any]]:
    """
    List all committees of a given type for a session.

    Args:
        committee_type: Type of committee (house, senate, year-round, interim, other, session-only, all)
        session: Session code (e.g., '2026A'). Defaults to current session.
        cache_manager: Optional cache manager instance

    Returns:
        List of committee dicts with name, type, url, member_count
    """
    if not session:
        session = get_current_session()

    # Check cache
    cache_key = f"committees_list_{committee_type}_{session}"
    if cache_manager:
        cached = cache_manager.get(cache_key, max_age_hours=24)
        if cached:
            return cached

    # Fetch committees page
    url = f"{COMMITTEES_URL}"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        raise Exception(f"Failed to fetch committees page: {e}")

    soup = BeautifulSoup(response.text, 'html.parser')

    committees = []

    # Map 'session-only' to both house and senate
    if committee_type == 'session-only':
        types_to_fetch = ['house', 'senate']
    elif committee_type == 'all':
        types_to_fetch = list(get_committee_types().keys())
    else:
        types_to_fetch = [committee_type]

    for ctype in types_to_fetch:
        # Find the section for this committee type
        section_id = f"{ctype.replace('-', '_')}_committees"
        section = soup.find('h2', text=re.compile(ctype.replace('-', ' ').title(), re.I))

        if not section:
            # Try alternate approach with id
            section = soup.find(id=section_id)

        if not section:
            continue

        # Find the parent section/div that contains committee cards
        parent_section = section.find_parent('section') or section.find_parent('div')

        if not parent_section:
            parent_section = section

        # Look for committee tile links (cards) in this section
        # Pattern: /committees/SESSION/TYPE/CommitteeName
        # Try both upper and lowercase session codes
        pattern_upper = re.compile(rf'/committees/{session}/{ctype}/[A-Za-z]+', re.I)
        pattern_lower = re.compile(rf'/committees/{session.lower()}/{ctype}/[A-Za-z]+', re.I)

        # Find all links after this heading (until next heading or end)
        links = []

        # Method 1: Find committee-tile class links
        tile_links = parent_section.find_all('a', class_='committee-tile')
        for link in tile_links:
            href = link.get('href', '')
            if pattern_upper.search(href) or pattern_lower.search(href):
                links.append(link)

        # Method 2: Fallback to any matching links in the section
        if not links:
            all_links = parent_section.find_all('a', href=True)
            for link in all_links:
                href = link.get('href', '')
                if pattern_upper.search(href) or pattern_lower.search(href):
                    links.append(link)

        for link in links:
            committee_url = link.get('href')

            # Get committee name from link text or nested span
            committee_name = link.text.strip()
            if not committee_name:
                span = link.find('span')
                if span:
                    committee_name = span.text.strip()

            # Extract committee slug from URL
            slug = committee_url.split('/')[-1]

            # Avoid duplicates
            if not any(c['slug'] == slug for c in committees):
                committees.append({
                    'name': committee_name,
                    'slug': slug,
                    'type': ctype,
                    'session': session,
                    'url': f"{BASE_URL}{committee_url}" if not committee_url.startswith('http') else committee_url
                })

    # Cache result
    if cache_manager:
        cache_manager.set(cache_key, committees, subdirectory='committees')

    return committees


def get_committee_info(
    committee_slug: str,
    committee_type: Optional[str] = None,
    session: Optional[str] = None,
    cache_manager=None
) -> Optional[Dict[str, Any]]:
    """
    Fetch detailed information for a specific committee.

    Args:
        committee_slug: Committee slug (e.g., 'JointBudgetCommittee')
        committee_type: Committee type (year-round, house, senate, interim, other).
                       If None, will try to find it.
        session: Session code (e.g., '2026A'). Defaults to current session.
        cache_manager: Optional cache manager instance

    Returns:
        Dict with committee details including members, schedule, contacts
    """
    if not session:
        session = get_current_session()

    # Check cache
    cache_key = f"committee_{committee_slug}_{session}"
    if cache_manager:
        cached = cache_manager.get(cache_key, max_age_hours=24)
        if cached:
            return cached

    # If committee_type not provided, try to find it
    if not committee_type:
        all_committees = list_committees('all', session, cache_manager)
        matching = [c for c in all_committees if c['slug'].lower() == committee_slug.lower()]
        if not matching:
            return None
        committee_type = matching[0]['type']

    # Fetch committee page
    url = f"{COMMITTEES_URL}/{session}/{committee_type}/{committee_slug}"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        raise Exception(f"Failed to fetch committee page: {e}")

    soup = BeautifulSoup(response.text, 'html.parser')

    # Extract committee information
    committee_info = {
        'name': None,
        'slug': committee_slug,
        'type': committee_type,
        'session': session,
        'url': url,
        'description': None,
        'members': [],
        'schedule': [],
        'staff': [],
        'leadership': {},
        'fetched_at': datetime.now().isoformat()
    }

    # Get committee name from h1 or h2
    title = soup.find('h1') or soup.find('h2')
    if title:
        committee_info['name'] = title.text.strip()

    # Get description
    desc_section = soup.find('section', class_=re.compile(r'description|mission|jurisdiction'))
    if desc_section:
        committee_info['description'] = desc_section.text.strip()

    # Extract members
    members = _extract_members(soup)
    committee_info['members'] = members

    # Extract leadership from members
    for member in members:
        if member.get('role') in ['Chair', 'Vice Chair']:
            committee_info['leadership'][member['role'].lower().replace(' ', '_')] = member['name']

    # Extract meeting schedule
    schedule = _extract_schedule(soup, session, committee_type, committee_slug)
    committee_info['schedule'] = schedule

    # Extract staff contacts
    staff = _extract_staff(soup)
    committee_info['staff'] = staff

    # Cache result
    if cache_manager:
        cache_manager.set(cache_key, committee_info, subdirectory='committees')

    return committee_info


def _extract_members(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """
    Extract committee members from page.

    Args:
        soup: BeautifulSoup object of committee page

    Returns:
        List of member dicts with name, role, chamber, image_url, profile_url
    """
    members = []

    # Look for committee member links (newer structure)
    member_links = soup.find_all('a', class_='cm-link')

    if member_links:
        for link in member_links:
            member = {
                'name': None,
                'role': 'Member',
                'chamber': None,
                'profile_url': None,
                'image_url': None
            }

            # Extract profile URL
            href = link.get('href', '')
            if href:
                member['profile_url'] = f"{BASE_URL}{href}" if not href.startswith('http') else href

            # Extract name from p.comm-member-name
            name_elem = link.find('p', class_='comm-member-name')
            if name_elem:
                member['name'] = name_elem.text.strip()

            # Extract role from div.comm-mem-role
            role_elem = link.find('div', class_='comm-mem-role')
            if role_elem:
                role_text = role_elem.text.strip()
                member['role'] = role_text if role_text else 'Member'

            # Extract chamber from the p tag before the name
            chamber_elem = link.find('p', class_='comm-member-name')
            if chamber_elem:
                prev_p = chamber_elem.find_previous_sibling('p')
                if prev_p:
                    chamber_text = prev_p.text.strip()
                    if 'Representative' in chamber_text:
                        member['chamber'] = 'House'
                    elif 'Senator' in chamber_text:
                        member['chamber'] = 'Senate'

            # Extract image
            img = link.find('img', class_='comm-mem-picture')
            if img:
                img_src = img.get('src')
                if img_src:
                    member['image_url'] = img_src

            if member['name']:
                members.append(member)

    else:
        # Fallback: older structure - look for legislator links
        legislator_links = soup.find_all('a', href=re.compile(r'/legislators/'))

        for link in legislator_links:
            # Skip if this is in navigation or footer
            if link.find_parent('nav') or link.find_parent('footer'):
                continue

            member_name = link.text.strip()
            if not member_name or len(member_name) < 3:
                continue

            profile_url = link.get('href', '')
            if profile_url:
                profile_url = f"{BASE_URL}{profile_url}" if not profile_url.startswith('http') else profile_url

            # Try to find role nearby (Chair, Vice Chair, etc.)
            role = 'Member'
            parent = link.find_parent()
            if parent:
                text = parent.text
                if 'Chair' in text and 'Vice' not in text:
                    role = 'Chair'
                elif 'Vice Chair' in text:
                    role = 'Vice Chair'

            # Avoid duplicates
            if not any(m['name'] == member_name for m in members):
                members.append({
                    'name': member_name,
                    'role': role,
                    'chamber': None,
                    'profile_url': profile_url,
                    'image_url': None
                })

    return members


def _extract_schedule(
    soup: BeautifulSoup,
    session: str,
    committee_type: str,
    committee_slug: str
) -> List[Dict[str, Any]]:
    """
    Extract meeting schedule from committee page.

    Args:
        soup: BeautifulSoup object of committee page
        session: Session code
        committee_type: Committee type
        committee_slug: Committee slug

    Returns:
        List of meeting dicts with date, time, location, agenda_url
    """
    schedule = []

    # Look for schedule section
    schedule_section = soup.find('section', class_=re.compile(r'schedule|meetings'))
    if not schedule_section:
        # Try finding by heading
        schedule_heading = soup.find(text=re.compile(r'Schedule|Meetings|Upcoming'))
        if schedule_heading:
            schedule_section = schedule_heading.find_parent('section')

    if schedule_section:
        # Look for meeting entries
        meetings = schedule_section.find_all('div', class_=re.compile(r'meeting'))

        for meeting in meetings:
            meeting_info = {
                'date': None,
                'time': None,
                'location': None,
                'agenda_url': None
            }

            # Extract date, time, location
            # Format varies: "Mon Feb 9", "1:30 PM", "HCR 0107"
            text = meeting.text

            # Try to find date pattern
            date_match = re.search(r'([A-Z][a-z]{2})\s+([A-Z][a-z]+)\s+(\d+)', text)
            if date_match:
                meeting_info['date'] = f"{date_match.group(2)} {date_match.group(3)}"

            # Try to find time pattern
            time_match = re.search(r'(\d+):(\d+)\s*(AM|PM|am|pm)', text)
            if time_match:
                meeting_info['time'] = f"{time_match.group(1)}:{time_match.group(2)} {time_match.group(3).upper()}"

            # Try to find location (room number)
            location_match = re.search(r'([HS]CR\s+\d+)', text)
            if location_match:
                meeting_info['location'] = location_match.group(1)

            # Look for agenda link
            agenda_link = meeting.find('a', href=re.compile(r'/agenda/committee/'))
            if agenda_link:
                meeting_info['agenda_url'] = f"{BASE_URL}{agenda_link.get('href')}"

            schedule.append(meeting_info)

    return schedule


def _extract_staff(soup: BeautifulSoup) -> List[Dict[str, str]]:
    """
    Extract staff contact information.

    Args:
        soup: BeautifulSoup object of committee page

    Returns:
        List of staff dicts with name, email, phone
    """
    staff = []

    # Look for staff/contact section
    staff_section = soup.find('section', class_=re.compile(r'staff|contact'))
    if not staff_section:
        # Try finding by heading
        staff_heading = soup.find(text=re.compile(r'Staff|Contact Us'))
        if staff_heading:
            staff_section = staff_heading.find_parent('section') or staff_heading.find_parent('div')

    if not staff_section:
        # Fallback to whole page
        staff_section = soup

    # Look for mailto and tel links within staff section
    email_links = staff_section.find_all('a', href=re.compile(r'^mailto:'))
    phone_links = staff_section.find_all('a', href=re.compile(r'^tel:'))

    # Extract emails (filter out share links)
    for link in email_links:
        email = link.get('href').replace('mailto:', '')

        # Skip if this is a share/social link (contains ?body= or ?subject=)
        if '?body=' in email or '?subject=' in email:
            continue

        # Skip generic/navigation emails
        if email in ['', 'info@']:
            continue

        # Try to find associated name
        name = link.text.strip() if link.text else None

        # If name is just "Email:" or similar, look for actual name nearby
        if name and ('email' in name.lower() or '@' in name):
            parent = link.find_parent()
            if parent:
                # Look for text before the link
                text_parts = parent.get_text().split(email)[0].strip()
                if text_parts and len(text_parts) < 50:
                    name = text_parts

        # Avoid duplicate entries
        if not any(s.get('email') == email for s in staff):
            staff.append({
                'name': name if name and name.lower() != 'email:' else None,
                'email': email,
                'phone': None
            })

    # Extract phones
    for link in phone_links:
        phone = link.get('href').replace('tel:', '')

        # Format phone number nicely (###-###-####)
        phone_digits = re.sub(r'\D', '', phone)
        if len(phone_digits) == 10:
            phone = f"{phone_digits[:3]}-{phone_digits[3:6]}-{phone_digits[6:]}"

        # Try to find associated email or name nearby
        parent = link.find_parent()
        associated_email = None
        if parent:
            # Look for email in same parent
            email_link = parent.find('a', href=re.compile(r'^mailto:'))
            if email_link:
                associated_email = email_link.get('href').replace('mailto:', '')
                # Skip share links
                if '?body=' in associated_email or '?subject=' in associated_email:
                    associated_email = None

        if associated_email:
            # Add phone to existing staff entry
            staff_entry = next((s for s in staff if s.get('email') == associated_email), None)
            if staff_entry:
                staff_entry['phone'] = phone
            else:
                staff.append({
                    'name': None,
                    'email': associated_email,
                    'phone': phone
                })
        else:
            # Check if we already have this phone
            if not any(s.get('phone') == phone for s in staff):
                staff.append({
                    'name': None,
                    'email': None,
                    'phone': phone
                })

    return staff


def _infer_chamber(name: str, profile_url: str) -> Optional[str]:
    """
    Infer chamber (House/Senate) from context.

    Args:
        name: Member name
        profile_url: URL to member profile

    Returns:
        'House' or 'Senate' or None
    """
    # Could be enhanced by fetching profile page
    # For now, return None
    return None


def search_committees(
    query: str,
    committee_type: str = 'all',
    session: Optional[str] = None,
    cache_manager=None
) -> List[Dict[str, Any]]:
    """
    Search for committees matching a query.

    Args:
        query: Search query (matches committee name)
        committee_type: Type filter
        session: Session code
        cache_manager: Optional cache manager

    Returns:
        List of matching committee dicts
    """
    all_committees = list_committees(committee_type, session, cache_manager)

    query_lower = query.lower()
    matches = [
        c for c in all_committees
        if query_lower in c['name'].lower() or query_lower in c['slug'].lower()
    ]

    return matches
