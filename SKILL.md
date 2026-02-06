---
name: colorado-legislature
description: Monitor Colorado legislature committees, bills, schedules, recordings, and budget documents. Features multi-committee audio/video via SLIQ, AI transcription with speaker diarization, cross-data search with phrase matching, automated watchlists, and advocacy HTML reports with champion identification. Use when user asks about committee meetings, bills, legislative schedules, budget items, Colorado legislators, or state legislature activities.
allowed-tools: ["Bash(python *)", "Read", "Write"]
---

# Colorado Legislature Monitor

A comprehensive monitoring tool for the Colorado Legislature. Tracks JBC activities, 6 priority committees, bills, recordings, transcripts, and budget documents -- with cross-data search, watchlists, and advocacy reports.

**Version**: 0.9.0
**Current Session**: 2026A (2026 Regular Session)

## Capabilities

- **JBC Schedules** - Weekly meeting schedules with linked recordings and budget documents
- **Multi-Committee Recordings** - Audio/video from 6 priority committees via SLIQ API (JBC, House/Senate Health & Human Services, House/Senate Agriculture, Joint Technology)
- **AI Transcription** - Transcribe recordings with speaker diarization via AssemblyAI; batch transcription across committees
- **Bill Tracking** - Full bill details: sponsors, status, amendments, votes, bill text versions, fiscal notes
- **Committee Info** - All year-round, session-only, and interim committees with member lists and leadership
- **Cross-Data Search** - Search across schedules, recordings, documents, bills, and transcripts with a single query
- **Phrase Search** - Use `"quoted phrases"` to find exact matches (e.g., `"food assistance"`)
- **Watchlists** - Automated keyword monitoring with "new only" filtering
- **Advocacy Reports** - HTML reports with executive summary, possible champions (identified from transcript speaker data), bill tracking, hearing mentions, and strategic next steps

## Usage

### JBC Schedule

**User Query Examples:**
- "What's on the JBC agenda this week?"
- "Show me the JBC schedule for next week"

**Commands:**
```bash
# Current week schedule with media and documents
python ~/.claude/skills/colorado-legislature/scripts/legislature.py jbc schedule --week current

# Next week schedule
python ~/.claude/skills/colorado-legislature/scripts/legislature.py jbc schedule --week next

# Specific week (minimal format)
python ~/.claude/skills/colorado-legislature/scripts/legislature.py jbc schedule --week 5 --no-media --no-docs
```

### JBC Recordings

**User Query Examples:**
- "Show me recent JBC recordings"
- "What videos are available for JBC meetings?"

**Commands:**
```bash
# All recent recordings
python ~/.claude/skills/colorado-legislature/scripts/legislature.py jbc recordings

# Recordings for specific week
python ~/.claude/skills/colorado-legislature/scripts/legislature.py jbc recordings --week 3
```

### Budget Documents

**User Query Examples:**
- "Show me budget documents for corrections"
- "What departments have budget briefings?"

**Commands:**
```bash
# All budget documents
python ~/.claude/skills/colorado-legislature/scripts/legislature.py jbc documents

# Documents for specific department
python ~/.claude/skills/colorado-legislature/scripts/legislature.py jbc documents --department education

# List all departments
python ~/.claude/skills/colorado-legislature/scripts/legislature.py jbc documents --list-departments
```

### Multi-Committee Recordings (SLIQ)

**User Query Examples:**
- "Show me Health & Human Services committee recordings"
- "What committees have recordings available?"
- "List recent agriculture committee hearings"

**Commands:**
```bash
# List available committees and their codes
python ~/.claude/skills/colorado-legislature/scripts/legislature.py recordings list-committees

# List recordings for a specific committee
python ~/.claude/skills/colorado-legislature/scripts/legislature.py recordings list --committee jbc
python ~/.claude/skills/colorado-legislature/scripts/legislature.py recordings list --committee house-hhs --since 2026-01-01
```

**Priority Committees:**
| Code | Committee | SLIQ ID |
|------|-----------|---------|
| jbc | Joint Budget Committee | 54 |
| house-hhs | House Health & Human Services | 28 |
| senate-hhs | Senate Health & Human Services | 40 |
| joint-tech | Joint Technology Committee | 65 |
| house-ag | House Agriculture, Water & Natural Resources | 32 |
| senate-ag | Senate Agriculture & Natural Resources | 36 |

### Transcription

