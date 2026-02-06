---
name: colorado-legislature
description: Monitor Colorado legislature committees, bills, schedules, and budget discussions. Tracks JBC activities, all committees (year-round, session-only, interim), legislation, votes, amendments, and budget documents. Use when user asks about committee meetings, bills, legislative schedules, budget items, Colorado legislators, or state legislature activities.
allowed-tools: ["Bash(python *)", "Read", "Write"]
---

# Colorado Legislature Monitor

A comprehensive monitoring tool for the Colorado Legislature with focus on the Joint Budget Committee (JBC), all legislative committees, bills and legislation tracking, and budget document monitoring.

**Version**: 0.5.0 (Phase 5 - Bills & Legislation Complete)
**Current Session**: 2026A (2026 Regular Session)

## Capabilities

### ✅ Phase 1: JBC Schedule MVP (Complete)
- Fetch and display Joint Budget Committee weekly schedules
- PDF parsing with date, time, and topic extraction
- Intelligent caching (current week fresh, historical permanent)
- Markdown-formatted tables

### ✅ Phase 1.5: Media & Documents (Complete)
- Granicus audio/video recording links for JBC meetings
- Budget document portal scraping (briefings, figure settings, etc.)
- Department name normalization
- Enhanced schedule tables with Media and Documents columns

### ✅ Phase 2: Committee Expansion (Complete)
- All year-round committees (14 committees)
- Session-only committees (House & Senate committees of reference)
- Interim committees and task forces
- Committee member lists with leadership
- Full committee information pages

### ✅ Phase 3: Search & Watchlists (Complete)
- Cross-data search (schedules, recordings, documents, bills)
- Keyword-based search with match highlighting
- Watchlists for monitoring specific topics
- Department and chamber filtering
- New-only filtering for watchlist updates

### ✅ Phase 4: Bills & Legislation (Complete)
- Bill listing with session/chamber filtering
- Detailed bill information (sponsors, status, amendments, votes)
- Bill text versions (Introduced, Engrossed, Enrolled)
- Fiscal notes and impact statements
- Complete bill history timeline
- Amendment tracking with status
- Vote records with results
- Bill search across titles, sponsors, subjects
- Watchlist integration for bill tracking

## Usage

### JBC Schedule

**User Query Examples:**
- "What's on the JBC agenda this week?"
- "Show me the JBC schedule for next week"
- "What is the Joint Budget Committee meeting about?"

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

# Recording for specific date
python ~/.claude/skills/colorado-legislature/scripts/legislature.py jbc recordings --date 2026-02-04
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

# Documents by type
python ~/.claude/skills/colorado-legislature/scripts/legislature.py jbc documents --type briefing

# List all departments
python ~/.claude/skills/colorado-legislature/scripts/legislature.py jbc documents --list-departments
```

### Committees

**User Query Examples:**
- "List all year-round committees"
- "Show me the Joint Budget Committee members"
- "What committees meet during the session?"

**Commands:**
```bash
# List year-round committees
python ~/.claude/skills/colorado-legislature/scripts/legislature.py committees --type year-round

# List session-only committees (House + Senate)
python ~/.claude/skills/colorado-legislature/scripts/legislature.py committees --type session-only

# List all committees
python ~/.claude/skills/colorado-legislature/scripts/legislature.py committees --type all

# Get detailed committee information
python ~/.claude/skills/colorado-legislature/scripts/legislature.py committee info JointBudgetCommittee
python ~/.claude/skills/colorado-legislature/scripts/legislature.py committee info AgricultureWaterNaturalResources
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

# Filter by type
python ~/.claude/skills/colorado-legislature/scripts/legislature.py bills list --type Resolution

# Get detailed bill information
python ~/.claude/skills/colorado-legislature/scripts/legislature.py bill info HB26-1001
python ~/.claude/skills/colorado-legislature/scripts/legislature.py bill info SB26-004

# Search bills by keyword
python ~/.claude/skills/colorado-legislature/scripts/legislature.py bills search "education"
python ~/.claude/skills/colorado-legislature/scripts/legislature.py bills search "housing" --chamber Senate
```

### Search

**User Query Examples:**
- "Search for housing in all legislative data"
- "Find mentions of education funding"
- "Search for corrections budget items"

**Commands:**
```bash
# Search across all data types (schedules, recordings, documents, bills)
python ~/.claude/skills/colorado-legislature/scripts/legislature.py search "housing"

