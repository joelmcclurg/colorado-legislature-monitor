"""HTML formatters for Colorado Legislature search results."""
from datetime import datetime
import html


def format_search_results_html(results, query):
    """
    Format search results as styled HTML.

    Args:
        results: Results dict from search_all
        query: Original query string

    Returns:
        str: HTML document with embedded CSS
    """
    total = results.get('total_count', 0)

    # CSS styling
    css = """
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            max-width: 1200px;
            margin: 40px auto;
            padding: 0 20px;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
        }
        .container {
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }
        h2 {
            color: #34495e;
            margin-top: 40px;
            margin-bottom: 20px;
            border-bottom: 2px solid #ecf0f1;
            padding-bottom: 8px;
        }
        h3 {
            color: #7f8c8d;
            margin-top: 30px;
            margin-bottom: 15px;
        }
        .summary {
            background: #ecf0f1;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background: white;
        }
        th {
            background: #3498db;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }
        td {
            padding: 10px 12px;
            border-bottom: 1px solid #ecf0f1;
        }
        tr:hover {
            background: #f8f9fa;
        }
        a {
            color: #3498db;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
        .match {
            background: #fff3cd;
            padding: 2px 4px;
            border-radius: 3px;
            font-weight: 600;
        }
        .context {
            background: #f8f9fa;
            border-left: 4px solid #3498db;
            padding: 15px;
            margin: 10px 0;
            font-style: italic;
            color: #555;
        }
        .context-item {
            margin-bottom: 20px;
        }
        .context-title {
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 8px;
        }
        .badge {
            background: #e74c3c;
            color: white;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 0.85em;
            font-weight: 600;
            margin-right: 5px;
        }
        .match-type {
            background: #27ae60;
            color: white;
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 0.85em;
        }
        .no-results {
            text-align: center;
            padding: 40px;
            color: #7f8c8d;
        }
    </style>
    """

    output = []
    output.append("<!DOCTYPE html>")
    output.append("<html lang='en'>")
    output.append("<head>")
    output.append("<meta charset='UTF-8'>")
    output.append("<meta name='viewport' content='width=device-width, initial-scale=1.0'>")
    output.append(f"<title>Search Results: {html.escape(query)}</title>")
    output.append(css)
    output.append("</head>")
    output.append("<body>")
    output.append("<div class='container'>")

    # Header
    output.append(f"<h1>Search Results for \"{html.escape(query)}\"</h1>")

    if total == 0:
        output.append("<div class='no-results'>")
        output.append("<p>No results found.</p>")
        output.append("</div>")
    else:
        # Summary
        type_count = sum(1 for k in ['schedules', 'recordings', 'documents', 'bills']
                         if results.get(k, []))
        output.append("<div class='summary'>")
        output.append(f"<strong>Found {total} matches</strong> across {type_count} data type(s).")
        output.append("</div>")

        # Bills section
        bills = results.get('bills', [])
        if bills:
            output.append(f"<h2>Bills ({len(bills)} matches)</h2>")
            output.append("<table>")
            output.append("<tr><th>Bill #</th><th>Title</th><th>Sponsors</th><th>Match</th></tr>")

            for item in bills:
                bill_num = html.escape(item.get('bill_number', '—'))
                title = _format_html_text(item.get('title', '—'))

                sponsors = item.get('sponsors', [])
                sponsors_str = ', '.join(sponsors[:2]) if sponsors else '—'
                if len(sponsors) > 2:
                    sponsors_str += f" (+{len(sponsors) - 2})"
                sponsors_str = html.escape(sponsors_str)

                # Match location
                match_location = item.get('match_location', 'title')
                if match_location == 'bill_text':
                    match_str = f"<span class='match-type'>Bill Text ({html.escape(item.get('match_version', ''))})</span>"
                elif match_location == 'amendment':
                    match_str = f"<span class='match-type'>Amendment {html.escape(item.get('match_amendment', ''))}</span>"
                elif match_location == 'fiscal_note':
                    match_str = "<span class='match-type'>Fiscal Note</span>"
                else:
                    match_str = "<span class='match-type'>Title</span>"

                # NEW badge
                if item.get('is_new'):
                    title = f"<span class='badge'>NEW</span> {title}"

                url = item.get('url', '')
                if url:
                    output.append(f"<tr><td><a href='{html.escape(url)}'>{bill_num}</a></td><td>{title}</td><td>{sponsors_str}</td><td>{match_str}</td></tr>")
                else:
                    output.append(f"<tr><td>{bill_num}</td><td>{title}</td><td>{sponsors_str}</td><td>{match_str}</td></tr>")

            output.append("</table>")

            # Bill content contexts
            bills_with_context = [b for b in bills if b.get('match_context') and b.get('match_location') != 'title']
            if bills_with_context:
                output.append("<h3>Bill Content Matches</h3>")
                for item in bills_with_context[:5]:
                    output.append("<div class='context-item'>")
                    bill_num = html.escape(item.get('bill_number', '—'))
                    match_location = html.escape(item.get('match_location', ''))
                    output.append(f"<div class='context-title'>{bill_num} ({match_location}):</div>")

                    contexts = item.get('match_context', [])
                    if isinstance(contexts, list):
                        for context in contexts[:2]:
                            context_html = _format_html_text(context)
                            output.append(f"<div class='context'>{context_html}</div>")
                    output.append("</div>")

        # Schedules section
        schedules = results.get('schedules', [])
        if schedules:
            output.append(f"<h2>Schedules ({len(schedules)} matches)</h2>")
            output.append("<table>")
            output.append("<tr><th>Date</th><th>Time</th><th>Topic</th><th>Week</th></tr>")

            for item in schedules:
                date = item.get('date', '—')
                try:
                    date_obj = datetime.strptime(date, '%Y-%m-%d')
                    date = date_obj.strftime('%b %d, %Y')
                except:
                    pass
                date = html.escape(date)

                time_str = html.escape(item.get('time', '—'))
                topic = _format_html_text(item.get('topic', '—'))
                week = html.escape(f"Week {item.get('week_number', '—')}")

                if item.get('is_new'):
                    topic = f"<span class='badge'>NEW</span> {topic}"

                output.append(f"<tr><td>{date}</td><td>{time_str}</td><td>{topic}</td><td>{week}</td></tr>")

            output.append("</table>")

        # Documents section
        documents = results.get('documents', [])
        if documents:
            output.append(f"<h2>Documents ({len(documents)} matches)</h2>")
            output.append("<table>")
            output.append("<tr><th>Department</th><th>Title</th><th>Type</th><th>Match</th></tr>")

            for item in documents:
                dept = item.get('department') or '—'
                if dept and dept != '—':
                    dept = dept.replace('**', '').title()
                dept = html.escape(dept)

                title = _format_html_text(item.get('title', '—'))
                if len(title) > 60:
                    title = title[:57] + "..."

                doc_type = item.get('doc_type', '—')
                if doc_type:
                    doc_type = doc_type.replace('_', ' ').title()
                doc_type = html.escape(doc_type)

                # Match location
                match_location = item.get('match_location', 'title')
                if match_location == 'pdf_content':
                    pdf_pages = item.get('pdf_pages', 0)
                    match_str = f"<span class='match-type'>PDF Content ({pdf_pages}p)</span>"
                else:
                    match_str = "<span class='match-type'>Title</span>"

                if item.get('is_new'):
                    title = f"<span class='badge'>NEW</span> {title}"

                url = item.get('url', '')
                if url:
                    title = f"<a href='{html.escape(url)}'>{title}</a>"

                output.append(f"<tr><td>{dept}</td><td>{title}</td><td>{doc_type}</td><td>{match_str}</td></tr>")

            output.append("</table>")

            # Document content contexts
            docs_with_context = [d for d in documents if d.get('match_context') and d.get('match_location') == 'pdf_content']
            if docs_with_context:
                output.append("<h3>Document Content Matches</h3>")
                for item in docs_with_context[:5]:
                    output.append("<div class='context-item'>")
                    title = html.escape(item.get('title_raw', item.get('title', '—')))
                    dept = html.escape(item.get('department_raw', ''))
                    output.append(f"<div class='context-title'>{title} ({dept}):</div>")

                    contexts = item.get('match_context', [])
                    if isinstance(contexts, list):
                        for context in contexts[:2]:
                            context_html = _format_html_text(context)
                            output.append(f"<div class='context'>{context_html}</div>")
                    output.append("</div>")

        # Recordings section
        recordings = results.get('recordings', [])
        if recordings:
            output.append(f"<h2>Recordings ({len(recordings)} matches)</h2>")
            output.append("<table>")
            output.append("<tr><th>Date</th><th>Title</th><th>Link</th></tr>")

            for item in recordings:
                date = item.get('date', '—')
                try:
                    date_obj = datetime.strptime(date, '%Y-%m-%d')
                    date = date_obj.strftime('%b %d, %Y')
                except:
                    pass
                date = html.escape(date)

                title = _format_html_text(item.get('title', '—'))
                video_url = item.get('video_url', '')

                if item.get('is_new'):
                    title = f"<span class='badge'>NEW</span> {title}"

                if video_url:
                    link = f"<a href='{html.escape(video_url)}'>Watch</a>"
                else:
                    link = "—"

                output.append(f"<tr><td>{date}</td><td>{title}</td><td>{link}</td></tr>")

            output.append("</table>")

    # Footer
    output.append("<hr style='margin-top: 40px; border: none; border-top: 1px solid #ecf0f1;'>")
    output.append("<p style='text-align: center; color: #7f8c8d; font-size: 0.9em;'>")
    output.append(f"Generated by Colorado Legislature Monitor on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    output.append("</p>")

    output.append("</div>")
    output.append("</body>")
    output.append("</html>")

    return "\n".join(output)


def format_advocacy_report_html(results, keywords, since_date, committee_members=None, champions=None):
    """
    Format search results as a professional advocacy HTML report.

    Args:
        results: Results dict from search_all (with mention_count on recordings)
        keywords: Original keyword string
        since_date: ISO date string (YYYY-MM-DD) for date range display
        committee_members: Optional dict mapping committee name -> list of member dicts

    Returns:
        str: Standalone HTML document
    """
    now = datetime.now()

    # Parse dates for display
    try:
        since_dt = datetime.strptime(since_date, '%Y-%m-%d')
        days = (now - since_dt).days
        date_range = f"{since_dt.strftime('%b %d, %Y')} — {now.strftime('%b %d, %Y')} ({days} days)"
    except (ValueError, TypeError):
        date_range = f"Through {now.strftime('%b %d, %Y')}"

    # Parse keywords into individual tags
    keyword_tags = []
    current = ""
    in_quotes = False
    for char in keywords:
        if char == '"':
            if in_quotes:
                if current:
                    keyword_tags.append(current)
                    current = ""
                in_quotes = False
            else:
                in_quotes = True
        elif char == ' ' and not in_quotes:
            if current:
                keyword_tags.append(current)
                current = ""
        else:
            current += char
    if current:
        keyword_tags.append(current)

    # Counts
    bills = results.get('bills', [])
    recordings = results.get('recordings', [])
    schedules = results.get('schedules', [])
    documents = results.get('documents', [])
    total = results.get('total_count', 0)

    css = """
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 0;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
        }
        .container {
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.12);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #1a365d 0%, #2c5282 100%);
            color: white;
            padding: 40px 40px 30px;
        }
        .header h1 {
            margin: 0 0 8px;
            font-size: 28px;
            font-weight: 700;
            border: none;
            color: white;
        }
        .header .subtitle {
            color: #bee3f8;
            font-size: 15px;
            margin-bottom: 20px;
        }
        .keyword-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 16px;
        }
        .keyword-tag {
            background: rgba(255,255,255,0.2);
            border: 1px solid rgba(255,255,255,0.3);
            color: white;
            padding: 4px 14px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: 500;
        }
        .date-range {
            color: #bee3f8;
            font-size: 14px;
        }
        .stats-bar {
            display: flex;
            gap: 0;
            background: #edf2f7;
            border-bottom: 1px solid #e2e8f0;
        }
        .stat-item {
            flex: 1;
            text-align: center;
            padding: 16px 10px;
            border-right: 1px solid #e2e8f0;
        }
        .stat-item:last-child { border-right: none; }
        .stat-number {
            font-size: 28px;
            font-weight: 700;
            color: #2c5282;
            display: block;
        }
        .stat-label {
            font-size: 12px;
            color: #718096;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .content { padding: 30px 40px 40px; }
        h2 {
            color: #1a365d;
            margin-top: 40px;
            margin-bottom: 16px;
            font-size: 20px;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 8px;
        }
        h2:first-child { margin-top: 0; }
        h3 {
            color: #4a5568;
            margin-top: 24px;
            margin-bottom: 12px;
            font-size: 16px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 16px 0 24px;
            font-size: 14px;
        }
        th {
            background: #2c5282;
            color: white;
            padding: 10px 12px;
            text-align: left;
            font-weight: 600;
            font-size: 13px;
        }
        td {
            padding: 9px 12px;
            border-bottom: 1px solid #e2e8f0;
            vertical-align: top;
        }
        tr:hover { background: #f7fafc; }
        a { color: #2c5282; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .match {
            background: #fefcbf;
            padding: 1px 4px;
            border-radius: 3px;
            font-weight: 600;
        }
        .context {
            background: #f7fafc;
            border-left: 4px solid #2c5282;
            padding: 12px 16px;
            margin: 8px 0;
            font-size: 13px;
            color: #4a5568;
            line-height: 1.5;
        }
        .context-item { margin-bottom: 20px; }
        .context-title {
            font-weight: 600;
            color: #1a365d;
            margin-bottom: 6px;
            font-size: 14px;
        }
        .match-type {
            background: #276749;
            color: white;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 12px;
            white-space: nowrap;
        }
        .dialogue {
            background: #f7fafc;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            padding: 16px;
            margin: 10px 0 20px;
        }
        .dialogue-header {
            font-weight: 600;
            color: #1a365d;
            margin-bottom: 10px;
            font-size: 14px;
        }
        .utterance {
            margin-bottom: 10px;
            padding-left: 12px;
            border-left: 3px solid #cbd5e0;
            font-size: 13px;
            line-height: 1.5;
        }
        .utterance:last-child { margin-bottom: 0; }
        .speaker-label {
            color: #2c5282;
            font-weight: 600;
            font-size: 12px;
        }
        .mention-count {
            background: #2c5282;
            color: white;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 12px;
            font-weight: 600;
        }
        .no-results {
            text-align: center;
            padding: 40px;
            color: #a0aec0;
        }
        .executive-summary {
            background: #ebf8ff;
            border: 1px solid #bee3f8;
            border-radius: 8px;
            padding: 24px 28px;
            margin: 0 0 32px;
            font-size: 15px;
            line-height: 1.7;
            color: #2d3748;
        }
        .executive-summary strong {
            color: #1a365d;
        }
        .analysis-card {
            background: #f7fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 20px 24px;
            margin-bottom: 16px;
        }
        .analysis-card h3 {
            margin: 0 0 12px;
            font-size: 15px;
            color: #1a365d;
        }
        .analysis-card p {
            margin: 0;
            font-size: 14px;
            color: #4a5568;
        }
        .champion-tag {
            display: inline-block;
            background: #ebf4ff;
            border: 1px solid #bee3f8;
            color: #2c5282;
            padding: 3px 10px;
            border-radius: 14px;
            font-size: 13px;
            font-weight: 600;
            margin: 3px 4px 3px 0;
        }
        .champion-tag-leader {
            display: inline-block;
            background: #2c5282;
            border: 1px solid #2a4365;
            color: #fff;
            padding: 3px 10px;
            border-radius: 14px;
            font-size: 13px;
            font-weight: 700;
            margin: 3px 4px 3px 0;
        }
        .champion-tag-leader a, .champion-tag a {
            color: inherit;
            text-decoration: none;
        }
        .champion-tag-leader a:hover, .champion-tag a:hover {
            text-decoration: underline;
        }
        .gap-warning {
            background: #fffff0;
            border: 1px solid #fefcbf;
            border-left: 4px solid #ecc94b;
            border-radius: 6px;
            padding: 14px 18px;
            margin-bottom: 12px;
            font-size: 14px;
            color: #744210;
        }
        .gap-warning strong {
            color: #975a16;
        }
        .next-steps {
            list-style: none;
            padding: 0;
            margin: 16px 0 0;
            counter-reset: step-counter;
        }
        .next-steps li {
            counter-increment: step-counter;
            position: relative;
            padding: 12px 16px 12px 52px;
            margin-bottom: 10px;
            background: #f7fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            font-size: 14px;
            line-height: 1.5;
            color: #2d3748;
        }
        .next-steps li::before {
            content: counter(step-counter);
            position: absolute;
            left: 16px;
            top: 12px;
            background: #2c5282;
            color: white;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            font-size: 13px;
            font-weight: 700;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .footer {
            text-align: center;
            color: #a0aec0;
            font-size: 12px;
            padding: 20px 40px;
            border-top: 1px solid #e2e8f0;
        }
        .champion-card {
            background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
            border: 1px solid #bae6fd;
            border-left: 4px solid #0284c7;
            border-radius: 8px;
            padding: 16px 20px;
            margin-bottom: 12px;
        }
        .champion-card-header {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
        }
        .champion-name {
            font-size: 16px;
            font-weight: 700;
            color: #0c4a6e;
        }
        .champion-role {
            font-size: 13px;
            color: #0369a1;
            font-weight: 600;
        }
        .champion-mentions {
            background: #0284c7;
            color: white;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 700;
        }
        .champion-quote {
            background: white;
            border-left: 3px solid #7dd3fc;
            padding: 8px 12px;
            margin-top: 8px;
            font-size: 13px;
            line-height: 1.5;
            color: #475569;
            font-style: italic;
        }
    </style>
    """

    o = []
    o.append("<!DOCTYPE html>")
    o.append("<html lang='en'>")
    o.append("<head>")
    o.append("<meta charset='UTF-8'>")
    o.append("<meta name='viewport' content='width=device-width, initial-scale=1.0'>")
    o.append(f"<title>Legislative Intelligence Report - {html.escape(keywords)}</title>")
    o.append(css)
    o.append("</head>")
    o.append("<body>")
    o.append("<div class='container'>")

    # Header
    o.append("<div class='header'>")
    o.append("<h1>Legislative Intelligence Report</h1>")
    o.append("<div class='subtitle'>Colorado General Assembly</div>")
    o.append("<div class='keyword-tags'>")
    for tag in keyword_tags:
        o.append(f"<span class='keyword-tag'>{html.escape(tag)}</span>")
    o.append("</div>")
    o.append(f"<div class='date-range'>{html.escape(date_range)}</div>")
    o.append("</div>")

    # Stats bar
    o.append("<div class='stats-bar'>")
    o.append(f"<div class='stat-item'><span class='stat-number'>{len(bills)}</span><span class='stat-label'>Bills</span></div>")
    o.append(f"<div class='stat-item'><span class='stat-number'>{len(recordings)}</span><span class='stat-label'>Hearings</span></div>")
    o.append(f"<div class='stat-item'><span class='stat-number'>{len(documents)}</span><span class='stat-label'>Documents</span></div>")
    o.append(f"<div class='stat-item'><span class='stat-number'>{len(schedules)}</span><span class='stat-label'>Schedule Items</span></div>")
    o.append("</div>")

    o.append("<div class='content'>")

    if total == 0:
        o.append("<div class='no-results'><p>No results found for this query and date range.</p></div>")
    else:
        # === Executive Summary ===
        top_committees = _extract_top_committees(recordings)
        all_sponsors = _extract_sponsors(bills)

        summary_parts = []
        summary_parts.append(f"This report identified <strong>{total} matches</strong> across")
        type_names = []
        if bills:
            type_names.append(f"{len(bills)} bill(s)")
        if recordings:
            type_names.append(f"{len(recordings)} hearing(s)")
        if documents:
            type_names.append(f"{len(documents)} document(s)")
        if schedules:
            type_names.append(f"{len(schedules)} schedule item(s)")
        summary_parts.append(f" {', '.join(type_names)}.")

        if top_committees:
            top_name = html.escape(top_committees[0]['name'])
            if top_committees[0]['mentions'] > 0:
                summary_parts.append(f" The most active committee is <strong>{top_name}</strong> with {top_committees[0]['mentions']} keyword mention(s).")
            else:
                summary_parts.append(f" Hearings were found in <strong>{top_name}</strong>.")

        if bills:
            summary_parts.append(f" There {'is' if len(bills) == 1 else 'are'} <strong>{len(bills)} bill(s)</strong> currently in play.")
        else:
            summary_parts.append(" <strong>No bills</strong> have been introduced on this topic in the current session.")

        # Time trend
        recent_recordings = [r for r in recordings if r.get('date', '') >= (datetime.now().strftime('%Y-%m') + '-01')]
        if recent_recordings and len(recent_recordings) < len(recordings):
            summary_parts.append(f" Of the hearings found, {len(recent_recordings)} occurred this month.")

        o.append("<div class='executive-summary'>")
        o.append(''.join(summary_parts))
        o.append("</div>")

        # === Possible Champions ===
        if champions:
            o.append("<h2>Possible Champions</h2>")
            o.append("<p style='color: #475569; margin-bottom: 16px;'>Legislators who actively discussed these topics in committee hearings &mdash; potential allies for advocacy:</p>")
            for champ in champions:
                name_esc = html.escape(champ['display'])
                role = html.escape(champ.get('role', 'Member'))
                chamber = html.escape(champ.get('chamber', ''))
                committee = html.escape(champ.get('committee', ''))
                mentions = champ['mention_count']
                role_text = f"{role}, {chamber}" if chamber else role
                mention_label = "mention" if mentions == 1 else "mentions"

                o.append("<div class='champion-card'>")
                o.append("<div class='champion-card-header'>")
                o.append(f"<div><span class='champion-name'>{name_esc}</span><br>"
                         f"<span class='champion-role'>{role_text} &bull; {committee}</span></div>")
                o.append(f"<span class='champion-mentions'>{mentions} {mention_label}</span>")
                o.append("</div>")
                for quote in champ.get('sample_quotes', [])[:2]:
                    quote_html = _format_html_text(quote)
                    o.append(f"<div class='champion-quote'>{quote_html}</div>")
                o.append("</div>")

        # === Key Champions ===
        committees_with_mentions = [c for c in top_committees if c['mentions'] > 0] if top_committees else []
        has_committee_leaders = committee_members and committees_with_mentions
        if all_sponsors or committees_with_mentions or has_committee_leaders:
            o.append("<h2>Key Champions</h2>")

            if all_sponsors:
                o.append("<div class='analysis-card'>")
                o.append("<h3>Bill Sponsors</h3>")
                o.append("<p>Legislators who introduced relevant legislation:</p>")
                o.append("<div style='margin-top: 8px;'>")
                for s in all_sponsors:
                    o.append(f"<span class='champion-tag'>{html.escape(s)}</span>")
                o.append("</div>")
                o.append("</div>")

            if committees_with_mentions:
                o.append("<div class='analysis-card'>")
                o.append("<h3>Active Committees</h3>")
                o.append("<p>Committees ranked by total keyword mentions across hearings:</p>")
                o.append("<div style='margin-top: 8px;'>")
                for c in committees_with_mentions:
                    o.append(f"<span class='champion-tag'>{html.escape(c['name'])} ({c['mentions']} mentions, {c['hearings']} hearings)</span>")
                o.append("</div>")
                o.append("</div>")

            if has_committee_leaders:
                o.append("<div class='analysis-card'>")
                o.append("<h3>Committee Leaders</h3>")
                o.append("<p>Members of committees with keyword activity:</p>")
                for c in committees_with_mentions:
                    cname = c['name']
                    members = committee_members.get(cname, [])
                    if not members:
                        continue
                    o.append(f"<div style='margin-top: 10px;'><strong>{html.escape(cname)}</strong></div>")
                    o.append("<div style='margin-top: 4px;'>")
                    # Show leadership first, then other members
                    leaders = [m for m in members if m.get('role') in ('Chair', 'Vice Chair')]
                    others = [m for m in members if m.get('role') not in ('Chair', 'Vice Chair')]
                    for m in leaders:
                        name_esc = html.escape(m['name'])
                        role = html.escape(m.get('role', ''))
                        chamber = html.escape(m.get('chamber', ''))
                        label = f"{name_esc} ({role}, {chamber})" if chamber else f"{name_esc} ({role})"
                        url = m.get('profile_url', '')
                        if url:
                            o.append(f"<span class='champion-tag-leader'><a href='{html.escape(url)}'>{label}</a></span>")
                        else:
                            o.append(f"<span class='champion-tag-leader'>{label}</span>")
                    for m in others:
                        name_esc = html.escape(m['name'])
                        chamber = html.escape(m.get('chamber', ''))
                        label = f"{name_esc} ({chamber})" if chamber else name_esc
                        url = m.get('profile_url', '')
                        if url:
                            o.append(f"<span class='champion-tag'><a href='{html.escape(url)}'>{label}</a></span>")
                        else:
                            o.append(f"<span class='champion-tag'>{label}</span>")
                    o.append("</div>")
                o.append("</div>")

        # === Bills Section ===
        if bills:
            o.append(f"<h2>Bills ({len(bills)})</h2>")
            o.append("<table>")
            o.append("<tr><th>Bill #</th><th>Title</th><th>Sponsors</th><th>Match</th></tr>")

            for item in bills:
                bill_num = html.escape(item.get('bill_number', ''))
                title_html = _format_html_text(item.get('title', ''))

                sponsors = item.get('sponsors', [])
                sponsors_str = ', '.join(sponsors[:2]) if sponsors else ''
                if len(sponsors) > 2:
                    sponsors_str += f" (+{len(sponsors) - 2})"
                sponsors_str = html.escape(sponsors_str)

                match_location = item.get('match_location', 'title')
                if match_location == 'bill_text':
                    match_str = f"<span class='match-type'>Bill Text ({html.escape(item.get('match_version', ''))})</span>"
                elif match_location == 'amendment':
                    match_str = f"<span class='match-type'>Amendment {html.escape(item.get('match_amendment', ''))}</span>"
                elif match_location == 'fiscal_note':
                    match_str = "<span class='match-type'>Fiscal Note</span>"
                else:
                    match_str = "<span class='match-type'>Title</span>"

                url = item.get('url', '')
                bill_cell = f"<a href='{html.escape(url)}'>{bill_num}</a>" if url else bill_num
                o.append(f"<tr><td>{bill_cell}</td><td>{title_html}</td><td>{sponsors_str}</td><td>{match_str}</td></tr>")

            o.append("</table>")

            # Bill content contexts
            bills_with_context = [b for b in bills if b.get('match_context') and b.get('match_location') != 'title']
            if bills_with_context:
                o.append("<h3>Bill Content Matches</h3>")
                for item in bills_with_context[:5]:
                    o.append("<div class='context-item'>")
                    bill_num = html.escape(item.get('bill_number', ''))
                    loc = html.escape(item.get('match_location', ''))
                    o.append(f"<div class='context-title'>{bill_num} ({loc}):</div>")
                    contexts = item.get('match_context', [])
                    if isinstance(contexts, list):
                        for ctx in contexts[:3]:
                            o.append(f"<div class='context'>{_format_html_text(ctx)}</div>")
                    o.append("</div>")

        # === Hearings/Recordings Section ===
        if recordings:
            o.append(f"<h2>Hearings ({len(recordings)})</h2>")
            o.append("<table>")
            o.append("<tr><th>Date</th><th>Committee</th><th>Title</th><th>Duration</th><th>Mentions</th><th>Link</th></tr>")

            for item in recordings:
                date_str = item.get('date', '')
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    date_display = date_obj.strftime('%b %d, %Y')
                except (ValueError, TypeError):
                    date_display = html.escape(date_str)

                committee = html.escape(item.get('committee_name', '') or item.get('committee', '') or 'JBC')
                title_html = _format_html_text(item.get('title', ''))
                duration = html.escape(item.get('duration', '') or '')

                mention_count = item.get('mention_count', 0)
                if mention_count > 0:
                    mentions_str = f"<span class='mention-count'>{mention_count}</span>"
                else:
                    mentions_str = ""

                video_url = item.get('video_url', '')
                link = f"<a href='{html.escape(video_url)}'>Watch</a>" if video_url else ""

                o.append(f"<tr><td>{date_display}</td><td>{committee}</td><td>{title_html}</td><td>{duration}</td><td>{mentions_str}</td><td>{link}</td></tr>")

            o.append("</table>")

            # Transcript dialogue snippets
            recordings_with_context = [r for r in recordings if r.get('match_context')]
            if recordings_with_context:
                o.append("<h3>Transcript Excerpts</h3>")
                for item in recordings_with_context:
                    title_raw = html.escape(item.get('title_raw', item.get('title', '')))
                    date_str = item.get('date', '')
                    try:
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        date_display = date_obj.strftime('%b %d, %Y')
                    except (ValueError, TypeError):
                        date_display = html.escape(date_str)
                    committee = html.escape(item.get('committee_name', '') or 'JBC')

                    o.append("<div class='dialogue'>")
                    o.append(f"<div class='dialogue-header'>{title_raw} — {committee} ({date_display})</div>")

                    contexts = item.get('match_context', [])
                    if isinstance(contexts, list):
                        for ctx in contexts[:5]:
                            ctx_html = _format_html_text(ctx)
                            o.append(f"<div class='utterance'>{ctx_html}</div>")

                    o.append("</div>")

        # === Hearing Mention Frequency ===
        recordings_with_mentions = [r for r in recordings if r.get('mention_count', 0) > 0]
        if recordings_with_mentions:
            recordings_with_mentions.sort(key=lambda x: x.get('mention_count', 0), reverse=True)
            o.append("<h2>Hearing Mention Frequency</h2>")
            o.append("<table>")
            o.append("<tr><th>Committee</th><th>Date</th><th>Title</th><th>Keyword Mentions</th></tr>")

            for item in recordings_with_mentions:
                committee = html.escape(item.get('committee_name', '') or item.get('committee', '') or 'JBC')
                date_str = item.get('date', '')
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    date_display = date_obj.strftime('%b %d, %Y')
                except (ValueError, TypeError):
                    date_display = html.escape(date_str)
                title_raw = html.escape(item.get('title_raw', item.get('title', '')))
                count = item.get('mention_count', 0)

                o.append(f"<tr><td>{committee}</td><td>{date_display}</td><td>{title_raw}</td><td><span class='mention-count'>{count}</span></td></tr>")

            o.append("</table>")

        # === Schedules Section ===
        if schedules:
            o.append(f"<h2>Schedule Items ({len(schedules)})</h2>")
            o.append("<table>")
            o.append("<tr><th>Date</th><th>Time</th><th>Topic</th><th>Week</th></tr>")

            for item in schedules:
                date_str = item.get('date', '')
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    date_display = date_obj.strftime('%b %d, %Y')
                except (ValueError, TypeError):
                    date_display = html.escape(date_str)

                time_str = html.escape(item.get('time', ''))
                topic = _format_html_text(item.get('topic', ''))
                week = html.escape(f"Week {item.get('week_number', '')}")

                o.append(f"<tr><td>{date_display}</td><td>{time_str}</td><td>{topic}</td><td>{week}</td></tr>")

            o.append("</table>")

        # === Documents Section ===
        if documents:
            o.append(f"<h2>Documents ({len(documents)})</h2>")
            o.append("<table>")
            o.append("<tr><th>Department</th><th>Title</th><th>Type</th><th>Match</th></tr>")

            for item in documents:
                dept = item.get('department') or ''
                if dept:
                    dept = dept.replace('**', '').title()
                dept = html.escape(dept)

                title_html = _format_html_text(item.get('title', ''))

                doc_type = item.get('doc_type', '')
                if doc_type:
                    doc_type = doc_type.replace('_', ' ').title()
                doc_type = html.escape(doc_type)

                match_location = item.get('match_location', 'title')
                if match_location == 'pdf_content':
                    pdf_pages = item.get('pdf_pages', 0)
                    match_str = f"<span class='match-type'>PDF ({pdf_pages}p)</span>"
                else:
                    match_str = "<span class='match-type'>Title</span>"

                url = item.get('url', '')
                if url:
                    title_html = f"<a href='{html.escape(url)}'>{title_html}</a>"

                o.append(f"<tr><td>{dept}</td><td>{title_html}</td><td>{doc_type}</td><td>{match_str}</td></tr>")

            o.append("</table>")

            # Document content contexts
            docs_with_context = [d for d in documents if d.get('match_context') and d.get('match_location') == 'pdf_content']
            if docs_with_context:
                o.append("<h3>Document Content Matches</h3>")
                for item in docs_with_context[:5]:
                    o.append("<div class='context-item'>")
                    title_raw = html.escape(item.get('title_raw', item.get('title', '')))
                    dept = html.escape(item.get('department_raw', ''))
                    o.append(f"<div class='context-title'>{title_raw} ({dept}):</div>")
                    contexts = item.get('match_context', [])
                    if isinstance(contexts, list):
                        for ctx in contexts[:3]:
                            o.append(f"<div class='context'>{_format_html_text(ctx)}</div>")
                    o.append("</div>")

        # === Barriers & Gaps ===
        gaps = []
        if not bills:
            gaps.append(("<strong>No introduced legislation.</strong>", "No bills matching these keywords have been introduced in the current session. There is no legislative vehicle for this issue yet."))
        if not schedules:
            gaps.append(("<strong>No upcoming hearings scheduled.</strong>", "No future schedule items match these keywords. The topic may not be on the near-term agenda."))

        # Check for priority committees with no mentions
        from scrapers.sliq import PRIORITY_COMMITTEES
        mentioned_committees = {(r.get('committee_name', '') or r.get('committee', '') or '').lower() for r in recordings}
        silent_committees = []
        for code, info in PRIORITY_COMMITTEES.items():
            cname = info['name']
            if cname.lower() not in mentioned_committees:
                silent_committees.append(cname)
        if silent_committees:
            names = ', '.join(html.escape(c) for c in silent_committees[:4])
            gaps.append(("<strong>Coverage gaps.</strong>", f"No keyword mentions found in: {names}. These committees may not have discussed this topic, or transcripts may not be available yet."))

        if documents and not bills and not recordings:
            gaps.append(("<strong>Budget documents only.</strong>", "Matches appear only in budget/fiscal documents. Without a bill or hearing discussion, this topic may lack a legislative vehicle."))

        if gaps:
            o.append("<h2>Barriers &amp; Gaps</h2>")
            for title, desc in gaps:
                o.append(f"<div class='gap-warning'>{title} {desc}</div>")

        # === Recommended Next Steps ===
        steps = []

        if schedules:
            upcoming_dates = []
            for s in schedules[:3]:
                d = s.get('date', '')
                try:
                    d_obj = datetime.strptime(d, '%Y-%m-%d')
                    upcoming_dates.append(d_obj.strftime('%b %d'))
                except (ValueError, TypeError):
                    pass
            if upcoming_dates:
                steps.append(f"Monitor upcoming hearings on {', '.join(upcoming_dates)}.")

        if bills:
            bill_nums = [b.get('bill_number', '') for b in bills[:5] if b.get('bill_number')]
            if bill_nums:
                steps.append(f"Track {', '.join(bill_nums)} through the committee process.")

        if not bills:
            steps.append("Consider engaging legislators to introduce legislation on this topic.")

        recordings_with_context = [r for r in recordings if r.get('match_context')]
        if recordings_with_context and top_committees:
            top_c = html.escape(top_committees[0]['name'])
            steps.append(f"Review transcript excerpts from {top_c} to understand legislative sentiment.")

        if documents:
            steps.append("Engage with JBC staff regarding budget allocations related to this topic.")

        if not recordings:
            steps.append("Request transcription of recent committee hearings to expand search coverage.")

        if steps:
            o.append("<h2>Recommended Next Steps</h2>")
            o.append("<ol class='next-steps'>")
            for step in steps:
                o.append(f"<li>{step}</li>")
            o.append("</ol>")

    o.append("</div>")  # end .content

    # Footer
    o.append(f"<div class='footer'>Generated by Colorado Legislature Monitor on {now.strftime('%Y-%m-%d %H:%M:%S')}</div>")

    o.append("</div>")  # end .container
    o.append("</body>")
    o.append("</html>")

    return "\n".join(o)


def _extract_top_committees(recordings):
    """Group recordings by committee, sum mentions, return sorted list."""
    committee_mentions = {}
    for r in recordings:
        name = r.get('committee_name', '') or r.get('committee', '') or 'JBC'
        count = r.get('mention_count', 0)
        if name not in committee_mentions:
            committee_mentions[name] = {'name': name, 'mentions': 0, 'hearings': 0}
        committee_mentions[name]['mentions'] += count
        committee_mentions[name]['hearings'] += 1
    result = sorted(committee_mentions.values(), key=lambda x: x['mentions'], reverse=True)
    return result


def _extract_sponsors(bills):
    """Extract unique sponsor names from matched bills."""
    sponsors = []
    seen = set()
    for b in bills:
        for s in b.get('sponsors', []):
            s_clean = ' '.join(s.split())
            if s_clean and s_clean not in seen:
                seen.add(s_clean)
                sponsors.append(s_clean)
    return sponsors



def _format_html_text(text):
    """
    Format text for HTML, converting **bold** to <span class='match'>.

    Args:
        text: Text with markdown bold markers

    Returns:
        str: HTML-formatted text
    """
    # Escape HTML first
    text = html.escape(text)

    # Convert **bold** to <span class='match'>
    import re
    text = re.sub(r'\*\*(.+?)\*\*', r"<span class='match'>\1</span>", text)

    return text
