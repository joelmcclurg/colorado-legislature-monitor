#!/usr/bin/env python3
"""
Colorado Legislature Monitoring CLI

Main entry point for fetching and displaying Colorado legislature data,
with a focus on the Joint Budget Committee (JBC).
"""
import argparse
import sys
import warnings
from datetime import datetime
from pathlib import Path

# Suppress SSL warnings from urllib3
warnings.filterwarnings('ignore', message='urllib3 v2 only supports OpenSSL')

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from cache.manager import CacheManager
from scrapers.schedules import get_jbc_schedule_for_week, get_current_week_number
from scrapers.sessions import get_current_session
from scrapers.audio import fetch_jbc_recordings, get_recordings_for_week
from scrapers.documents import fetch_budget_documents, get_documents_for_department, get_documents_by_type, list_departments
from scrapers.search import search_all, filter_results_since, build_search_pattern, highlight_matches
from scrapers.watchlist import WatchlistManager
from scrapers.committees import list_committees, get_committee_info, search_committees
from scrapers.bills import list_bills, get_bill_info, search_bills, extract_bill_content
from scrapers.transcripts import (
    transcribe_recording, get_transcript, list_transcribed_recordings,
    batch_transcribe, estimate_cost, resolve_speakers, resolve_and_store_speakers,
    format_timestamp
)
from scrapers.sliq import (
    PRIORITY_COMMITTEES, fetch_committee_recordings, fetch_all_priority_recordings
)
from formatters.markdown import (
    format_schedule, format_recordings, format_recordings_list,
    format_documents, format_error,
    format_search_results_full, format_watchlist_list, format_watchlist_definition,
    format_watchlist_results, format_committee_info, format_committees_list,
    format_bills_list, format_bill_info, format_transcript, format_transcript_list,
    format_transcription_status
)
from formatters.html import format_search_results_html, format_advocacy_report_html


def cmd_jbc_schedule(args):
    """Handle 'jbc schedule' command."""
    week_number = None

    if args.week == 'current':
        week_number = get_current_week_number()
    elif args.week == 'next':
        week_number = get_current_week_number() + 1
    elif args.week.isdigit():
        week_number = int(args.week)
    else:
        print(format_error(f"Invalid week specifier: {args.week}"))
        return 1

    # Determine what to include
    include_media = not getattr(args, 'no_media', False)
    include_docs = not getattr(args, 'no_docs', False)

    # Initialize cache
    cache = CacheManager()

    # Fetch schedule
    try:
        schedule = get_jbc_schedule_for_week(
            week_number,
            cache_manager=cache,
            include_media=include_media,
            include_docs=include_docs
        )

        if schedule:
            print(format_schedule(schedule, include_media=include_media, include_docs=include_docs))
            return 0
        else:
            print(format_error(f"Could not fetch schedule for week {week_number}. "
                             "The PDF may not be available yet, or the URL pattern may have changed."))
            return 1

    except Exception as e:
        print(format_error(f"Error fetching schedule: {str(e)}"))
        return 1


def cmd_jbc_recordings(args):
    """Handle 'jbc recordings' command."""
    cache = CacheManager()

    try:
        # Determine what recordings to show
        if hasattr(args, 'date') and args.date:
            # Specific date
            from scrapers.audio import get_recording_for_date
            recording = get_recording_for_date(args.date, cache)
            recordings = [recording] if recording else []
            print(format_recordings(recordings, date_str=args.date))
        elif hasattr(args, 'week') and args.week:
            # Specific week
            if args.week == 'current':
                week_number = get_current_week_number()
            elif args.week == 'next':
                week_number = get_current_week_number() + 1
            elif args.week.isdigit():
                week_number = int(args.week)
            else:
                print(format_error(f"Invalid week specifier: {args.week}"))
                return 1

            recordings = get_recordings_for_week(week_number, cache_manager=cache)
            print(format_recordings(recordings, week_number=week_number))
        else:
            # Show all recent recordings
            recordings = fetch_jbc_recordings(cache)
            print(format_recordings(recordings))

        return 0

    except Exception as e:
        print(format_error(f"Error fetching recordings: {str(e)}"))
        return 1


def cmd_jbc_documents(args):
    """Handle 'jbc documents' command."""
    cache = CacheManager()

    try:
        # Determine what documents to show
        if hasattr(args, 'department') and args.department:
            # Filter by department
            doc_type = getattr(args, 'type', None)
            documents = get_documents_for_department(args.department, doc_type=doc_type, cache_manager=cache)
            print(format_documents(documents, department=args.department, doc_type=doc_type))
        elif hasattr(args, 'type') and args.type:
            # Filter by type
            documents = get_documents_by_type(args.type, cache)
            print(format_documents(documents, doc_type=args.type))
        elif hasattr(args, 'list_departments') and args.list_departments:
            # List available departments
            departments = list_departments(cache)
            print("# Departments with Budget Documents\n")
            for dept in departments:
                print(f"- {dept.title()}")
            print(f"\n*{len(departments)} department(s)*")
        else:
            # Show all documents
            documents = fetch_budget_documents(cache)
            print(format_documents(documents))

        return 0

    except Exception as e:
        print(format_error(f"Error fetching documents: {str(e)}"))
        return 1


def cmd_jbc_search(args):
    """Handle 'jbc search' command."""
    cache = CacheManager()

    try:
        query = ' '.join(args.query)
        if getattr(args, 'exact', False):
            query = f'"{query}"'

        # Determine data types to search
        data_types = None
        if hasattr(args, 'type') and args.type:
            data_types = [args.type]

        # Get filters
        department = getattr(args, 'department', None)
        chamber = getattr(args, 'chamber', None)
        output_format = getattr(args, 'format', 'markdown')

        # Run search
        results = search_all(
            query,
            data_types=data_types,
            cache_manager=cache,
            department=department,
            chamber=chamber
        )

        # Format output
        if output_format == 'html':
            output = format_search_results_html(results, query)
        else:
            output = format_search_results_full(results, query)

        print(output)
        return 0

    except Exception as e:
        print(format_error(f"Error searching: {str(e)}"))
        return 1


def cmd_committee_info(args):
    """Handle 'committee info' command."""
    cache = CacheManager()

    try:
        committee_slug = args.name
        session = getattr(args, 'session', None)

        # Fetch committee info
        committee = get_committee_info(
            committee_slug=committee_slug,
            session=session,
            cache_manager=cache
        )

        if not committee:
            print(format_error(f"Committee '{committee_slug}' not found. "
                             "Try using 'committees list' to see available committees."))
            return 1

        print(format_committee_info(committee))
        return 0

    except Exception as e:
        print(format_error(f"Error fetching committee info: {str(e)}"))
        return 1


