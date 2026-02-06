"""Markdown formatters for Colorado Legislature data."""
from datetime import datetime


def format_schedule(schedule_data, include_media=True, include_docs=True):
    """
    Format schedule data as markdown.

    Args:
        schedule_data: Dict from schedules.py with meetings list
        include_media: Whether to include Media column
        include_docs: Whether to include Documents column

    Returns:
        str: Markdown-formatted schedule
    """
    if not schedule_data:
        return "No schedule data available."

    output = []

    # Header with week info
    week_num = schedule_data.get('week_number', '?')
    week_start = schedule_data.get('week_start', '')
    week_end = schedule_data.get('week_end', '')

    if week_start and week_end:
        try:
            start_obj = datetime.strptime(week_start, '%Y-%m-%d')
            end_obj = datetime.strptime(week_end, '%Y-%m-%d')
            date_range = f"{start_obj.strftime('%b %d')} - {end_obj.strftime('%b %d, %Y')}"
            output.append(f"# JBC Schedule - Week {week_num} ({date_range})")
        except:
            output.append(f"# JBC Schedule - Week {week_num}")
    else:
        output.append(f"# JBC Schedule - Week {week_num}")

    output.append("")

    meetings = schedule_data.get('meetings', [])

    if not meetings:
        output.append("No meetings scheduled for this week.")
        output.append("")
    else:
        # Group meetings by date
        meetings_by_date = {}
        for meeting in meetings:
            date = meeting.get('date', 'TBD')
            if date not in meetings_by_date:
                meetings_by_date[date] = []
            meetings_by_date[date].append(meeting)

        # Output meetings by date
        for date in sorted(meetings_by_date.keys()):
            # Format date nicely
            try:
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                formatted_date = date_obj.strftime('%A, %B %d')
            except:
                formatted_date = date

            output.append(f"## {formatted_date}")
            output.append("")

            date_meetings = meetings_by_date[date]

            # Check if the only item is a "Will Not Meet" notice
            if len(date_meetings) == 1 and date_meetings[0].get('is_cancelled'):
                output.append(f"*{date_meetings[0].get('topic', 'No meetings')}*")
                output.append("")
                continue

            # Build table header based on what columns to include
            header = "| Time | Topic"
            separator = "|------|-------"
            if include_media:
                header += " | Media"
                separator += "|-------"
            if include_docs:
                header += " | Documents"
                separator += "|-----------"
            header += " |"
            separator += "|"

            output.append(header)
            output.append(separator)

            for meeting in date_meetings:
                if meeting.get('is_cancelled'):
                    row = f"| — | *{meeting.get('topic', 'Cancelled')}*"
                    if include_media:
                        row += " | —"
                    if include_docs:
                        row += " | —"
                    row += " |"
                    output.append(row)
                else:
                    time = meeting.get('time', 'TBD')
                    topic = meeting.get('topic', 'No topic')
                    # Escape pipe characters in topic
                    topic = topic.replace('|', '\\|')
                    # Add department info if different from topic
                    dept = meeting.get('department')
                    if dept and dept not in topic:
                        topic = f"{topic} ({dept})"

                    row = f"| {time} | {topic}"

                    # Add media column
                    if include_media:
                        media_cell = _format_media_cell(meeting)
                        row += f" | {media_cell}"

                    # Add documents column
                    if include_docs:
                        docs_cell = _format_docs_cell(meeting)
                        row += f" | {docs_cell}"

                    row += " |"
                    output.append(row)

            output.append("")

    # Add metadata
    output.append("---")
    revision = schedule_data.get('revision')
    if revision:
        output.append(f"**Schedule Revision:** {revision}")
    output.append(f"**Source:** {schedule_data.get('source_url', 'N/A')}")
    output.append(f"**Fetched:** {schedule_data.get('fetched_at', 'N/A')}")

    return "\n".join(output)


def _format_media_cell(meeting):
    """
    Format the Media cell for a meeting.

    Args:
        meeting: Meeting dict with optional video_url and media_status

    Returns:
        str: Formatted cell content
    """
    video_url = meeting.get('video_url')
    media_status = meeting.get('media_status', 'unavailable')

    if video_url:
        return f"[Video]({video_url})"
    elif media_status == 'pending':
        return "*Pending*"
    else:
        return "*--*"


def _format_docs_cell(meeting):
    """
    Format the Documents cell for a meeting.

    Args:
        meeting: Meeting dict with optional document_url and document_title

    Returns:
        str: Formatted cell content
    """
    doc_url = meeting.get('document_url')
    doc_title = meeting.get('document_title')

    if doc_url:
        # Use "Brief" as the link text, or a shortened title
        link_text = "Brief"
        if doc_title and len(doc_title) < 20:
            link_text = doc_title
        return f"[{link_text}]({doc_url})"
    else:
        return "*--*"


