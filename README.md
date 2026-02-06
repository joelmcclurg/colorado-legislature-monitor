# Colorado Legislature Monitor

A command-line tool for monitoring the Colorado General Assembly. Tracks committee schedules, bills, recordings, transcripts, and budget documents -- with cross-data search and automated watchlists.

Built to help policy advocates stay on top of legislative activity without manually checking dozens of web pages.

**Version**: 0.8.0
**Current Session**: 2026A

## What It Does

- **JBC Schedules** - Weekly Joint Budget Committee meeting schedules with linked recordings and budget documents
- **Multi-Committee Recordings** - Audio/video from 6 priority committees via SLIQ (JBC, House/Senate Health & Human Services, House/Senate Agriculture, Joint Technology)
- **AI Transcription** - Transcribe committee recordings with speaker diarization using AssemblyAI
- **Bill Tracking** - Full bill details: sponsors, status, amendments, votes, bill text versions
- **Committee Info** - All year-round, session-only, and interim committees with member lists
- **Cross-Data Search** - Search across schedules, recordings, documents, bills, and transcripts with a single query
- **Phrase Search** - Use `"quoted phrases"` to find exact matches (e.g., `"food assistance"`)
- **Watchlists** - Automated keyword monitoring with "new only" filtering

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/joelmcclurg/colorado-legislature-monitor.git
cd colorado-legislature-monitor
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

**Requires Python 3.9+**

### 3. Set up API key (optional, for transcription only)

Create a `.env` file in the project root:

```
ASSEMBLYAI_API_KEY=your_key_here
```