# Search specific data type
python ~/.claude/skills/colorado-legislature/scripts/legislature.py search "budget" --type schedules
python ~/.claude/skills/colorado-legislature/scripts/legislature.py search "education" --type bills

# Search with department filter
python ~/.claude/skills/colorado-legislature/scripts/legislature.py search "corrections" --department corrections

# Search bills with chamber filter
python ~/.claude/skills/colorado-legislature/scripts/legislature.py search "transportation" --type bills --chamber House
```

### Watchlists

**User Query Examples:**
- "Create a watchlist for SNAP-related items"
- "Show me new housing legislation"
- "Track education budget discussions"

**Commands:**
```bash
# Create a watchlist
python ~/.claude/skills/colorado-legislature/scripts/legislature.py watch add snap --keywords "SNAP" "food assistance" --display-name "SNAP Benefits"

# Create watchlist with department filter
python ~/.claude/skills/colorado-legislature/scripts/legislature.py watch add edu-budget --keywords "education" "budget" --departments education

# List all watchlists
python ~/.claude/skills/colorado-legislature/scripts/legislature.py watch list

# Show watchlist configuration
python ~/.claude/skills/colorado-legislature/scripts/legislature.py watch show snap

# Run a watchlist (all results)
python ~/.claude/skills/colorado-legislature/scripts/legislature.py watch run snap

# Run watchlist (new items only since last check)
python ~/.claude/skills/colorado-legislature/scripts/legislature.py watch run snap --new-only

# Delete a watchlist
python ~/.claude/skills/colorado-legislature/scripts/legislature.py watch delete snap
```

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

**Python Version:** 3.7+ (Recommended: 3.9+)

## Data Sources

| Resource | URL Pattern | Method |
|----------|-------------|--------|
| JBC Schedules | `content.leg.colorado.gov/sites/default/files/JBC%20Schedule_*.pdf` | PDF parsing |
| Audio/Video | `coloradoga.granicus.com/ViewPublisher.php?view_id=26` | HTML scraping |
| Budget Documents | `content.leg.colorado.gov/content/budget` | HTML scraping |
| Committees | `leg.colorado.gov/committees/{session}/{type}/{name}` | HTML scraping |
| Bills | `leg.colorado.gov/bills/{bill-number}` | HTML scraping |

**Website**: https://colorado.leg.gov
**No Public API**: All data scraped from HTML and PDFs

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

**Cache Location**: `~/.claude/skills/colorado-legislature/data/`

**Clear Cache**:
```bash
rm -rf ~/.claude/skills/colorado-legislature/data/
```

## Data Structures

### Schedule Data
```json
{
  "week_number": 5,
  "week_start": "2026-02-03",
  "week_end": "2026-02-09",
  "meetings": [
    {
      "date": "2026-02-04",
      "time": "1:30 PM",
      "topic": "Department of Education Budget Hearing",
      "department": "education",
      "video_url": "https://...",
      "document_url": "https://...",
      "is_cancelled": false
    }
  ]
}
```

### Committee Data
```json
{
  "name": "Joint Budget Committee",
  "slug": "JointBudgetCommittee",
  "type": "year-round",
  "session": "2026A",
  "members": [
    {
      "name": "Emily Sirota",
      "role": "Chair",
      "chamber": "House",
      "profile_url": "https://..."
    }
  ],
  "leadership": {
    "chair": "Emily Sirota",
    "vice_chair": "Jeff Bridges"
  }
}
```

### Bill Data
```json
{
  "bill_number": "HB26-1001",
  "title": "Housing Developments on Qualifying Properties",
  "session": "2026A",
  "status": "Under Consideration",
  "sponsors": [
    {
      "name": "Andrew Boesenecker",
      "role": "Prime Sponsor"
    }
  ],
  "committee": {
    "name": "House Transportation, Housing & Local Government"
  },
  "subjects": ["Housing", "Local Government"],
  "last_action": "Introduced in House - 01/14/2026",
  "bill_text": [
    {
      "version": "Introduced",
      "date": "01/14/2026",
      "url": "https://..."
    }
  ],
  "amendments": [...],
  "votes": [...]
}
```

## Troubleshooting

### No Schedule/Data Found
- PDF may not be published yet for future weeks
- URL pattern may have changed
- Network connectivity issues
- Try clearing cache

### Parsing Errors
- HTML/PDF format may have changed
- Check raw_content in output
- Heuristic parser may need adjustment

### Missing Bills
- Bills must be fetched with `bill info` before they appear in search
- Main bills page only shows recent/featured bills
- Use bill number directly if known

### Cache Issues
```bash
# Clear all cache
rm -rf ~/.claude/skills/colorado-legislature/data/