def format_committee_info(committee_data):
    """
    Format committee information as markdown.

    Args:
        committee_data: Dict with committee details from committees.py scraper

    Returns:
        str: Markdown-formatted committee info
    """
    output = []

    # Header
    name = committee_data.get('name', 'Committee')
    committee_type = committee_data.get('type', '').replace('-', ' ').title()
    output.append(f"# {name}")
    output.append("")
    output.append(f"**Type:** {committee_type}")
    output.append(f"**Session:** {committee_data.get('session', 'Unknown')}")
    output.append("")

    # Description
    if committee_data.get('description'):
        output.append("## Description")
        output.append("")
        output.append(committee_data['description'])
        output.append("")

    # Leadership
    leadership = committee_data.get('leadership', {})
    if leadership:
        output.append("## Leadership")
        output.append("")
        if leadership.get('chair'):
            output.append(f"**Chair:** {leadership['chair']}")
        if leadership.get('vice_chair'):
            output.append(f"**Vice Chair:** {leadership['vice_chair']}")
        output.append("")

    # Members
    members = committee_data.get('members', [])
    if members:
        output.append(f"## Members ({len(members)})")
        output.append("")

        # Separate by role
        chairs = [m for m in members if 'Chair' in m.get('role', '')]
        regular = [m for m in members if 'Chair' not in m.get('role', '')]

        # Show leadership first
        for member in chairs:
            role = member.get('role', 'Member')
            name = member.get('name', 'Unknown')
            profile_url = member.get('profile_url')

            if profile_url:
                output.append(f"- **{role}:** [{name}]({profile_url})")
            else:
                output.append(f"- **{role}:** {name}")

        # Then regular members
        for member in regular:
            name = member.get('name', 'Unknown')
            profile_url = member.get('profile_url')

            if profile_url:
                output.append(f"- [{name}]({profile_url})")
            else:
                output.append(f"- {name}")

        output.append("")

    # Meeting Schedule
    schedule = committee_data.get('schedule', [])
    if schedule:
        output.append("## Upcoming Meetings")
        output.append("")
        output.append("| Date | Time | Location | Agenda |")
        output.append("|------|------|----------|--------|")

        for meeting in schedule[:5]:  # Show up to 5 upcoming
            date = meeting.get('date', 'TBD')
            time = meeting.get('time', 'TBD')
            location = meeting.get('location', 'TBD')
            agenda_url = meeting.get('agenda_url')

            if agenda_url:
                output.append(f"| {date} | {time} | {location} | [View]({agenda_url}) |")
            else:
                output.append(f"| {date} | {time} | {location} | — |")

        output.append("")

    # Staff Contacts
    staff = committee_data.get('staff', [])
    if staff:
        output.append("## Staff Contacts")
        output.append("")

        for person in staff:
            name = person.get('name', 'Staff')
            email = person.get('email')
            phone = person.get('phone')

            if name and name != 'Staff':
                output.append(f"**{name}**")

            if email:
                output.append(f"- Email: {email}")
            if phone:
                output.append(f"- Phone: {phone}")

            if not email and not phone and not name:
                continue

            output.append("")

    # Metadata
    output.append("---")
    output.append(f"**URL:** {committee_data.get('url', 'N/A')}")
    output.append(f"**Fetched:** {committee_data.get('fetched_at', 'N/A')}")

    return "\n".join(output)


def format_committees_list(committees):
    """
    Format a list of committees as markdown table.

    Args:
        committees: List of committee summary dicts

    Returns:
        str: Markdown-formatted committees table
    """
    output = []

    if not committees:
        output.append("No committees found.")
        return "\n".join(output)

    # Group by type
    by_type = {}
    for comm in committees:
        ctype = comm.get('type', 'other')
        if ctype not in by_type:
            by_type[ctype] = []
        by_type[ctype].append(comm)

    # Display each type
    type_names = {
        'house': 'House Committees of Reference',
        'senate': 'Senate Committees of Reference',
        'year-round': 'Year-Round Committees',
        'interim': 'Interim Committees',
        'other': 'Other Committees'
    }

    for ctype, type_committees in sorted(by_type.items()):
        type_name = type_names.get(ctype, ctype.title())
        output.append(f"## {type_name} ({len(type_committees)})")
        output.append("")

        for comm in sorted(type_committees, key=lambda c: c.get('name', '')):
            name = comm.get('name', 'Unknown')
            slug = comm.get('slug', '')
            output.append(f"- {name} (`{slug}`)")

        output.append("")

    output.append(f"*Total: {len(committees)} committee(s)*")

    return "\n".join(output)


def format_search_results(results):
    """
    Format search results as markdown.

    Args:
        results: List of search result dicts

    Returns:
        str: Markdown-formatted search results
    """
    if not results:
        return "No results found."

    output = []
    output.append(f"# Search Results ({len(results)} found)")
    output.append("")

    for i, result in enumerate(results, 1):
        output.append(f"## {i}. {result.get('title', 'Untitled')}")
        output.append("")

        if result.get('date'):
            output.append(f"**Date:** {result['date']}")
        if result.get('committee'):
            output.append(f"**Committee:** {result['committee']}")
        if result.get('excerpt'):
            output.append("")
            output.append(result['excerpt'])
        if result.get('url'):
            output.append("")
            output.append(f"[View details]({result['url']})")

        output.append("")
        output.append("---")
        output.append("")

    return "\n".join(output)