def cmd_committees_list(args):
    """Handle 'committees list' command."""
    cache = CacheManager()

    try:
        committee_type = getattr(args, 'type', 'all')
        session = getattr(args, 'session', None)

        # Fetch committees
        committees = list_committees(
            committee_type=committee_type,
            session=session,
            cache_manager=cache
        )

        if not committees:
            print(format_error(f"No committees found for type '{committee_type}'."))
            return 1

        print(format_committees_list(committees))
        return 0

    except Exception as e:
        print(format_error(f"Error listing committees: {str(e)}"))
        return 1


def cmd_search(args):
    """Handle top-level 'search' command (alias for jbc search)."""
    return cmd_jbc_search(args)


def cmd_watch_list(args):
    """Handle 'watch list' command."""
    cache = CacheManager()
    manager = WatchlistManager(cache.get_watchlists_dir())

    try:
        watchlists = manager.list_watchlists()
        print(format_watchlist_list(watchlists))
        return 0
    except Exception as e:
        print(format_error(f"Error listing watchlists: {str(e)}"))
        return 1


def cmd_watch_show(args):
    """Handle 'watch show' command."""
    cache = CacheManager()
    manager = WatchlistManager(cache.get_watchlists_dir())

    try:
        watchlist = manager.get_watchlist(args.name)
        if not watchlist:
            print(format_error(f"Watchlist '{args.name}' not found."))
            return 1

        print(format_watchlist_definition(watchlist))
        return 0
    except Exception as e:
        print(format_error(f"Error showing watchlist: {str(e)}"))
        return 1


def cmd_watch_add(args):
    """Handle 'watch add' command."""
    cache = CacheManager()
    manager = WatchlistManager(cache.get_watchlists_dir())

    try:
        keywords = args.keywords
        departments = getattr(args, 'departments', None) or []
        display_name = getattr(args, 'display_name', None)
        exact = getattr(args, 'exact', False)

        watchlist = manager.create_watchlist(
            name=args.name,
            keywords=keywords,
            departments=departments,
            display_name=display_name,
            exact=exact
        )

        print(f"# Watchlist Created: {watchlist['display_name']}")
        print("")
        print(f"**Name:** `{watchlist['name']}`")
        print(f"**Keywords:** {', '.join(watchlist['keywords'])}")
        if watchlist['departments']:
            print(f"**Departments:** {', '.join(watchlist['departments'])}")
        print("")
        print(f"Run with: `watch run {watchlist['name']}`")

        return 0

    except ValueError as e:
        print(format_error(str(e)))
        return 1
    except Exception as e:
        print(format_error(f"Error creating watchlist: {str(e)}"))
        return 1


def cmd_watch_delete(args):
    """Handle 'watch delete' command."""
    cache = CacheManager()
    manager = WatchlistManager(cache.get_watchlists_dir())

    try:
        if manager.delete_watchlist(args.name):
            print(f"Watchlist '{args.name}' deleted.")
            return 0
        else:
            print(format_error(f"Watchlist '{args.name}' not found."))
            return 1
    except Exception as e:
        print(format_error(f"Error deleting watchlist: {str(e)}"))
        return 1


def cmd_watch_run(args):
    """Handle 'watch run' command."""
    cache = CacheManager()
    manager = WatchlistManager(cache.get_watchlists_dir())

    try:
        new_only = getattr(args, 'new_only', False)

        results = manager.run_watchlist(
            name=args.name,
            cache_manager=cache,
            new_only=new_only
        )

        print(format_watchlist_results(results))

        # Update last_checked if not in new_only mode (or always to track runs)
        manager.update_last_checked(args.name)

        return 0

    except ValueError as e:
        print(format_error(str(e)))
        return 1
    except Exception as e:
        print(format_error(f"Error running watchlist: {str(e)}"))
        return 1


def cmd_bills_list(args):
    """Handle 'bills list' command."""
    cache = CacheManager()

    try:
        session = getattr(args, 'session', None)
        chamber = getattr(args, 'chamber', None)
        bill_type = getattr(args, 'type', None)
        limit = getattr(args, 'limit', 100)

        # Fetch bills
        bills = list_bills(
            session=session,
            chamber=chamber,
            bill_type=bill_type,
            limit=limit,
            cache_manager=cache
        )

        if not bills:
            print(format_error(f"No bills found matching criteria."))
            return 1

        print(format_bills_list(bills, session=session or get_current_session()))
        return 0

    except Exception as e:
        print(format_error(f"Error listing bills: {str(e)}"))
        return 1


def cmd_bill_info(args):
    """Handle 'bill info' command."""
    cache = CacheManager()

    try:
        bill_number = args.bill_number
        session = getattr(args, 'session', None)

        # Fetch bill info
        bill = get_bill_info(
            bill_number=bill_number,
            session=session,
            cache_manager=cache
        )

        if not bill:
            print(format_error(f"Bill '{bill_number}' not found."))
            return 1

        print(format_bill_info(bill))
        return 0

    except Exception as e:
        print(format_error(f"Error fetching bill info: {str(e)}"))
        return 1


def cmd_bills_search(args):
    """Handle 'bills search' command."""
    cache = CacheManager()

    try:
        query = ' '.join(args.query)
        if getattr(args, 'exact', False):
            query = f'"{query}"'
        session = getattr(args, 'session', None)
        chamber = getattr(args, 'chamber', None)
        limit = getattr(args, 'limit', 50)

        # Search bills
        bills = search_bills(
            query=query,
            session=session,
            chamber=chamber,
            limit=limit,
            cache_manager=cache
        )

        if not bills:
            print(format_error(f"No bills found matching '{query}'."))
            return 1

        print(format_bills_list(bills, session=session or get_current_session()))
        return 0

    except Exception as e:
        print(format_error(f"Error searching bills: {str(e)}"))
        return 1