Get a key at [assemblyai.com](https://www.assemblyai.com/). This is only needed for the `transcript` commands. All other features work without it.

## Quick Start

```bash
# See this week's JBC schedule
python scripts/legislature.py jbc schedule --week current

# List recent bills
python scripts/legislature.py bills list --limit 10

# Get details on a specific bill
python scripts/legislature.py bill info HB26-1001

# Search across all data for a topic
python scripts/legislature.py search "housing"

# Search for an exact phrase
python scripts/legislature.py search '"food assistance"'

# Check version
python scripts/legislature.py version
```

## Commands

### JBC (Joint Budget Committee)

```bash
# Weekly schedule (current, next, or week number)
python scripts/legislature.py jbc schedule --week current
python scripts/legislature.py jbc schedule --week next
python scripts/legislature.py jbc schedule --week 5

# Minimal output (no media/docs columns)
python scripts/legislature.py jbc schedule --week 5 --no-media --no-docs

# JBC recordings (Granicus)
python scripts/legislature.py jbc recordings
python scripts/legislature.py jbc recordings --week 3

# Budget documents by department
python scripts/legislature.py jbc documents --department corrections
python scripts/legislature.py jbc documents --list-departments
```

### Multi-Committee Recordings (SLIQ)

```bash
# List available committees and their codes
python scripts/legislature.py recordings list-committees

# List recordings for a specific committee
python scripts/legislature.py recordings list --committee jbc
python scripts/legislature.py recordings list --committee house-hhs --since 2026-01-01

# Priority committees:
#   jbc           - Joint Budget Committee
#   house-hhs     - House Health & Human Services
#   senate-hhs    - Senate Health & Human Services
#   joint-tech    - Joint Technology Committee
#   house-ag      - House Agriculture, Water & Natural Resources
#   senate-ag     - Senate Agriculture & Natural Resources
```

### Transcription (requires AssemblyAI key)

```bash
# Transcribe a single recording by clip ID
python scripts/legislature.py transcript transcribe CLIP_ID

# View a transcript
python scripts/legislature.py transcript view CLIP_ID

# Batch transcribe all recordings for a committee
python scripts/legislature.py transcript transcribe-batch --committee jbc

# Batch transcribe all priority committees
python scripts/legislature.py transcript transcribe-all

# Check transcription coverage
python scripts/legislature.py transcript status
```

### Bills & Legislation

```bash
# List bills (with optional filters)
python scripts/legislature.py bills list --limit 20
python scripts/legislature.py bills list --chamber House

# Bill details
python scripts/legislature.py bill info HB26-1001
python scripts/legislature.py bill info SB26-004

# Search bills by keyword
python scripts/legislature.py bills search "education"
```

### Committees

```bash
# List committees by type
python scripts/legislature.py committees --type year-round
python scripts/legislature.py committees --type session-only
python scripts/legislature.py committees --type all

# Committee details (members, leadership)
python scripts/legislature.py committee info JointBudgetCommittee
```

### Search

```bash
# Search across all data types
python scripts/legislature.py search "housing"

# Search specific data type
python scripts/legislature.py search "budget" --type schedules
python scripts/legislature.py search "education" --type bills

# Exact phrase search
python scripts/legislature.py search '"food assistance"'
```

### Watchlists

```bash
# Create a watchlist
python scripts/legislature.py watch add snap --keywords "SNAP" "food assistance" --display-name "SNAP Benefits"

# List all watchlists
python scripts/legislature.py watch list

# Run a watchlist (all results)
python scripts/legislature.py watch run snap

# Run watchlist (new items only since last check)
python scripts/legislature.py watch run snap --new-only

# Delete a watchlist
python scripts/legislature.py watch delete snap
```

## Data Sources

| Source | URL | Method |
|--------|-----|--------|
| JBC Schedules | content.leg.colorado.gov | PDF parsing |
| JBC Recordings | coloradoga.granicus.com | HTML scraping |
| Committee Recordings | sg001-harmony.sliq.net | JSON API |
| Budget Documents | content.leg.colorado.gov/content/budget | HTML scraping |
| Committees | leg.colorado.gov/committees | HTML scraping |
| Bills | leg.colorado.gov/bills | HTML scraping |

All data is sourced from public Colorado General Assembly websites. There is no public API; all data is scraped from HTML and PDFs.

## Caching

Data is cached locally in the `data/` directory to minimize requests:

| Data Type | Cache Duration |
|-----------|----------------|
| Current week schedule | Always fresh |
| Historical schedules | Permanent |
| Current recordings | 1 hour |
| Historical recordings | Permanent |
| Budget documents | 6 hours |
| Committee lists | 24 hours |
| Bills | 6 hours |
| Transcripts | Permanent |

Clear all cached data:
```bash
rm -rf data/
```

## Project Structure

```
colorado-legislature-monitor/
├── SKILL.md                    # Claude Code skill definition
├── README.md                   # This file
├── requirements.txt            # Python dependencies
├── scripts/
│   ├── legislature.py          # Main CLI entry point
│   ├── scrapers/
│   │   ├── schedules.py        # JBC PDF schedule parser
│   │   ├── sessions.py         # Session year helper
│   │   ├── audio.py            # Granicus audio/video scraper
│   │   ├── sliq.py             # SLIQ API client (multi-committee)
│   │   ├── documents.py        # Budget document scraper
│   │   ├── committees.py       # Committee scraper
│   │   ├── bills.py            # Bills/legislation scraper
│   │   ├── search.py           # Cross-data search engine
│   │   ├── watchlist.py        # Watchlist manager
│   │   └── transcripts.py      # AssemblyAI transcription
│   ├── cache/
│   │   └── manager.py          # Caching with TTL strategies
│   └── formatters/
│       ├── markdown.py         # CLI output formatting
│       └── html.py             # HTML report export
├── docs/                       # Additional documentation
└── data/                       # Cached data (gitignored)
```

## Using with Claude Code (Optional)

This tool was originally built as a [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skill. If you use Claude Code, you can install it as a skill:

1. Copy or symlink this repo to `~/.claude/skills/colorado-legislature/`
2. Claude will automatically detect the `SKILL.md` and invoke the tool when you ask questions like:
   - "What's on the JBC agenda this week?"
   - "Show me bills about housing"
   - "Create a watchlist for SNAP benefits"

## Dependencies

- **requests** (>=2.31.0) - HTTP requests
- **beautifulsoup4** (>=4.12.0) - HTML parsing
- **lxml** (>=5.1.0) - Parser backend
- **pdfplumber** (>=0.11.0) - PDF text extraction
- **python-dateutil** (>=2.8.0) - Date parsing
- **assemblyai** (>=0.37.0) - Audio transcription (optional)

## License

For personal and educational use. Data sourced from colorado.leg.gov (public domain).

## Credits

- **Data Source**: Colorado General Assembly (colorado.leg.gov)
- **Built with**: [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- **Transcription**: AssemblyAI

---

**Last Updated**: February 5, 2026