def format_recordings_list(recordings, cache_manager=None, committee_filter=None):
    """
    Format a list of SLIQ committee recordings as markdown.

    Shows recordings across committees with transcription status.

    Args:
        recordings: List of recording dicts from sliq.py
        cache_manager: Optional CacheManager to check transcription status
        committee_filter: Optional committee code to show in header

    Returns:
        str: Markdown-formatted recordings list
    """
    output = []

    if committee_filter:
        # Try to get human-readable name
        try:
            from scrapers.sliq import PRIORITY_COMMITTEES
            name = PRIORITY_COMMITTEES.get(committee_filter, {}).get('name', committee_filter)
        except ImportError:
            name = committee_filter
        output.append(f"# Recordings - {name}")
    else:
        output.append("# Committee Recordings")

    output.append("")

    if not recordings:
        output.append("No recordings found.")
        return "\n".join(output)

    # Check which recordings are transcribed
    transcribed_ids = set()
    if cache_manager:
        for key in cache_manager.metadata.keys():
            if key.startswith('transcript_'):
                clip_id = key[len('transcript_'):]
                transcript = cache_manager.get(key, max_age_hours=None)
                if transcript and not transcript.get('error'):
                    transcribed_ids.add(clip_id)

    output.append("| Date | Committee | Title | Duration | Transcribed |")
    output.append("|------|-----------|-------|----------|-------------|")

    for rec in recordings:
        date = rec.get('date', 'Unknown')
        try:
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            date = date_obj.strftime('%b %d, %Y')
        except (ValueError, TypeError):
            pass

        committee_name = rec.get('committee_name', '')
        # Shorten committee names for table
        short_names = {
            'Joint Budget Committee': 'JBC',
            'House Health & Human Services': 'House H&HS',
            'Senate Health & Human Services': 'Senate H&HS',
            'Joint Technology Committee': 'Joint Tech',
            'House Agriculture, Water & Natural Resources': 'House Ag/Water',
            'Senate Agriculture & Natural Resources': 'Senate Ag/NR',
        }
        committee_short = short_names.get(committee_name, committee_name)

        title = rec.get('title', 'Meeting')
        if len(title) > 35:
            title = title[:32] + "..."
        title = title.replace('|', '\\|')

        duration = rec.get('duration') or '---'
        clip_id = rec.get('clip_id', '')
        is_transcribed = 'Yes' if clip_id in transcribed_ids else 'No'

        output.append(f"| {date} | {committee_short} | {title} | {duration} | {is_transcribed} |")

    output.append("")
    transcribed_count = sum(1 for r in recordings if r.get('clip_id', '') in transcribed_ids)
    output.append(f"*{len(recordings)} recording(s), {transcribed_count} transcribed*")

    return "\n".join(output)


def format_recordings(recordings, week_number=None, date_str=None):
    """
    Format a list of recordings as markdown.

    Args:
        recordings: List of recording dicts from audio scraper
        week_number: Optional week number for header
        date_str: Optional specific date for header

    Returns:
        str: Markdown-formatted recordings list
    """
    output = []

    # Header
    if date_str:
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            output.append(f"# JBC Recordings for {date_obj.strftime('%B %d, %Y')}")
        except:
            output.append(f"# JBC Recordings for {date_str}")
    elif week_number:
        output.append(f"# JBC Recordings - Week {week_number}")
    else:
        output.append("# JBC Recordings")

    output.append("")

    if not recordings:
        output.append("No recordings found.")
        return "\n".join(output)

    # Table
    output.append("| Date | Title | Duration | Link |")
    output.append("|------|-------|----------|------|")

    for rec in recordings:
        date = rec.get('date', 'Unknown')
        try:
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            date = date_obj.strftime('%b %d, %Y')
        except:
            pass

        title = rec.get('title', 'JBC Meeting')
        # Truncate long titles
        if len(title) > 40:
            title = title[:37] + "..."
        # Escape pipes
        title = title.replace('|', '\\|')

        duration = rec.get('duration') or '—'
        video_url = rec.get('video_url', '')

        if video_url:
            output.append(f"| {date} | {title} | {duration} | [Watch]({video_url}) |")
        else:
            output.append(f"| {date} | {title} | {duration} | — |")

    output.append("")
    output.append(f"*{len(recordings)} recording(s) found*")

    return "\n".join(output)


def format_documents(documents, department=None, doc_type=None):
    """
    Format a list of budget documents as markdown.

    Args:
        documents: List of document dicts from documents scraper
        department: Optional department filter for header
        doc_type: Optional doc type filter for header

    Returns:
        str: Markdown-formatted documents list
    """
    output = []

    # Header
    if department:
        output.append(f"# Budget Documents - {department.title()}")
    elif doc_type:
        output.append(f"# Budget Documents - {doc_type.replace('_', ' ').title()}")
    else:
        output.append("# Budget Documents")

    output.append("")

    if not documents:
        output.append("No documents found.")
        return "\n".join(output)

    # Group by type if not filtered
    if not doc_type:
        docs_by_type = {}
        for doc in documents:
            dtype = doc.get('doc_type', 'other')
            if dtype not in docs_by_type:
                docs_by_type[dtype] = []
            docs_by_type[dtype].append(doc)

        for dtype in sorted(docs_by_type.keys()):
            type_docs = docs_by_type[dtype]
            output.append(f"## {dtype.replace('_', ' ').title()}")
            output.append("")
            output.append("| Department | Title | Year | Link |")
            output.append("|------------|-------|------|------|")

            for doc in type_docs:
                dept = doc.get('department', '—')
                if dept:
                    dept = dept.title()
                title = doc.get('title', 'Untitled')
                if len(title) > 35:
                    title = title[:32] + "..."
                title = title.replace('|', '\\|')
                year = doc.get('year') or '—'
                url = doc.get('url', '')

                if url:
                    output.append(f"| {dept} | {title} | {year} | [Download]({url}) |")
                else:
                    output.append(f"| {dept} | {title} | {year} | — |")

            output.append("")
    else:
        # Simple table for filtered results
        output.append("| Department | Title | Year | Link |")
        output.append("|------------|-------|------|------|")

        for doc in documents:
            dept = doc.get('department', '—')
            if dept:
                dept = dept.title()
            title = doc.get('title', 'Untitled')
            if len(title) > 35:
                title = title[:32] + "..."
            title = title.replace('|', '\\|')
            year = doc.get('year') or '—'
            url = doc.get('url', '')

            if url:
                output.append(f"| {dept} | {title} | {year} | [Download]({url}) |")
            else:
                output.append(f"| {dept} | {title} | {year} | — |")

        output.append("")

    output.append(f"*{len(documents)} document(s) found*")

    return "\n".join(output)