def cmd_extract(args):
    """Handle 'extract' command to extract PDF content."""
    cache = CacheManager()

    try:
        target = args.target
        completed = 0
        total = 0

        def progress_callback(done, total_count, url, from_cache=False):
            nonlocal completed
            completed = done
            source = "cache" if from_cache else "extracting"
            print(f"  [{done}/{total_count}] {source}: {url.split('/')[-1][:60]}...")

        if target == 'documents':
            print("Extracting PDF content from budget documents...")
            department = getattr(args, 'department', None)

            # Fetch documents with content extraction
            documents = fetch_budget_documents(
                cache_manager=cache,
                extract_content=True,
                progress_callback=progress_callback
            )

            if department:
                # Filter by department
                from scrapers.documents import normalize_department
                normalized = normalize_department(department)
                documents = [d for d in documents if d.get('department') == normalized]

            pdf_docs = [d for d in documents if d.get('url', '').lower().endswith('.pdf')]
            print(f"\n✓ Extracted content from {len(pdf_docs)} documents")

            # Show extraction errors if any
            errors = [d for d in pdf_docs if d.get('pdf_error')]
            if errors:
                print(f"\n⚠ {len(errors)} documents had extraction errors:")
                for doc in errors[:5]:  # Show first 5 errors
                    print(f"  - {doc.get('title', 'Unknown')}: {doc.get('pdf_error')}")

        elif target == 'bills':
            print("Extracting PDF content from bills...")
            session = getattr(args, 'session', None) or get_current_session()
            limit = getattr(args, 'limit', 100)

            # Get list of bills
            bills_list = list_bills(session=session, limit=limit, cache_manager=cache)
            print(f"Found {len(bills_list)} bills in session {session}")

            # Extract content from each bill
            total = len(bills_list)
            for i, bill_summary in enumerate(bills_list):
                bill_number = bill_summary.get('bill_number')
                print(f"\n[{i+1}/{total}] Processing {bill_number}...")

                # Get detailed bill info with content extraction
                bill = get_bill_info(
                    bill_number,
                    session=session,
                    cache_manager=cache,
                    extract_content=True,
                    progress_callback=progress_callback
                )

            print(f"\n✓ Extracted content from {total} bills")

        elif target == 'status':
            print("PDF Content Extraction Status\n")

            # Check documents
            docs_with_content = cache.get('budget_documents_with_content', max_age_hours=None)
            docs_without = cache.get('budget_documents', max_age_hours=None)

            if docs_with_content:
                pdf_docs = [d for d in docs_with_content if d.get('url', '').lower().endswith('.pdf')]
                extracted = [d for d in pdf_docs if d.get('pdf_content')]
                print(f"Documents: {len(extracted)}/{len(pdf_docs)} PDFs extracted")
            elif docs_without:
                pdf_docs = [d for d in docs_without if d.get('url', '').lower().endswith('.pdf')]
                print(f"Documents: 0/{len(pdf_docs)} PDFs extracted (run 'extract documents')")
            else:
                print("Documents: No documents cached")

            # Check bills
            bill_count = 0
            extracted_bill_count = 0
            for key in cache.metadata.keys():
                if key.startswith('bill_') and not key.startswith('bills_list_'):
                    bill_count += 1
                    bill = cache.get(key, max_age_hours=None)
                    if bill and bill.get('bill_text'):
                        for version in bill['bill_text']:
                            if version.get('content'):
                                extracted_bill_count += 1
                                break

            print(f"Bills: {extracted_bill_count}/{bill_count} bills with extracted content")

            # Cache usage
            cache_size = sum(
                (cache.base_dir / subdir).stat().st_size
                for subdir in ['bills', 'documents', 'schedules']
                if (cache.base_dir / subdir).exists()
            ) if cache.base_dir.exists() else 0
            print(f"\nCache size: {cache_size / 1024 / 1024:.1f} MB")

        else:
            print(format_error(f"Unknown extraction target: {target}"))
            return 1

        return 0

    except Exception as e:
        print(format_error(f"Error extracting content: {str(e)}"))
        import traceback
        traceback.print_exc()
        return 1


def cmd_transcript_transcribe(args):
    """Handle 'transcript transcribe' command."""
    cache = CacheManager()

    try:
        target = args.target

        # Check if target is a date (YYYY-MM-DD) and resolve to clip_id
        clip_id = target
        if len(target) == 10 and target[4] == '-' and target[7] == '-':
            from scrapers.audio import get_recording_for_date
            recording = get_recording_for_date(target, cache)
            if not recording:
                print(format_error(f"No recording found for date {target}"))
                return 1
            clip_id = recording.get('clip_id')
            print(f"Found recording for {target}: clip {clip_id} - {recording.get('title', '')}")
            print("")

        def progress(msg):
            print(f"  {msg}")

        print(f"Transcribing clip {clip_id}...")
        result = transcribe_recording(clip_id, cache_manager=cache, progress_callback=progress)

        if result.get('error'):
            print(format_error(result['error']))
            return 1

        print("")
        print(f"Transcript saved to cache.")
        print(f"View with: transcript view {clip_id}")
        return 0

    except Exception as e:
        print(format_error(f"Error transcribing: {str(e)}"))
        return 1


def cmd_transcript_view(args):
    """Handle 'transcript view' command."""
    cache = CacheManager()

    try:
        clip_id = args.clip_id
        speaker = getattr(args, 'speaker', None)
        highlight = getattr(args, 'highlight', None)

        transcript = get_transcript(clip_id, cache)
        if not transcript:
            print(format_error(f"No transcript found for clip {clip_id}. "
                             f"Transcribe it first with: transcript transcribe {clip_id}"))
            return 1

        print(format_transcript(transcript, speaker_filter=speaker, highlight_query=highlight))
        return 0

    except Exception as e:
        print(format_error(f"Error viewing transcript: {str(e)}"))
        return 1


def cmd_transcript_list(args):
    """Handle 'transcript list' command."""
    cache = CacheManager()

    try:
        transcripts = list_transcribed_recordings(cache)
        print(format_transcript_list(transcripts))
        return 0

    except Exception as e:
        print(format_error(f"Error listing transcripts: {str(e)}"))
        return 1


def cmd_transcript_status(args):
    """Handle 'transcript status' command."""
    cache = CacheManager()

    try:
        from scrapers.audio import fetch_jbc_recordings

        recordings = fetch_jbc_recordings(cache)
        transcripts = list_transcribed_recordings(cache)
        transcribed_ids = set(t.get('clip_id') for t in transcripts if not t.get('error'))

        print("# Transcript Status")
        print("")

        total = len(recordings)
        done = len(transcribed_ids)
        print(f"**Recordings:** {total}")
        print(f"**Transcribed:** {done}")
        print(f"**Remaining:** {total - done}")
        print("")

        if recordings:
            print("| Date | Title | Clip ID | Transcribed |")
            print("|------|-------|---------|-------------|")

            for rec in recordings[:20]:  # Show first 20
                date = rec.get('date', '—')
                title = rec.get('title', '—')
                if len(title) > 30:
                    title = title[:27] + "..."
                title = title.replace('|', '\\|')
                clip_id = rec.get('clip_id', '—')
                status = "Yes" if clip_id in transcribed_ids else "No"
                print(f"| {date} | {title} | {clip_id} | {status} |")

            print("")

        return 0

    except Exception as e:
        print(format_error(f"Error checking status: {str(e)}"))
        return 1