Requires `ASSEMBLYAI_API_KEY` environment variable or `.env` file.

**User Query Examples:**
- "Transcribe the latest JBC recording"
- "How much transcription coverage do we have?"
- "Transcribe all Health & Human Services recordings"

**Commands:**
```bash
# Transcribe a single recording by clip ID
python ~/.claude/skills/colorado-legislature/scripts/legislature.py transcript transcribe CLIP_ID

# View a transcript
python ~/.claude/skills/colorado-legislature/scripts/legislature.py transcript view CLIP_ID

# Batch transcribe all recordings for a committee
python ~/.claude/skills/colorado-legislature/scripts/legislature.py transcript transcribe-batch --committee jbc

# Batch transcribe all priority committees
python ~/.claude/skills/colorado-legislature/scripts/legislature.py transcript transcribe-all

# Check transcription coverage
python ~/.claude/skills/colorado-legislature/scripts/legislature.py transcript status
```

### Committees

**User Query Examples:**
- "List all year-round committees"
- "Show me the Joint Budget Committee members"

**Commands:**
```bash
# List committees by type
python ~/.claude/skills/colorado-legislature/scripts/legislature.py committees --type year-round
python ~/.claude/skills/colorado-legislature/scripts/legislature.py committees --type session-only
python ~/.claude/skills/colorado-legislature/scripts/legislature.py committees --type all

# Get detailed committee information
python ~/.claude/skills/colorado-legislature/scripts/legislature.py committee info JointBudgetCommittee
```

### Bills & Legislation

**User Query Examples:**
- "Show me recent bills"
- "What's the status of HB26-1001?"
- "Search for housing bills"

**Commands:**
```bash
# List recent bills (default 100)
python ~/.claude/skills/colorado-legislature/scripts/legislature.py bills list --limit 20

# Filter by chamber
python ~/.claude/skills/colorado-legislature/scripts/legislature.py bills list --chamber House

# Get detailed bill information
python ~/.claude/skills/colorado-legislature/scripts/legislature.py bill info HB26-1001
python ~/.claude/skills/colorado-legislature/scripts/legislature.py bill info SB26-004

# Search bills by keyword
python ~/.claude/skills/colorado-legislature/scripts/legislature.py bills search "education"
```

### Search

**User Query Examples:**
- "Search for housing in all legislative data"
- "Find mentions of food assistance"

**Commands:**
```bash
# Search across all data types (schedules, recordings, documents, bills, transcripts)
python ~/.claude/skills/colorado-legislature/scripts/legislature.py search "housing"

# Exact phrase search
python ~/.claude/skills/colorado-legislature/scripts/legislature.py search '"food assistance"'

# Search specific data type
python ~/.claude/skills/colorado-legislature/scripts/legislature.py search "budget" --type schedules
python ~/.claude/skills/colorado-legislature/scripts/legislature.py search "education" --type bills

# Search with department filter
python ~/.claude/skills/colorado-legislature/scripts/legislature.py search "corrections" --department corrections
```

### Watchlists

**User Query Examples:**
- "Create a watchlist for SNAP-related items"
- "Show me new housing legislation"

**Commands:**
```bash
# Create a watchlist
python ~/.claude/skills/colorado-legislature/scripts/legislature.py watch add snap --keywords "SNAP" "food assistance" --display-name "SNAP Benefits"

# List all watchlists
python ~/.claude/skills/colorado-legislature/scripts/legislature.py watch list

# Run a watchlist (all results)
python ~/.claude/skills/colorado-legislature/scripts/legislature.py watch run snap

# Run watchlist (new items only since last check)
python ~/.claude/skills/colorado-legislature/scripts/legislature.py watch run snap --new-only

# Delete a watchlist
python ~/.claude/skills/colorado-legislature/scripts/legislature.py watch delete snap
```

### Advocacy Reports

Generates a comprehensive HTML report for a topic with executive summary, possible champions, bill tracking, hearing mentions, and strategic recommendations.

**User Query Examples:**
- "Generate a report on SNAP for the last 60 days"
- "Create an advocacy report on housing"
- "Build a report on education funding since January"

**Commands:**
```bash
# Generate report (default: last 60 days)
python ~/.claude/skills/colorado-legislature/scripts/legislature.py report SNAP "food assistance"

# Custom time window
python ~/.claude/skills/colorado-legislature/scripts/legislature.py report SNAP --days 90

# Specific start date
python ~/.claude/skills/colorado-legislature/scripts/legislature.py report housing --since 2026-01-01

# Generate and open in browser
python ~/.claude/skills/colorado-legislature/scripts/legislature.py report SNAP --days 60 --open
```