def format_error(error_message):
    """
    Format an error message as markdown.

    Args:
        error_message: Error message string

    Returns:
        str: Markdown-formatted error
    """
    output = []
    output.append("# Error")
    output.append("")
    output.append(f"```")
    output.append(error_message)
    output.append("```")
    output.append("")
    output.append("Please try again or contact support if the issue persists.")

    return "\n".join(output)


def format_search_results_full(results, query):
    """
    Format search results as markdown, grouped by type with highlights.

    Args:
        results: Results dict from search_all with keys:
            - query: str
            - schedules: list
            - recordings: list
            - documents: list
            - total_count: int
        query: Original query string

    Returns:
        str: Markdown-formatted search results
    """
    output = []
    total = results.get('total_count', 0)

    output.append(f"# Search Results for \"{query}\"")
    output.append("")

    if total == 0:
        output.append("No results found.")
        return "\n".join(output)

    # Count by type
    schedule_count = len(results.get('schedules', []))
    recording_count = len(results.get('recordings', []))
    document_count = len(results.get('documents', []))

    output.append(f"Found **{total}** matches across {_count_data_types(results)} data type(s).")
    output.append("")

    # Bills section
    bills = results.get('bills', [])
    if bills:
        bill_count = len(bills)
        output.append(f"## Bills ({bill_count} match{'es' if bill_count != 1 else ''})")
        output.append("")
        output.append("| Bill # | Title | Sponsors | Match |")
        output.append("|--------|-------|----------|-------|")

        for item in bills:
            bill_num = item.get('bill_number', '—')
            title = item.get('title', '—')
            # Escape pipes but preserve bold markers
            title = title.replace('|', '\\|')
            if len(title) > 45:
                title = title[:42] + "..."

            sponsors = item.get('sponsors', [])
            sponsors_str = ', '.join(sponsors[:2]) if sponsors else '—'
            if len(sponsors) > 2:
                sponsors_str += f" (+{len(sponsors) - 2})"

            # Match location indicator
            match_location = item.get('match_location', 'title')
            if match_location == 'bill_text':
                match_str = f"Bill Text ({item.get('match_version', '')})"
            elif match_location == 'amendment':
                match_str = f"Amendment {item.get('match_amendment', '')}"
            elif match_location == 'fiscal_note':
                match_str = "Fiscal Note"
            else:
                match_str = "Title"

            # Add "NEW" indicator if present
            if item.get('is_new'):
                title = f"*NEW* {title}"

            url = item.get('url', '')
            if url:
                output.append(f"| [{bill_num}]({url}) | {title} | {sponsors_str} | {match_str} |")
            else:
                output.append(f"| {bill_num} | {title} | {sponsors_str} | {match_str} |")

        output.append("")

        # Show content contexts for bill matches
        bills_with_context = [b for b in bills if b.get('match_context') and b.get('match_location') != 'title']
        if bills_with_context:
            output.append("### Bill Content Matches")
            output.append("")
            for item in bills_with_context[:5]:  # Show first 5 with context
                bill_num = item.get('bill_number', '—')
                match_location = item.get('match_location', '')
                contexts = item.get('match_context', [])
                if isinstance(contexts, list) and contexts:
                    output.append(f"**{bill_num}** ({match_location}):")
                    for context in contexts[:2]:  # Show first 2 contexts per bill
                        output.append(f"> {context}")
                    output.append("")
            output.append("")

    # Schedules section
    schedules = results.get('schedules', [])
    if schedules:
        output.append(f"## Schedules ({schedule_count} match{'es' if schedule_count != 1 else ''})")
        output.append("")
        output.append("| Date | Time | Topic | Week |")
        output.append("|------|------|-------|------|")

        for item in schedules:
            date = item.get('date', '—')
            try:
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                date = date_obj.strftime('%b %d, %Y')
            except:
                pass

            time = item.get('time', '—')
            topic = item.get('topic', '—')
            # Escape pipes but preserve bold markers
            topic = topic.replace('|', '\\|')
            week = item.get('week_number', '—')

            # Add "NEW" indicator if present
            if item.get('is_new'):
                topic = f"*NEW* {topic}"

            output.append(f"| {date} | {time} | {topic} | Week {week} |")

        output.append("")

    # Documents section
    documents = results.get('documents', [])
    if documents:
        output.append(f"## Documents ({document_count} match{'es' if document_count != 1 else ''})")
        output.append("")
        output.append("| Department | Title | Type | Match |")
        output.append("|------------|-------|------|-------|")

        for item in documents:
            dept = item.get('department') or '—'
            if dept and dept != '—':
                dept = dept.replace('**', '').title()  # Clean up for display
            title = item.get('title', '—')
            title = title.replace('|', '\\|')
            if len(title) > 40:
                title = title[:37] + "..."
            doc_type = item.get('doc_type', '—')
            if doc_type:
                doc_type = doc_type.replace('_', ' ').title()

            # Match location
            match_location = item.get('match_location', 'title')
            if match_location == 'pdf_content':
                pdf_pages = item.get('pdf_pages', 0)
                match_str = f"PDF Content ({pdf_pages}p)"
            else:
                match_str = "Title"

            # Add "NEW" indicator if present
            if item.get('is_new'):
                title = f"*NEW* {title}"

            output.append(f"| {dept} | {title} | {doc_type} | {match_str} |")

        output.append("")

        # Show content contexts for document matches
        docs_with_context = [d for d in documents if d.get('match_context') and d.get('match_location') == 'pdf_content']
        if docs_with_context:
            output.append("### Document Content Matches")
            output.append("")
            for item in docs_with_context[:5]:  # Show first 5 with context
                title = item.get('title_raw', item.get('title', '—'))
                dept = item.get('department_raw', '')
                contexts = item.get('match_context', [])
                if isinstance(contexts, list) and contexts:
                    output.append(f"**{title}** ({dept}):")
                    for context in contexts[:2]:  # Show first 2 contexts per document
                        output.append(f"> {context}")
                    output.append("")
            output.append("")

    # Recordings section
    recordings = results.get('recordings', [])
    if recordings:
        output.append(f"## Recordings ({recording_count} match{'es' if recording_count != 1 else ''})")
        output.append("")
        output.append("| Date | Committee | Title | Match | Link |")
        output.append("|------|-----------|-------|-------|------|")

        for item in recordings:
            date = item.get('date', '---')
            try:
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                date = date_obj.strftime('%b %d, %Y')
            except (ValueError, TypeError):
                pass

            # Committee name (short form)
            committee_name = item.get('committee_name', '')
            short_names = {
                'Joint Budget Committee': 'JBC',
                'House Health & Human Services': 'House H&HS',
                'Senate Health & Human Services': 'Senate H&HS',
                'Joint Technology Committee': 'Joint Tech',
                'House Agriculture, Water & Natural Resources': 'House Ag/Water',
                'Senate Agriculture & Natural Resources': 'Senate Ag/NR',
            }
            committee_short = short_names.get(committee_name, committee_name or 'JBC')

            title = item.get('title', '---')
            title = title.replace('|', '\\|')
            if len(title) > 35:
                title = title[:32] + "..."
            video_url = item.get('video_url', '')

            # Match location indicator
            match_location = item.get('match_location', 'title')
            if match_location == 'transcript':
                match_str = "Transcript"
            else:
                match_str = "Title"

            # Add "NEW" indicator if present
            if item.get('is_new'):
                title = f"*NEW* {title}"

            if video_url:
                output.append(f"| {date} | {committee_short} | {title} | {match_str} | [Watch]({video_url}) |")
            else:
                output.append(f"| {date} | {committee_short} | {title} | {match_str} | --- |")

        output.append("")

        # Show transcript context snippets for transcript matches
        recordings_with_context = [r for r in recordings if r.get('match_context') and r.get('match_location') == 'transcript']
        if recordings_with_context:
            output.append("### Transcript Matches")
            output.append("")
            for item in recordings_with_context[:5]:  # Show first 5 with context
                title = item.get('title_raw', item.get('title', '---'))
                date = item.get('date', '')
                committee_name = item.get('committee_name', '')
                label = f"**{title}**"
                if committee_name:
                    label += f" ({committee_name}, {date})"
                else:
                    label += f" ({date})"
                contexts = item.get('match_context', [])
                if isinstance(contexts, list) and contexts:
                    output.append(f"{label}:")
                    for context in contexts[:3]:  # Show first 3 contexts per recording
                        output.append(f"> {context}")
                    output.append("")
            output.append("")

    return "\n".join(output)