def cmd_recordings_list(args):
    """Handle 'recordings list' command."""
    cache = CacheManager()

    try:
        committee = getattr(args, 'committee', None)
        since = getattr(args, 'since', None)

        if committee:
            if committee not in PRIORITY_COMMITTEES:
                print(format_error(f"Unknown committee '{committee}'. Use 'recordings list-committees' to see available codes."))
                return 1
            recordings = fetch_committee_recordings(committee, cache_manager=cache, since_date=since)
        else:
            recordings = fetch_all_priority_recordings(cache_manager=cache, since_date=since)

        print(format_recordings_list(recordings, cache_manager=cache, committee_filter=committee))
        return 0

    except Exception as e:
        print(format_error(f"Error listing recordings: {str(e)}"))
        return 1


def cmd_recordings_list_committees(args):
    """Handle 'recordings list-committees' command."""
    print("# Priority Committees")
    print("")
    print("| Code | Committee | SLIQ Category |")
    print("|------|-----------|---------------|")

    for code, info in PRIORITY_COMMITTEES.items():
        name = info['name']
        cat_id = info['category_id']
        print(f"| `{code}` | {name} | {cat_id} |")

    print("")
    print(f"*{len(PRIORITY_COMMITTEES)} committee(s) configured*")
    print("")
    print("Use: `recordings list --committee CODE` to see recordings for a specific committee")
    return 0


def cmd_transcript_transcribe_batch(args):
    """Handle 'transcript transcribe-batch' command."""
    cache = CacheManager()

    try:
        committee = args.committee
        since = getattr(args, 'since', None)

        if committee not in PRIORITY_COMMITTEES:
            print(format_error(f"Unknown committee '{committee}'. Use 'recordings list-committees' to see available codes."))
            return 1

        committee_name = PRIORITY_COMMITTEES[committee]['name']
        recordings = fetch_committee_recordings(committee, cache_manager=cache, since_date=since)

        if not recordings:
            print(f"No recordings found for {committee_name}.")
            return 0

        # Show cost estimate
        est = estimate_cost(recordings, cache_manager=cache)
        print(f"# Batch Transcription - {committee_name}")
        print("")
        print(f"**Recordings:** {est['total']}")
        print(f"**Already transcribed:** {est['already_done']}")
        print(f"**To transcribe:** {est['to_do']}")
        print(f"**Estimated hours:** {est['hours']}")
        print(f"**Estimated cost:** ${est['cost']:.2f}")
        print("")

        if est['to_do'] == 0:
            print("All recordings already transcribed!")
            return 0

        # Proceed with transcription
        print("Starting batch transcription...")
        print("")

        def progress(msg):
            print(f"  {msg}")

        result = batch_transcribe(recordings, cache_manager=cache, progress_callback=progress)

        print("")
        print(f"**Transcribed:** {result['transcribed']}")
        print(f"**Skipped (cached):** {result['skipped']}")
        if result['errors']:
            print(f"**Errors:** {len(result['errors'])}")
            for err in result['errors']:
                print(f"  - {err['title']}: {err['error']}")

        return 0

    except Exception as e:
        print(format_error(f"Error in batch transcription: {str(e)}"))
        return 1


def cmd_transcript_transcribe_all(args):
    """Handle 'transcript transcribe-all' command."""
    cache = CacheManager()

    try:
        since = getattr(args, 'since', None)
        recordings = fetch_all_priority_recordings(cache_manager=cache, since_date=since)

        if not recordings:
            print("No recordings found across priority committees.")
            return 0

        # Show cost estimate
        est = estimate_cost(recordings, cache_manager=cache)
        print("# Batch Transcription - All Priority Committees")
        print("")
        print(f"**Total recordings:** {est['total']}")
        print(f"**Already transcribed:** {est['already_done']}")
        print(f"**To transcribe:** {est['to_do']}")
        print(f"**Estimated hours:** {est['hours']}")
        print(f"**Estimated cost:** ${est['cost']:.2f}")
        print("")

        if est['to_do'] == 0:
            print("All recordings already transcribed!")
            return 0

        # Proceed with transcription
        print("Starting batch transcription...")
        print("")

        def progress(msg):
            print(f"  {msg}")

        result = batch_transcribe(recordings, cache_manager=cache, progress_callback=progress)

        print("")
        print(f"**Transcribed:** {result['transcribed']}")
        print(f"**Skipped (cached):** {result['skipped']}")
        if result['errors']:
            print(f"**Errors:** {len(result['errors'])}")
            for err in result['errors'][:10]:
                print(f"  - {err['title']}: {err['error']}")

        return 0

    except Exception as e:
        print(format_error(f"Error in batch transcription: {str(e)}"))
        return 1


def cmd_transcript_status_all(args):
    """Handle enhanced 'transcript status' showing all priority committees."""
    cache = CacheManager()

    try:
        # Get transcribed clip IDs
        transcripts = list_transcribed_recordings(cache)
        transcribed_ids = set(t.get('clip_id') for t in transcripts if not t.get('error'))

        committees_status = []

        for code, info in PRIORITY_COMMITTEES.items():
            category_id = info['category_id']
            name = info['name']
            cache_key = f"sliq_recordings_{category_id}"
            recordings = cache.get(cache_key, max_age_hours=None) or []

            total = len(recordings)
            done = sum(1 for r in recordings if r.get('clip_id', '') in transcribed_ids)

            # Calculate remaining hours and cost
            remaining_seconds = sum(
                r.get('duration_seconds', 0) or 0
                for r in recordings
                if r.get('clip_id', '') not in transcribed_ids
            )
            remaining_hours = remaining_seconds / 3600.0
            cost = remaining_hours * 0.37

            committees_status.append({
                'name': name,
                'code': code,
                'total': total,
                'transcribed': done,
                'hours': round(remaining_hours, 1),
                'cost': round(cost, 2),
            })

        # Also check Granicus JBC recordings
        granicus_recordings = cache.get('jbc_recordings', max_age_hours=None) or []
        if granicus_recordings:
            granicus_total = len(granicus_recordings)
            granicus_done = sum(1 for r in granicus_recordings if r.get('clip_id', '') in transcribed_ids)
            if granicus_total > 0:
                committees_status.insert(0, {
                    'name': 'JBC (Granicus)',
                    'code': 'granicus_jbc',
                    'total': granicus_total,
                    'transcribed': granicus_done,
                    'hours': 0,  # No duration data from Granicus
                    'cost': 0,
                })

        print(format_transcription_status(committees_status))
        return 0

    except Exception as e:
        print(format_error(f"Error checking status: {str(e)}"))
        return 1


