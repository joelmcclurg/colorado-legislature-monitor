# HTML Export Guide

## Overview

Search results can now be exported as styled, standalone HTML files that can be:
- Opened in any web browser
- Shared via email or cloud storage
- Printed or saved as PDFs from the browser
- Embedded in reports or presentations

## Basic Usage

### Phrase Search

Use quotes for exact phrase matching:

```bash
# Match exact phrase "food assistance"
python3 scripts/legislature.py search '"food assistance"'

# Match multiple phrases or words
python3 scripts/legislature.py search '"food assistance" SNAP housing'

# Without quotes: matches any word
python3 scripts/legislature.py search 'food assistance'  # matches "food" OR "assistance"
```

### Export to HTML File

```bash
# Search and save as HTML
python3 scripts/legislature.py search "SNAP" --format html > snap_results.html

# Search with filters (use quotes for phrases)
python3 scripts/legislature.py search '"food assistance"' --format html --type documents > food_docs.html

# Search by department
python3 scripts/legislature.py search "budget" --format html --department "Adults" > adults_budget.html
```

### Open in Browser

```bash
# macOS
python3 scripts/legislature.py search "SNAP" --format html > results.html && open results.html

# Linux
python3 scripts/legislature.py search "SNAP" --format html > results.html && xdg-open results.html

# Windows
python3 scripts/legislature.py search "SNAP" --format html > results.html && start results.html
```

### Default Format (Markdown)

```bash
# Markdown is the default format
python3 scripts/legislature.py search "SNAP"

# Explicitly specify markdown
python3 scripts/legislature.py search "SNAP" --format markdown
```

## HTML Features

The generated HTML includes:

### Styling
- Clean, professional design
- Responsive layout (works on mobile)
- Color-coded sections
- Highlighted search matches (yellow background)
- Hover effects on table rows

### Content
- **Summary** - Total matches and data types
- **Tables** - Sortable columns with links
- **Match Location** - Shows where the match was found (Title, PDF Content, Bill Text, etc.)
- **Context Snippets** - Shows surrounding text for content matches
- **Timestamps** - Generation date/time in footer

### Links
- Bills: Link to leg.colorado.gov bill pages
- Documents: Link to PDF downloads
- Recordings: Link to video players

## Advanced Usage

### Convert to PDF

```bash
# Using browser (recommended)
python3 scripts/legislature.py search "SNAP" --format html > results.html
# Open results.html in Chrome/Firefox and use Print > Save as PDF

# Using wkhtmltopdf (if installed)
python3 scripts/legislature.py search "SNAP" --format html | wkhtmltopdf - results.pdf

# Using pandoc + latex (if installed)
python3 scripts/legislature.py search "SNAP" --format html > temp.html
pandoc temp.html -o results.pdf
```

### Email Results

```bash
# Save HTML and attach to email
python3 scripts/legislature.py search "SNAP" --format html > snap_results.html
# Attach snap_results.html to your email

# Or copy to clipboard (macOS)
python3 scripts/legislature.py search "SNAP" --format html | pbcopy
```

### Batch Export

```bash
# Export multiple searches
for query in "SNAP" "food assistance" "housing" "medicaid"; do
    python3 scripts/legislature.py search "$query" --format html > "${query// /_}_results.html"
done

# Creates: SNAP_results.html, food_assistance_results.html, housing_results.html, medicaid_results.html
```

### Custom Styling

The HTML file has embedded CSS. To customize:

1. Export to HTML file
2. Edit the `<style>` section (lines 8-110)
3. Modify colors, fonts, spacing as needed

Example colors:
- Primary blue: `#3498db`
- Background: `#f5f5f5`
- Highlight: `#fff3cd`
- Heading: `#2c3e50`

## Comparison: Markdown vs HTML

| Feature | Markdown | HTML |
|---------|----------|------|
| **Size** | Smaller | Larger (includes CSS) |
| **Viewing** | Terminal, text editors | Web browsers |
| **Styling** | Basic | Rich formatting |
| **Links** | Clickable in some viewers | Always clickable |
| **Sharing** | Plain text | Standalone file |
| **Best For** | Quick viewing, piping | Sharing, printing, archiving |

## Use Cases

### For Advocates

```bash
# Weekly SNAP policy tracking
python3 scripts/legislature.py search "SNAP" --format html > "SNAP_Week$(date +%V).html"

# Share with team
python3 scripts/legislature.py search "food assistance" --format html > team_report.html
# Email team_report.html to colleagues

# Print for in-person meetings
python3 scripts/legislature.py search "housing" --format html > housing.html
# Open in browser, print to PDF, print hardcopy
```

### For Researchers

```bash
# Archive search results
mkdir archive/$(date +%Y-%m-%d)
python3 scripts/legislature.py search "medicaid" --format html > "archive/$(date +%Y-%m-%d)/medicaid.html"

# Compare over time
python3 scripts/legislature.py search "budget" --format html > "budget_$(date +%Y%m%d).html"
```

### For Reports

```bash
# Generate section for report
python3 scripts/legislature.py search "education funding" --format html > education_section.html

# Extract body content (without HTML wrapper) for embedding
# (Requires sed or text processing)
```

## File Locations

HTML files can be saved anywhere:

```bash
# Project directory
python3 scripts/legislature.py search "SNAP" --format html > results/snap.html

# Desktop (macOS)
python3 scripts/legislature.py search "SNAP" --format html > ~/Desktop/snap.html

# Temp directory
python3 scripts/legislature.py search "SNAP" --format html > /tmp/snap.html
```

## Troubleshooting

### Issue: HTML displays as text in terminal

**Solution**: Redirect to a file instead of viewing directly
```bash
# Wrong
python3 scripts/legislature.py search "SNAP" --format html

# Right
python3 scripts/legislature.py search "SNAP" --format html > results.html
```

### Issue: Browser shows garbled text

**Solution**: Ensure UTF-8 encoding (already included in HTML header)

### Issue: Links don't work

**Solution**: HTML links work in browsers, not in text editors. Open with a browser.

## Examples

### Complete Workflow

```bash
# 1. Extract PDF content
python3 scripts/legislature.py extract documents --department "Adults"

# 2. Search with content
python3 scripts/legislature.py search "SNAP" --format html > snap_report.html

# 3. Open in browser
open snap_report.html  # macOS
# or
xdg-open snap_report.html  # Linux

# 4. Save as PDF from browser (File > Print > Save as PDF)

# 5. Share or archive
```

### Weekly Report Script

```bash
#!/bin/bash
# weekly_report.sh

WEEK=$(date +%Y-W%V)
OUTDIR="reports/$WEEK"
mkdir -p "$OUTDIR"

# Extract fresh content
python3 scripts/legislature.py extract documents

# Generate reports
for topic in "SNAP" "food assistance" "housing" "medicaid"; do
    filename=$(echo "$topic" | tr ' ' '_')
    python3 scripts/legislature.py search "$topic" --format html > "$OUTDIR/${filename}.html"
done

echo "Reports generated in $OUTDIR/"
ls -lh "$OUTDIR/"
```

## Next Steps

After exporting HTML:
1. Open in browser to verify
2. Use browser's Print function to create PDF
3. Share via email, cloud storage, or print
4. Archive for future reference

For more information, see:
- `/docs/WORKFLOWS.md` - General usage patterns
- `/docs/PDF_CONTENT_SEARCH.md` - Content extraction details