def _count_data_types(results):
    """Count how many data types have results."""
    count = 0
    if results.get('schedules'):
        count += 1
    if results.get('recordings'):
        count += 1
    if results.get('documents'):
        count += 1
    if results.get('bills'):
        count += 1
    return count


def format_watchlist_list(watchlists):
    """
    Format a list of watchlists as markdown table.

    Args:
        watchlists: List of watchlist summary dicts

    Returns:
        str: Markdown-formatted watchlist table
    """
    output = []
    output.append("# Watchlists")
    output.append("")

    if not watchlists:
        output.append("No watchlists configured.")
        output.append("")
        output.append("Create one with: `watch add <name> --keywords \"keyword1\" \"keyword2\"`")
        return "\n".join(output)

    output.append("| Name | Display Name | Keywords | Last Checked |")
    output.append("|------|--------------|----------|--------------|")

    for wl in watchlists:
        name = wl.get('name', '—')
        display = wl.get('display_name', '—')
        keywords = wl.get('keywords', [])
        keywords_str = ', '.join(keywords[:3])
        if len(keywords) > 3:
            keywords_str += f" (+{len(keywords) - 3} more)"
        last_checked = wl.get('last_checked')
        if last_checked:
            try:
                dt = datetime.fromisoformat(last_checked)
                last_checked = dt.strftime('%b %d, %Y %H:%M')
            except:
                pass
        else:
            last_checked = "*Never*"

        output.append(f"| {name} | {display} | {keywords_str} | {last_checked} |")

    output.append("")
    output.append(f"*{len(watchlists)} watchlist(s)*")

    return "\n".join(output)