def cmd_transcript_resolve_speakers(args):
    """Handle 'transcript resolve-speakers' command.

    Iterates all cached transcripts, runs utterance splitting on poorly-diarized
    ones, then resolves speaker labels to real names using committee member data.
    """
    cache = CacheManager()

    try:
        from processing.utterance_splitter import is_splitting_candidate, split_utterances

        transcripts = list_transcribed_recordings(cache)
        if not transcripts:
            print("No transcripts found in cache.")
            return 0

        # Build a map from clip_id to committee code using recording metadata
        clip_to_committee = {}
        for code, info in PRIORITY_COMMITTEES.items():
            category_id = info['category_id']
            cache_key = f"sliq_recordings_{category_id}"
            recordings = cache.get(cache_key, max_age_hours=None) or []
            for rec in recordings:
                cid = rec.get('clip_id', '')
                if cid:
                    clip_to_committee[cid] = code

        # Also check Granicus JBC recordings
        granicus_recordings = cache.get('jbc_recordings', max_age_hours=None) or []
        for rec in granicus_recordings:
            cid = rec.get('clip_id', '')
            if cid:
                clip_to_committee[cid] = 'JointBudgetCommittee'

        # Cache committee member lookups to avoid repeated fetches
        committee_members_cache = {}

        total_processed = 0
        total_speakers_resolved = 0
        total_still_unresolved = 0
        total_splits = 0

        print("# Speaker Resolution")
        print("")
        print(f"Processing {len(transcripts)} transcripts...")
        print("")

        for t_info in transcripts:
            clip_id = t_info.get('clip_id', '')
            if not clip_id or t_info.get('error'):
                continue

            transcript = get_transcript(clip_id, cache)
            if not transcript or transcript.get('error'):
                continue

            committee_code = clip_to_committee.get(clip_id)
            if not committee_code:
                print(f"  [{clip_id}] Skipped — no committee mapping found")
                continue

            # Strip _House/_Senate suffix for committee slug lookup
            committee_slug = committee_code.replace('_House', '').replace('_Senate', '')

            # Get committee members (cached)
            if committee_slug not in committee_members_cache:
                try:
                    committee_info = get_committee_info(committee_slug, cache_manager=cache)
                    if committee_info:
                        committee_members_cache[committee_slug] = {
                            'members': committee_info.get('members', []),
                            'name': committee_info.get('name', committee_slug),
                        }
                    else:
                        committee_members_cache[committee_slug] = {'members': [], 'name': committee_slug}
                except Exception:
                    committee_members_cache[committee_slug] = {'members': [], 'name': committee_slug}

            members = committee_members_cache[committee_slug]['members']
            committee_name = committee_members_cache[committee_slug]['name']

            # Step 1: Run utterance splitting on poorly-diarized transcripts
            split_stats = None
            if is_splitting_candidate(transcript):
                split_stats = split_utterances(transcript)
                total_splits += split_stats.get('splits_made', 0)

            # Step 2: Resolve speakers
            speaker_map = resolve_and_store_speakers(
                clip_id, committee_name, members, cache
            )

            resolved = sum(1 for v in speaker_map.values() if v.get('name'))
            unique_speakers = set(u.get('speaker', '') for u in transcript.get('utterances', []))
            unresolved = len(unique_speakers) - resolved

            total_processed += 1
            total_speakers_resolved += resolved
            total_still_unresolved += max(0, unresolved)

            # Report
            status_parts = []
            if split_stats and split_stats['splits_made'] > 0:
                status_parts.append(
                    f"split {split_stats['utterances_before']}→{split_stats['utterances_after']} utterances"
                )
            if resolved > 0:
                names = [v['display'] for v in speaker_map.values() if v.get('display')]
                status_parts.append(f"resolved {resolved}: {', '.join(names[:5])}")
            if not status_parts:
                status_parts.append("no speakers resolved")

            print(f"  [{clip_id}] {'; '.join(status_parts)}")

        print("")
        print("## Summary")
        print(f"- **Transcripts processed:** {total_processed}")
        print(f"- **Speakers resolved:** {total_speakers_resolved}")
        print(f"- **Still unresolved:** {total_still_unresolved}")
        if total_splits > 0:
            print(f"- **Utterance splits:** {total_splits}")
        return 0

    except Exception as e:
        print(format_error(f"Error resolving speakers: {str(e)}"))
        import traceback
        traceback.print_exc()
        return 1