**Report Sections:**
- **Executive Summary** - Overview with match counts and date range
- **Possible Champions** - Legislators identified from transcript speaker data who discussed the topic, with mention counts and sample quotes
- **Key Bills** - Relevant legislation with sponsors, status, and committee assignments
- **Committee Hearings** - Recordings where the topic was discussed, with timestamps
- **Mention Frequency** - How often the topic appears across data types
- **Upcoming Schedule** - Relevant upcoming meetings
- **Budget Documents** - Related budget materials
- **Barriers & Gaps** - Data coverage limitations
- **Next Steps** - Strategic recommendations for advocates

## Installation

Dependencies are installed automatically by Claude when the skill is first used. For manual installation:

```bash
pip install -r ~/.claude/skills/colorado-legislature/requirements.txt
```

**Required Packages:**
- requests (>=2.31.0) - HTTP requests
- beautifulsoup4 (>=4.12.0) - HTML parsing
- lxml (>=5.1.0) - BeautifulSoup parser
- pdfplumber (>=0.11.0) - PDF extraction
- python-dateutil (>=2.8.0) - Date parsing
- assemblyai (>=0.37.0) - Audio transcription (optional, for transcript commands)

**Python Version:** 3.9+

## Data Sources

| Resource | URL Pattern | Method |
|----------|-------------|--------|
| JBC Schedules | `content.leg.colorado.gov/sites/default/files/JBC%20Schedule_*.pdf` | PDF parsing |
| JBC Recordings | `coloradoga.granicus.com/ViewPublisher.php?view_id=26` | HTML scraping |
| Committee Recordings | `sg001-harmony.sliq.net/00327/Harmony/en/api/Data/GetListViewData` | JSON API (SLIQ) |
| Budget Documents | `content.leg.colorado.gov/content/budget` | HTML scraping |
| Committees | `leg.colorado.gov/committees/{session}/{type}/{name}` | HTML scraping |
| Bills | `leg.colorado.gov/bills/{bill-number}` | HTML scraping |

**Website**: https://colorado.leg.gov
**No Public API**: All data scraped from HTML, PDFs, and SLIQ JSON API

## Caching Strategy

| Data Type | Cache Duration | Rationale |
|-----------|----------------|-----------|
| Current week JBC schedule | 0 hours (always fresh) | Changes daily |
| Historical schedules | Permanent | Won't change |
| Current recordings | 1 hour | New recordings may appear |
| Historical recordings | Permanent | Won't change |
| Budget documents | 6 hours | May be updated periodically |
| Committee lists | 24 hours | Updates infrequently during session |
| Committee details | 24 hours | Member changes are rare |
| Bills | 6 hours | Status updates frequently during session |
| Transcripts | Permanent | Audio content doesn't change |
| Reports | Permanent (saved as files) | Timestamped HTML snapshots |

**Cache Location**: `~/.claude/skills/colorado-legislature/data/`

**Clear Cache**:
```bash
rm -rf ~/.claude/skills/colorado-legislature/data/
```

## Architecture

```
~/.claude/skills/colorado-legislature/
├── SKILL.md                    # This file (Claude reads this)
├── README.md                   # Detailed documentation
├── requirements.txt            # Python dependencies
├── scripts/
│   ├── legislature.py          # Main CLI entry point
│   ├── scrapers/
│   │   ├── schedules.py        # JBC PDF schedule parser
│   │   ├── sessions.py         # Session year helper
│   │   ├── audio.py            # Granicus audio/video scraper
│   │   ├── sliq.py             # SLIQ API client (multi-committee)
│   │   ├── documents.py        # Budget document scraper
│   │   ├── pdf_extractor.py    # PDF text extraction utilities
│   │   ├── committees.py       # Committee scraper
│   │   ├── bills.py            # Bills/legislation scraper
│   │   ├── search.py           # Cross-data search engine
│   │   ├── watchlist.py        # Watchlist manager
│   │   └── transcripts.py      # AssemblyAI transcription + batch
│   ├── cache/
│   │   └── manager.py          # Caching with TTL strategies
│   └── formatters/
│       ├── markdown.py         # CLI output formatting
│       └── html.py             # HTML report export
└── data/                       # Cached data (gitignored)
    ├── schedules/
    ├── recordings/
    ├── documents/
    ├── committees/
    ├── bills/
    ├── watchlists/
    ├── transcripts/            # Permanent transcript storage
    ├── reports/                # Generated HTML reports
    └── metadata.json
```