def format_watchlist_definition(watchlist):
    """
    Format a single watchlist's configuration details.

    Args:
        watchlist: Watchlist dict with full configuration

    Returns:
        str: Markdown-formatted watchlist details
    """
    output = []
    name = watchlist.get('name', 'Unknown')
    display = watchlist.get('display_name', name)

    output.append(f"# Watchlist: {display}")
    output.append("")
    output.append(f"**Name:** `{name}`")
    output.append("")

    # Keywords
    keywords = watchlist.get('keywords', [])
    output.append("**Keywords:**")
    for kw in keywords:
        output.append(f"- {kw}")
    output.append("")

    # Departments
    departments = watchlist.get('departments', [])
    if departments:
        output.append("**Departments:**")
        for dept in departments:
            output.append(f"- {dept.title()}")
        output.append("")

    # Match mode
    match_mode = watchlist.get('match_mode', 'word_boundary')
    output.append(f"**Match Mode:** {match_mode}")
    output.append("")

    # Last checked
    last_checked = watchlist.get('last_checked')
    if last_checked:
        try:
            dt = datetime.fromisoformat(last_checked)
            last_checked = dt.strftime('%B %d, %Y at %H:%M')
        except:
            pass
        output.append(f"**Last Checked:** {last_checked}")
    else:
        output.append("**Last Checked:** Never")

    # Created at
    created = watchlist.get('created_at')
    if created:
        try:
            dt = datetime.fromisoformat(created)
            created = dt.strftime('%B %d, %Y')
        except:
            pass
        output.append(f"**Created:** {created}")

    return "\n".join(output)


def format_watchlist_results(run_results):
    """
    Format watchlist run results.

    Args:
        run_results: Dict from WatchlistManager.run_watchlist with:
            - watchlist: dict
            - results: dict (from search_all)
            - new_only: bool
            - run_at: str

    Returns:
        str: Markdown-formatted results
    """
    output = []
    watchlist = run_results.get('watchlist', {})
    results = run_results.get('results', {})
    new_only = run_results.get('new_only', False)

    display_name = watchlist.get('display_name', watchlist.get('name', 'Unknown'))

    if new_only:
        output.append(f"# Watchlist Results: {display_name} (New Only)")
    else:
        output.append(f"# Watchlist Results: {display_name}")

    output.append("")

    # Summary
    total = results.get('total_count', 0)
    if total == 0:
        if new_only:
            output.append("No new results since last check.")
        else:
            output.append("No results found matching this watchlist.")
        return "\n".join(output)

    keywords = watchlist.get('keywords', [])
    output.append(f"**Searching for:** {', '.join(keywords)}")
    output.append("")

    # Use the full search results formatter
    output.append(format_search_results_full(results, ', '.join(keywords)))

    # Add metadata
    output.append("---")
    run_at = run_results.get('run_at')
    if run_at:
        try:
            dt = datetime.fromisoformat(run_at)
            run_at = dt.strftime('%B %d, %Y at %H:%M')
        except:
            pass
        output.append(f"**Run at:** {run_at}")

    last_checked = watchlist.get('last_checked')
    if last_checked and new_only:
        try:
            dt = datetime.fromisoformat(last_checked)
            last_checked = dt.strftime('%B %d, %Y at %H:%M')
        except:
            pass
        output.append(f"**Showing results since:** {last_checked}")

    return "\n".join(output)


def format_bills_list(bills, session=None):
    """
    Format a list of bills as markdown table.

    Args:
        bills: List of bill summary dicts
        session: Optional session code for header

    Returns:
        str: Markdown-formatted bills table
    """
    output = []

    if session:
        output.append(f"# Bills - {session}")
    else:
        output.append("# Bills")
    output.append("")

    if not bills:
        output.append("No bills found.")
        return "\n".join(output)

    output.append("| Bill # | Title | Last Action |")
    output.append("|--------|-------|-------------|")

    for bill in bills:
        bill_num = bill.get('bill_number', '—')
        title = bill.get('title') or '—'
        # Truncate long titles
        if title != '—' and len(title) > 50:
            title = title[:47] + "..."
        title = title.replace('|', '\\|')

        last_action = bill.get('last_action') or '—'
        if last_action != '—' and len(last_action) > 40:
            last_action = last_action[:37] + "..."
        last_action = last_action.replace('|', '\\|')

        url = bill.get('url', '')
        if url:
            output.append(f"| [{bill_num}]({url}) | {title} | {last_action} |")
        else:
            output.append(f"| {bill_num} | {title} | {last_action} |")

    output.append("")
    output.append(f"*{len(bills)} bill(s)*")

    return "\n".join(output)