def cmd_report(args):
    """Handle 'report' command - generate advocacy HTML report."""
    cache = CacheManager()

    try:
        # Build query string preserving quoted phrases
        # Re-quote multi-word args only if they don't already contain quotes
        # (shell strips outer quotes but inner quotes survive)
        parts = []
        for kw in args.keywords:
            if ' ' in kw and '"' not in kw:
                parts.append(f'"{kw}"')
            else:
                parts.append(kw)
        keywords = ' '.join(parts)

        # Compute since_date
        if hasattr(args, 'since') and args.since:
            since_date = args.since
        else:
            days = getattr(args, 'days', 60) or 60
            from datetime import timedelta
            since_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        # Run search
        results = search_all(query=keywords, cache_manager=cache)

        # Filter by date
        results = filter_results_since(results, since_date)

        # Collect committee member data for recordings
        committee_members = {}
        seen_slugs = set()
        for rec in results.get('recordings', []):
            slug = rec.get('committee', '')
            cname = rec.get('committee_name', '')
            if slug and slug not in seen_slugs:
                seen_slugs.add(slug)
                try:
                    # Strip _House/_Senate suffixes for lookup
                    lookup_slug = slug
                    for suffix in ('_House', '_Senate'):
                        if lookup_slug.endswith(suffix):
                            lookup_slug = lookup_slug[:-len(suffix)]
                            break
                    info = get_committee_info(lookup_slug, cache_manager=cache)
                    if info and info.get('members'):
                        committee_members[cname] = info['members']
                except Exception:
                    pass

        # Resolve speaker labels in transcript excerpt strings
        for rec in results.get('recordings', []):
            clip_id = rec.get('clip_id', '')
            committee_name = rec.get('committee_name', '')
            contexts = rec.get('match_context', [])
            if not clip_id or not contexts or not isinstance(contexts, list):
                continue
            members = committee_members.get(committee_name, [])
            if not members:
                continue
            transcript = get_transcript(clip_id, cache_manager=cache)
            if not transcript:
                continue
            speaker_map = resolve_speakers(transcript, members)
            if not speaker_map:
                continue
            new_contexts = []
            for ctx in contexts:
                for label, info in speaker_map.items():
                    ctx = ctx.replace(f'[Speaker {label},', f'[{info["display"]},')
                new_contexts.append(ctx)
            rec['match_context'] = new_contexts

        # Build champion data from resolved speakers + full transcripts
        pattern = build_search_pattern(keywords)
        champions_agg = {}  # keyed by legislator name
        for rec in results.get('recordings', []):
            clip_id = rec.get('clip_id', '')
            committee_name = rec.get('committee_name', '')
            if not clip_id:
                continue
            members = committee_members.get(committee_name, [])
            if not members:
                continue
            transcript = get_transcript(clip_id, cache_manager=cache)
            if not transcript:
                continue
            speaker_map = resolve_speakers(transcript, members)
            if not speaker_map:
                continue
            # Scan all utterances for keyword mentions by resolved speakers
            for utt in transcript.get('utterances', []):
                spk = utt.get('speaker', '')
                if spk not in speaker_map:
                    continue
                text = utt.get('text', '')
                matches = pattern.findall(text) if pattern else []
                if not matches:
                    continue
                info = speaker_map[spk]
                name = info['name']
                if name not in champions_agg:
                    member = None
                    for m in members:
                        if m.get('name') == name:
                            member = m
                            break
                    champions_agg[name] = {
                        'name': name,
                        'display': info['display'],
                        'role': member.get('role', 'Member') if member else 'Member',
                        'chamber': member.get('chamber', '') if member else '',
                        'committee': committee_name,
                        'mention_count': 0,
                        'sample_quotes': [],
                    }
                champions_agg[name]['mention_count'] += len(matches)
                # Collect up to 2 sample quotes per champion
                if len(champions_agg[name]['sample_quotes']) < 2:
                    ts = format_timestamp(utt.get('start', 0))
                    match = pattern.search(text)
                    if match and len(text) > 200:
                        start_pos = max(0, match.start() - 75)
                        end_pos = min(len(text), match.end() + 75)
                        snippet = text[start_pos:end_pos]
                        if start_pos > 0:
                            snippet = "..." + snippet
                        if end_pos < len(text):
                            snippet = snippet + "..."
                    else:
                        snippet = text[:200] + ("..." if len(text) > 200 else "")
                    snippet = highlight_matches(snippet, pattern)
                    champions_agg[name]['sample_quotes'].append(f"[{ts}] {snippet}")

        # Sort by mention count, take top 8
        champions = sorted(champions_agg.values(), key=lambda x: x['mention_count'], reverse=True)[:8]

        # Generate HTML report
        report_html = format_advocacy_report_html(results, keywords, since_date, committee_members=committee_members, champions=champions)

        # Save to file
        reports_dir = Path(cache.base_dir) / 'reports'
        reports_dir.mkdir(parents=True, exist_ok=True)
        filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        filepath = reports_dir / filename
        filepath.write_text(report_html, encoding='utf-8')

        print(f"Report saved to: {filepath}")
        print(f"Results: {results['total_count']} matches ({len(results.get('bills', []))} bills, "
              f"{len(results.get('recordings', []))} hearings, "
              f"{len(results.get('documents', []))} documents, "
              f"{len(results.get('schedules', []))} schedule items)")

        # Open in browser if requested
        if getattr(args, 'open', False):
            import subprocess
            subprocess.run(['open', str(filepath)])

        return 0

    except Exception as e:
        print(format_error(f"Error generating report: {str(e)}"))
        return 1