## Examples

### Example 1: Check JBC This Week

**User**: "What's on the JBC agenda this week?"

**Claude invokes**:
```bash
python ~/.claude/skills/colorado-legislature/scripts/legislature.py jbc schedule --week current
```

### Example 2: Find Housing Bills

**User**: "Show me bills about housing"

**Claude invokes**:
```bash
python ~/.claude/skills/colorado-legislature/scripts/legislature.py search "housing" --type bills
```

### Example 3: Track SNAP Benefits

**User**: "Create a watchlist for SNAP food assistance"

**Claude invokes**:
```bash
python ~/.claude/skills/colorado-legislature/scripts/legislature.py watch add snap --keywords "SNAP" "food assistance" "food stamps" --display-name "SNAP Benefits"
```

Then later:
```bash
python ~/.claude/skills/colorado-legislature/scripts/legislature.py watch run snap --new-only
```

### Example 4: Get Bill Details

**User**: "What's the status of HB26-1001?"

**Claude invokes**:
```bash
python ~/.claude/skills/colorado-legislature/scripts/legislature.py bill info HB26-1001
```

### Example 5: Generate Advocacy Report

**User**: "Generate a report on SNAP for the last 60 days"

**Claude invokes**:
```bash
python ~/.claude/skills/colorado-legislature/scripts/legislature.py report SNAP "food assistance" --days 60 --open
```

This generates an HTML report with matched bills, committee hearing mentions, possible legislative champions (identified from transcripts), and strategic next steps. The `--open` flag opens it in the browser.

### Example 6: Transcribe & Search Committee Recordings

**User**: "What has the Health & Human Services committee said about Medicaid?"

**Claude invokes**:
```bash
# Check transcription coverage first
python ~/.claude/skills/colorado-legislature/scripts/legislature.py transcript status

# Transcribe if needed
python ~/.claude/skills/colorado-legislature/scripts/legislature.py transcript transcribe-batch --committee house-hhs

# Search across all transcripts
python ~/.claude/skills/colorado-legislature/scripts/legislature.py search "Medicaid"
```

## Tips for Claude

When users ask about Colorado legislature:

1. **JBC Queries**: Use `jbc schedule` for agenda questions
2. **Committee Info**: Use `committees` and `committee info` for membership
3. **Bill Tracking**: Use `bill info` for specific bills, `bills search` for discovery
4. **Budget Documents**: Use `jbc documents` with department filters
5. **Watchlists**: Suggest watchlists for ongoing monitoring needs
6. **Search**: Use `search` command for cross-data queries; use `"quoted phrases"` for exact matching
7. **Reports**: Use `report` when users want a comprehensive overview of a topic for advocacy -- it generates a self-contained HTML file with champions, bills, hearings, and strategy
8. **Transcripts**: Use `transcript status` to check coverage before searching; `transcript transcribe-batch --committee CODE` to fill gaps

**Always**:
- Include `--week current` or `--week next` for schedule queries
- Use bill numbers when known (HB26-####, SB26-####)
- Filter by department or chamber when appropriate
- Suggest watchlists for recurring information needs
- Use `--open` with reports to show results in the browser
- Quote multi-word phrases in search/report commands: `"food assistance"`

## Error Handling

The skill gracefully handles:
- Missing PDFs/pages (helpful error messages)
- Network failures (falls back to cache when possible)
- Parsing errors (shows context for debugging)
- Invalid inputs (validates week numbers, bill numbers, etc.)
- Rate limiting (polite delays between requests)
- Missing API key (clear error for transcript commands)

## Future Enhancements

- [ ] Real-time meeting alerts
- [ ] Bill status change notifications
- [ ] Legislator voting records and analysis
- [ ] Budget allocation visualizations
- [ ] Historical session comparison (back to 2016)
- [ ] Committee vote predictions
- [ ] MCP Server for persistent connections
- [ ] PDF report export (in addition to HTML)

## Credits

**Created**: February 4, 2026
**Purpose**: Monitor Colorado Legislature activities for SNAP on the Ground project
**Data Source**: Colorado General Assembly (colorado.leg.gov)
**Transcription**: AssemblyAI
**License**: Personal and educational use