def format_bill_info(bill_data):
    """
    Format detailed bill information as markdown.

    Args:
        bill_data: Dict with bill details from bills.py scraper

    Returns:
        str: Markdown-formatted bill info
    """
    output = []

    # Header
    bill_num = bill_data.get('bill_number', 'Bill')
    title = bill_data.get('title', '')
    output.append(f"# {bill_num}")
    if title:
        output.append(f"## {title}")
    output.append("")

    # Session and status
    session = bill_data.get('session', 'Unknown')
    status = bill_data.get('status')
    output.append(f"**Session:** {session}")
    if status:
        output.append(f"**Status:** {status}")
    output.append("")

    # Long title
    long_title = bill_data.get('long_title')
    if long_title:
        output.append("### Description")
        output.append("")
        output.append(long_title)
        output.append("")

    # Sponsors
    sponsors = bill_data.get('sponsors', [])
    if sponsors:
        output.append("### Sponsors")
        output.append("")

        prime = [s for s in sponsors if s.get('role') == 'Prime Sponsor']
        co = [s for s in sponsors if s.get('role') == 'Co-Sponsor']

        if prime:
            output.append("**Prime Sponsors:**")
            for sponsor in prime:
                name = sponsor.get('name', 'Unknown')
                url = sponsor.get('url')
                if url:
                    output.append(f"- [{name}]({url})")
                else:
                    output.append(f"- {name}")
            output.append("")

        if co:
            output.append("**Co-Sponsors:**")
            for sponsor in co:
                name = sponsor.get('name', 'Unknown')
                url = sponsor.get('url')
                if url:
                    output.append(f"- [{name}]({url})")
                else:
                    output.append(f"- {name}")
            output.append("")

    # Committee assignment
    committee = bill_data.get('committee')
    if committee:
        output.append("### Committee Assignment")
        output.append("")
        comm_name = committee.get('name', 'Unknown')
        comm_url = committee.get('url')
        if comm_url:
            output.append(f"[{comm_name}]({comm_url})")
        else:
            output.append(comm_name)
        output.append("")

    # Subjects
    subjects = bill_data.get('subjects', [])
    if subjects:
        output.append("### Subjects")
        output.append("")
        output.append(', '.join(subjects))
        output.append("")

    # Last action
    last_action = bill_data.get('last_action')
    if last_action:
        output.append("### Last Action")
        output.append("")
        output.append(last_action)
        output.append("")

    # Bill text versions
    bill_text = bill_data.get('bill_text', [])
    if bill_text:
        output.append("### Bill Text")
        output.append("")
        output.append("| Version | Date | Link |")
        output.append("|---------|------|------|")

        for version in bill_text:
            ver = version.get('version', '—')
            date = version.get('date', '—')
            url = version.get('url', '')

            if url:
                output.append(f"| {ver} | {date} | [Download]({url}) |")
            else:
                output.append(f"| {ver} | {date} | — |")

        output.append("")

    # Fiscal notes
    fiscal_notes = bill_data.get('fiscal_notes', [])
    if fiscal_notes:
        output.append("### Fiscal Notes")
        output.append("")
        output.append("| Version | Date | Link |")
        output.append("|---------|------|------|")

        for note in fiscal_notes:
            ver = note.get('version', '—')
            date = note.get('date', '—')
            url = note.get('url', '')

            if url:
                output.append(f"| {ver} | {date} | [Download]({url}) |")
            else:
                output.append(f"| {ver} | {date} | — |")

        output.append("")

    # Amendments
    amendments = bill_data.get('amendments', [])
    if amendments:
        output.append(f"### Amendments ({len(amendments)})")
        output.append("")
        output.append("| Date | Number | Location | Status | Link |")
        output.append("|------|--------|----------|--------|------|")

        for amend in amendments:
            date = amend.get('date', '—')
            number = amend.get('number', '—')
            location = amend.get('location', '—')
            status = amend.get('status', '—')
            url = amend.get('url', '')

            if url:
                output.append(f"| {date} | {number} | {location} | {status} | [PDF]({url}) |")
            else:
                output.append(f"| {date} | {number} | {location} | {status} | — |")

        output.append("")

    # Votes
    votes = bill_data.get('votes', [])
    if votes:
        output.append(f"### Votes ({len(votes)})")
        output.append("")
        output.append("| Date | Calendar | Motion | Result | Link |")
        output.append("|------|----------|--------|--------|------|")

        for vote in votes:
            date = vote.get('date', '—')
            calendar = vote.get('calendar', '—')
            motion = vote.get('motion', '—')
            result = vote.get('result', '—')
            url = vote.get('url', '')

            if url:
                output.append(f"| {date} | {calendar} | {motion} | {result} | [Details]({url}) |")
            else:
                output.append(f"| {date} | {calendar} | {motion} | {result} | — |")

        output.append("")

    # Bill history
    history = bill_data.get('history', [])
    if history:
        output.append("### Bill History")
        output.append("")
        for entry in history:
            date = entry.get('date', '')
            action = entry.get('action', '')
            if date:
                output.append(f"- **{date}**: {action}")
            else:
                output.append(f"- {action}")
        output.append("")

    # Metadata
    output.append("---")
    output.append(f"**URL:** {bill_data.get('url', 'N/A')}")
    output.append(f"**Fetched:** {bill_data.get('fetched_at', 'N/A')}")

    return "\n".join(output)