def cmd_version(args):
    """Handle 'version' command."""
    print("Colorado Legislature Monitor v0.9.0 (Phase 9 - Advocacy Reports & Champion Identification)")
    print(f"Current session: {get_current_session()}")
    print(f"Current week: {get_current_week_number()}")
    return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Colorado Legislature Monitoring Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Get JBC schedule for current week (with media and documents)
  legislature.py jbc schedule --week current

  # Get JBC schedule for next week
  legislature.py jbc schedule --week next

  # Get JBC schedule for specific week number (without media/docs columns)
  legislature.py jbc schedule --week 5 --no-media --no-docs

  # List JBC recordings for a specific week
  legislature.py jbc recordings --week 2

  # Get budget documents for a department
  legislature.py jbc documents --department corrections

  # List all departments with documents
  legislature.py jbc documents --list-departments

  # Search across all cached data
  legislature.py jbc search "food assistance"
  legislature.py jbc search "budget" --type schedules
  legislature.py jbc search "corrections" --department corrections

  # Watchlists
  legislature.py watch list
  legislature.py watch run snap
  legislature.py watch run snap --new-only
  legislature.py watch add housing --keywords "housing" "affordable"
  legislature.py watch show housing
  legislature.py watch delete housing

  # Committees
  legislature.py committees --type year-round
  legislature.py committees --type session-only
  legislature.py committees --type all
  legislature.py committee info JointBudgetCommittee
  legislature.py committee info AgricultureWaterNaturalResources --session 2026A

  # Show version info
  legislature.py version
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # JBC command
    jbc_parser = subparsers.add_parser('jbc', help='Joint Budget Committee commands')
    jbc_subparsers = jbc_parser.add_subparsers(dest='jbc_command')

    # JBC schedule subcommand
    schedule_parser = jbc_subparsers.add_parser('schedule', help='Get JBC schedule')
    schedule_parser.add_argument(
        '--week',
        default='current',
        help='Week to fetch (current, next, or week number 1-52)'
    )
    schedule_parser.add_argument(
        '--no-media',
        action='store_true',
        help='Exclude audio/video links from output'
    )
    schedule_parser.add_argument(
        '--no-docs',
        action='store_true',
        help='Exclude document links from output'
    )

    # JBC recordings subcommand
    recordings_parser = jbc_subparsers.add_parser('recordings', help='List JBC recordings')
    recordings_parser.add_argument(
        '--week',
        help='Week to show (current, next, or week number 1-52)'
    )
    recordings_parser.add_argument(
        '--date',
        help='Specific date (YYYY-MM-DD format)'
    )

    # JBC documents subcommand
    documents_parser = jbc_subparsers.add_parser('documents', help='List budget documents')
    documents_parser.add_argument(
        '--department',
        help='Filter by department name'
    )
    documents_parser.add_argument(
        '--type',
        choices=['briefing', 'figure_setting', 'request', 'decision', 'summary', 'overview', 'analysis', 'other'],
        help='Filter by document type'
    )
    documents_parser.add_argument(
        '--list-departments',
        action='store_true',
        help='List all departments with available documents'
    )

    # JBC search subcommand
    jbc_search_parser = jbc_subparsers.add_parser('search', help='Search across all cached data')
    jbc_search_parser.add_argument('query', nargs='+', help='Search query (use --exact for phrase match)')
    jbc_search_parser.add_argument('--exact', action='store_true', help='Match exact phrase instead of individual words')
    jbc_search_parser.add_argument(
        '--type',
        choices=['schedules', 'recordings', 'documents', 'bills'],
        help='Limit search to specific data type'
    )
    jbc_search_parser.add_argument(
        '--department',
        help='Filter by department name'
    )
    jbc_search_parser.add_argument(
        '--chamber',
        choices=['House', 'Senate'],
        help='Filter bills by chamber'
    )
    jbc_search_parser.add_argument(
        '--format',
        choices=['markdown', 'html'],
        default='markdown',
        help='Output format (default: markdown)'
    )

    # Watch command (watchlists)
    watch_parser = subparsers.add_parser('watch', help='Watchlist commands')
    watch_subparsers = watch_parser.add_subparsers(dest='watch_command')

    # watch list
    watch_subparsers.add_parser('list', help='List all watchlists')

    # watch show <name>
    watch_show_parser = watch_subparsers.add_parser('show', help='Show watchlist details')
    watch_show_parser.add_argument('name', help='Watchlist name')

    # watch add <name> --keywords ... --departments ...
    watch_add_parser = watch_subparsers.add_parser('add', help='Create a new watchlist')
    watch_add_parser.add_argument('name', help='Watchlist name (lowercase, no spaces)')
    watch_add_parser.add_argument(
        '--keywords',
        nargs='+',
        required=True,
        help='Keywords to search for'
    )
    watch_add_parser.add_argument(
        '--departments',
        nargs='+',
        help='Departments to filter (optional)'
    )
    watch_add_parser.add_argument(
        '--display-name',
        help='Human-readable display name'
    )
    watch_add_parser.add_argument(
        '--exact',
        action='store_true',
        help='Treat keywords as an exact phrase'
    )

    # watch delete <name>
    watch_delete_parser = watch_subparsers.add_parser('delete', help='Delete a watchlist')
    watch_delete_parser.add_argument('name', help='Watchlist name')

    # watch run <name>
    watch_run_parser = watch_subparsers.add_parser('run', help='Run a watchlist query')
    watch_run_parser.add_argument('name', help='Watchlist name')
    watch_run_parser.add_argument(
        '--new-only',
        action='store_true',
        help='Only show results since last check'
    )

    # Committee command
    committee_parser = subparsers.add_parser('committee', help='Committee commands')
    committee_subparsers = committee_parser.add_subparsers(dest='committee_command')

    info_parser = committee_subparsers.add_parser('info', help='Get committee info')
    info_parser.add_argument('name', help='Committee slug (e.g., JointBudgetCommittee)')
    info_parser.add_argument('--session', help='Session code (e.g., 2026A). Defaults to current session.')

    # Committees list command
    list_parser = subparsers.add_parser('committees', help='List committees')
    list_parser.add_argument(
        '--type',
        default='all',
        choices=['all', 'year-round', 'session-only', 'house', 'senate', 'interim', 'other'],
        help='Committee type to list'
    )
    list_parser.add_argument('--session', help='Session code (e.g., 2026A). Defaults to current session.')

    # Top-level search command (alias for jbc search)
    search_parser = subparsers.add_parser('search', help='Search across all data (alias for jbc search)')
    search_parser.add_argument('query', nargs='+', help='Search query (use --exact for phrase match)')
    search_parser.add_argument('--exact', action='store_true', help='Match exact phrase instead of individual words')
    search_parser.add_argument(
        '--type',
        choices=['schedules', 'recordings', 'documents', 'bills'],
        help='Limit search to specific data type'
    )
    search_parser.add_argument(
        '--department',
        help='Filter by department name'
    )
    search_parser.add_argument(
        '--chamber',
        choices=['House', 'Senate'],
        help='Filter bills by chamber'
    )
    search_parser.add_argument(
        '--format',
        choices=['markdown', 'html'],
        default='markdown',
        help='Output format (default: markdown)'
    )

    # Bills command
    bills_parser = subparsers.add_parser('bills', help='Bill commands')
    bills_subparsers = bills_parser.add_subparsers(dest='bills_command')

    # bills list
    bills_list_parser = bills_subparsers.add_parser('list', help='List bills')
    bills_list_parser.add_argument('--session', help='Session code (e.g., 2026A). Defaults to current session.')
    bills_list_parser.add_argument('--chamber', choices=['House', 'Senate'], help='Filter by chamber')
    bills_list_parser.add_argument('--type', choices=['Bill', 'Resolution', 'Memorial'], help='Filter by bill type')
    bills_list_parser.add_argument('--limit', type=int, default=100, help='Maximum number of bills to return (default: 100)')

    # bills search
    bills_search_parser = bills_subparsers.add_parser('search', help='Search bills by keyword')
    bills_search_parser.add_argument('query', nargs='+', help='Search query (use --exact for phrase match)')
    bills_search_parser.add_argument('--exact', action='store_true', help='Match exact phrase instead of individual words')
    bills_search_parser.add_argument('--session', help='Session code (e.g., 2026A). Defaults to current session.')
    bills_search_parser.add_argument('--chamber', choices=['House', 'Senate'], help='Filter by chamber')
    bills_search_parser.add_argument('--limit', type=int, default=50, help='Maximum number of results (default: 50)')

    # Bill info command (singular)
    bill_parser = subparsers.add_parser('bill', help='Bill commands')
    bill_subparsers = bill_parser.add_subparsers(dest='bill_command')

    # bill info
    bill_info_parser = bill_subparsers.add_parser('info', help='Get detailed bill information')
    bill_info_parser.add_argument('bill_number', help='Bill number (e.g., HB26-1001, SB26-004)')
    bill_info_parser.add_argument('--session', help='Session code (e.g., 2026A). Defaults to current session.')

    # Extract command (PDF content extraction)
    extract_parser = subparsers.add_parser('extract', help='Extract PDF content for search')
    extract_parser.add_argument(
        'target',
        choices=['documents', 'bills', 'status'],
        help='What to extract (documents, bills, or show status)'
    )
    extract_parser.add_argument(
        '--department',
        help='Filter documents by department'
    )
    extract_parser.add_argument(
        '--session',
        help='Session code for bills (e.g., 2026A). Defaults to current session.'
    )
    extract_parser.add_argument(
        '--limit',
        type=int,
        default=100,
        help='Maximum number of bills to extract (default 100)'
    )

    # Recordings command (SLIQ multi-committee)
    recordings_parser = subparsers.add_parser('recordings', help='Committee recording commands (SLIQ)')
    recordings_subparsers = recordings_parser.add_subparsers(dest='recordings_command')

    # recordings list
    recordings_list_parser = recordings_subparsers.add_parser('list', help='List recordings from priority committees')
    recordings_list_parser.add_argument(
        '--committee', help='Committee code (use list-committees to see codes)')
    recordings_list_parser.add_argument(
        '--since', help='Start date YYYY-MM-DD (default: 2025-08-01)')

    # recordings list-committees
    recordings_subparsers.add_parser('list-committees', help='Show priority committees with codes')

    # Transcript command
    transcript_parser = subparsers.add_parser('transcript', help='Transcript commands (AssemblyAI)')
    transcript_subparsers = transcript_parser.add_subparsers(dest='transcript_command')

    # transcript transcribe
    transcript_transcribe_parser = transcript_subparsers.add_parser(
        'transcribe', help='Transcribe a recording (requires ASSEMBLYAI_API_KEY)')
    transcript_transcribe_parser.add_argument(
        'target', help='Clip ID or date (YYYY-MM-DD) of recording to transcribe')

    # transcript transcribe-batch
    transcript_batch_parser = transcript_subparsers.add_parser(
        'transcribe-batch', help='Batch transcribe all recordings for a committee')
    transcript_batch_parser.add_argument(
        '--committee', required=True, help='Committee code (use recordings list-committees)')
    transcript_batch_parser.add_argument(
        '--since', help='Start date YYYY-MM-DD (default: 2025-08-01)')

    # transcript transcribe-all
    transcript_all_parser = transcript_subparsers.add_parser(
        'transcribe-all', help='Batch transcribe all priority committee recordings')
    transcript_all_parser.add_argument(
        '--since', help='Start date YYYY-MM-DD (default: 2025-08-01)')

    # transcript view
    transcript_view_parser = transcript_subparsers.add_parser('view', help='View a cached transcript')
    transcript_view_parser.add_argument('clip_id', help='Clip ID of the transcript')
    transcript_view_parser.add_argument(
        '--speaker', help='Filter to a specific speaker (e.g., A, B)')
    transcript_view_parser.add_argument(
        '--highlight', help='Highlight a query in the transcript text')

    # transcript list
    transcript_subparsers.add_parser('list', help='List transcribed recordings')

    # transcript status
    transcript_subparsers.add_parser('status', help='Show transcript status for all recordings')

    # transcript resolve-speakers
    transcript_subparsers.add_parser(
        'resolve-speakers',
        help='Batch resolve speaker labels to real names in all cached transcripts'
    )

    # Report command (advocacy HTML report)
    report_parser = subparsers.add_parser('report', help='Generate advocacy HTML report')
    report_parser.add_argument('keywords', nargs='+', help='Search keywords (quote phrases: "Nutrition Assistance")')
    report_parser.add_argument(
        '--days', type=int, default=60,
        help='Number of days to look back (default: 60)')
    report_parser.add_argument(
        '--since', help='Start date YYYY-MM-DD (overrides --days)')
    report_parser.add_argument(
        '--open', action='store_true',
        help='Open report in browser after generating')

    # Version command
    subparsers.add_parser('version', help='Show version info')

    # Parse arguments
    args = parser.parse_args()

    # Route to command handlers
    if not args.command:
        parser.print_help()
        return 1

    if args.command == 'jbc':
        if args.jbc_command == 'schedule':
            return cmd_jbc_schedule(args)
        elif args.jbc_command == 'recordings':
            return cmd_jbc_recordings(args)
        elif args.jbc_command == 'documents':
            return cmd_jbc_documents(args)
        elif args.jbc_command == 'search':
            return cmd_jbc_search(args)
        else:
            jbc_parser.print_help()
            return 1
    elif args.command == 'watch':
        if args.watch_command == 'list':
            return cmd_watch_list(args)
        elif args.watch_command == 'show':
            return cmd_watch_show(args)
        elif args.watch_command == 'add':
            return cmd_watch_add(args)
        elif args.watch_command == 'delete':
            return cmd_watch_delete(args)
        elif args.watch_command == 'run':
            return cmd_watch_run(args)
        else:
            watch_parser.print_help()
            return 1
    elif args.command == 'committee':
        return cmd_committee_info(args)
    elif args.command == 'committees':
        return cmd_committees_list(args)
    elif args.command == 'bills':
        if args.bills_command == 'list':
            return cmd_bills_list(args)
        elif args.bills_command == 'search':
            return cmd_bills_search(args)
        else:
            bills_parser.print_help()
            return 1
    elif args.command == 'bill':
        if args.bill_command == 'info':
            return cmd_bill_info(args)
        else:
            bill_parser.print_help()
            return 1
    elif args.command == 'search':
        return cmd_search(args)
    elif args.command == 'extract':
        return cmd_extract(args)
    elif args.command == 'recordings':
        if args.recordings_command == 'list':
            return cmd_recordings_list(args)
        elif args.recordings_command == 'list-committees':
            return cmd_recordings_list_committees(args)
        else:
            recordings_parser.print_help()
            return 1
    elif args.command == 'transcript':
        if args.transcript_command == 'transcribe':
            return cmd_transcript_transcribe(args)
        elif args.transcript_command == 'transcribe-batch':
            return cmd_transcript_transcribe_batch(args)
        elif args.transcript_command == 'transcribe-all':
            return cmd_transcript_transcribe_all(args)
        elif args.transcript_command == 'view':
            return cmd_transcript_view(args)
        elif args.transcript_command == 'list':
            return cmd_transcript_list(args)
        elif args.transcript_command == 'status':
            return cmd_transcript_status_all(args)
        elif args.transcript_command == 'resolve-speakers':
            return cmd_transcript_resolve_speakers(args)
        else:
            transcript_parser.print_help()
            return 1
    elif args.command == 'report':
        return cmd_report(args)
    elif args.command == 'version':
        return cmd_version(args)
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