# Clear specific type
rm -rf ~/.claude/skills/colorado-legislature/data/bills/
rm -rf ~/.claude/skills/colorado-legislature/data/committees/
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
│   │   ├── documents.py        # Budget document scraper
│   │   ├── committees.py       # Committee scraper
│   │   ├── bills.py            # Bills/legislation scraper
│   │   ├── search.py           # Cross-data search engine
│   │   └── watchlist.py        # Watchlist manager
│   ├── cache/
│   │   └── manager.py          # Caching with TTL
│   └── formatters/
│       └── markdown.py         # Output formatters
└── data/                       # Cached data (gitignored)
    ├── schedules/
    ├── recordings/
    ├── documents/
    ├── committees/
    ├── bills/
    ├── watchlists/
    └── metadata.json
```

## Examples

### Example 1: Check JBC This Week

**User**: "What's on the JBC agenda this week?"

**Claude invokes**:
```bash
python ~/.claude/skills/colorado-legislature/scripts/legislature.py jbc schedule --week current
```

**Output**:
```markdown
# JBC Schedule - Week 6 (Feb 03 - Feb 09, 2026)

## Wednesday, February 05

| Time | Topic | Media | Documents |
|------|-------|-------|-----------|
| 1:30 – 5:00 | Dept of Education Budget Hearing | [Video](https://...) | [Brief](https://...) |

---
**Fetched**: 2026-02-04T15:30:00
```

### Example 2: Find Housing Bills

**User**: "Show me bills about housing"

**Claude invokes**:
```bash
python ~/.claude/skills/colorado-legislature/scripts/legislature.py search "housing" --type bills
```

**Output**:
```markdown
# Search Results for "housing"

Found **1** matches across 1 data type(s).

## Bills (1 match)

| Bill # | Title | Sponsors |
|--------|-------|----------|
| [HB26-1001](...) | **Housing** Developments on Qualifying Pro... | Andrew Boesenecker, Javier Mabrey |
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

**Output**:
```markdown
# HB26-1001
## Housing Developments on Qualifying Properties

**Session:** 2026A
**Status:** Under Consideration

### Sponsors
**Prime Sponsors:**
- [Andrew Boesenecker](...)
- [Javier Mabrey](...)

### Committee Assignment
[House Transportation, Housing & Local Government](...)

### Subjects
Housing, Local Government

### Last Action
Introduced in House - 01/14/2026
```

## Tips for Claude

When users ask about Colorado legislature:

1. **JBC Queries**: Use `jbc schedule` for agenda questions
2. **Committee Info**: Use `committees list` and `committee info` for membership
3. **Bill Tracking**: Use `bill info` for specific bills, `bills search` for discovery
4. **Budget Documents**: Use `jbc documents` with department filters
5. **Watchlists**: Suggest watchlists for ongoing monitoring needs
6. **Search**: Use `search` command for cross-data queries

**Always**:
- Include `--week current` or `--week next` for schedule queries
- Use bill numbers when known (HB26-####, SB26-####)
- Filter by department or chamber when appropriate
- Suggest watchlists for recurring information needs

## Error Handling

The skill gracefully handles:
- Missing PDFs/pages (helpful error messages)
- Network failures (falls back to cache when possible)
- Parsing errors (shows context for debugging)
- Invalid inputs (validates week numbers, bill numbers, etc.)
- Rate limiting (polite delays between requests)

## Future Enhancements

- [ ] Real-time meeting alerts
- [ ] Bill status change notifications
- [ ] Legislator voting records and analysis
- [ ] Budget allocation visualizations
- [ ] Historical session comparison (back to 2016)
- [ ] Testimony transcripts
- [ ] Committee vote predictions
- [ ] MCP Server for persistent connections

## Credits

**Created**: February 4, 2026
**Purpose**: Monitor Colorado Legislature activities for SNAP on the Ground project
**Data Source**: Colorado General Assembly (colorado.leg.gov)
**License**: Personal and educational use