def _ms_to_timestamp(ms):
    """Convert milliseconds to HH:MM:SS format."""
    if ms is None:
        return "00:00:00"
    total_seconds = int(ms / 1000)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def format_transcript(transcript_data, speaker_filter=None, highlight_query=None):
    """
    Format a transcript as markdown with speaker labels and timestamps.

    Args:
        transcript_data: Transcript dict from transcripts.py
        speaker_filter: Optional speaker letter to show only that speaker
        highlight_query: Optional query string to highlight in text

    Returns:
        str: Markdown-formatted transcript
    """
    output = []

    clip_id = transcript_data.get('clip_id', '?')
    duration = transcript_data.get('duration_seconds', 0)
    speaker_count = transcript_data.get('speaker_count', 0)
    transcribed_at = transcript_data.get('transcribed_at', '')

    output.append(f"# Transcript - Clip {clip_id}")
    output.append("")
    output.append(f"**Duration:** {_ms_to_timestamp(int(duration * 1000))}")
    output.append(f"**Speakers:** {speaker_count}")
    output.append(f"**Transcribed:** {transcribed_at[:10] if transcribed_at else 'Unknown'}")
    output.append("")

    if transcript_data.get('error'):
        output.append(f"**Error:** {transcript_data['error']}")
        return "\n".join(output)

    utterances = transcript_data.get('utterances', [])
    if not utterances:
        output.append("No utterances found in transcript.")
        return "\n".join(output)

    # Build highlight pattern if query provided
    highlight_pattern = None
    if highlight_query:
        from scrapers.search import build_search_pattern
        highlight_pattern = build_search_pattern(highlight_query)

    output.append("---")
    output.append("")

    last_speaker = None
    for utt in utterances:
        speaker = utt.get('speaker', '?')

        # Apply speaker filter
        if speaker_filter and speaker != speaker_filter:
            continue

        start_ms = utt.get('start', 0)
        timestamp = _ms_to_timestamp(start_ms)
        text = utt.get('text', '')

        # Highlight matches if pattern provided
        if highlight_pattern:
            from scrapers.search import highlight_matches
            text = highlight_matches(text, highlight_pattern)

        # Only show speaker header when speaker changes
        if speaker != last_speaker:
            output.append(f"### Speaker {speaker} [{timestamp}]")
            output.append("")
            last_speaker = speaker
        else:
            output.append(f"*[{timestamp}]*")

        output.append(text)
        output.append("")

    return "\n".join(output)


def format_transcript_list(transcribed_recordings, all_recordings=None):
    """
    Format a list of transcribed recordings as a markdown table.

    Args:
        transcribed_recordings: List of transcript summary dicts
        all_recordings: Optional list of all recordings for status comparison

    Returns:
        str: Markdown-formatted table
    """
    output = []
    output.append("# Transcribed Recordings")
    output.append("")

    if not transcribed_recordings:
        output.append("No recordings have been transcribed yet.")
        output.append("")
        output.append("Transcribe a recording with: `transcript transcribe <clip_id>`")
        return "\n".join(output)

    output.append("| Clip ID | Speakers | Utterances | Duration | Transcribed |")
    output.append("|---------|----------|------------|----------|-------------|")

    for t in transcribed_recordings:
        clip_id = t.get('clip_id', '?')
        speakers = t.get('speaker_count', 0)
        utterances = t.get('utterance_count', 0)
        duration = _ms_to_timestamp(int(t.get('duration_seconds', 0) * 1000))
        transcribed = t.get('transcribed_at', '')[:10] if t.get('transcribed_at') else '—'
        error = t.get('error')

        if error:
            output.append(f"| {clip_id} | — | — | — | Error |")
        else:
            output.append(f"| {clip_id} | {speakers} | {utterances} | {duration} | {transcribed} |")

    output.append("")
    output.append(f"*{len(transcribed_recordings)} transcript(s)*")

    return "\n".join(output)


def format_transcription_status(committees_status):
    """
    Format transcription coverage across all priority committees.

    Args:
        committees_status: List of dicts with keys:
            - name: str (committee human-readable name)
            - code: str (committee code)
            - total: int (total recordings)
            - transcribed: int (transcribed count)
            - hours: float (total hours of untranscribed)
            - cost: float (estimated cost)

    Returns:
        str: Markdown-formatted status table
    """
    output = []
    output.append("# Transcription Status")
    output.append("")

    if not committees_status:
        output.append("No committee recording data available.")
        return "\n".join(output)

    output.append("| Committee | Recordings | Transcribed | Remaining | Est. Cost |")
    output.append("|-----------|------------|-------------|-----------|-----------|")

    total_recordings = 0
    total_transcribed = 0
    total_remaining = 0
    total_cost = 0.0

    for cs in committees_status:
        name = cs.get('name', 'Unknown')
        total = cs.get('total', 0)
        done = cs.get('transcribed', 0)
        remaining = total - done
        cost = cs.get('cost', 0.0)

        total_recordings += total
        total_transcribed += done
        total_remaining += remaining
        total_cost += cost

        pct = f"{done}/{total}" if total > 0 else "0/0"
        cost_str = f"${cost:.2f}" if remaining > 0 else "---"
        output.append(f"| {name} | {total} | {pct} | {remaining} | {cost_str} |")

    output.append(f"| **Total** | **{total_recordings}** | **{total_transcribed}/{total_recordings}** | **{total_remaining}** | **${total_cost:.2f}** |")
    output.append("")

    if total_remaining > 0:
        output.append(f"*Estimated cost to transcribe all remaining: ${total_cost:.2f}*")
    else:
        output.append("*All recordings transcribed!*")

    return "\n".join(output)
