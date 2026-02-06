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
