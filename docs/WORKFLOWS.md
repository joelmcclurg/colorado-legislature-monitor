# Common Advocacy Workflows

This guide shows how to use the Colorado Legislature Monitor for common advocacy tasks.

## Quick Reference

```bash
# Find mentions of your issue across all data
legislature.py search "SNAP"

# Use quotes for exact phrase matching
legislature.py search '"food assistance"'  # Only matches "food assistance" together
legislature.py search 'food assistance'     # Matches "food" OR "assistance"

# Monitor your issue automatically
legislature.py watch create snap-issues "SNAP OR food stamps OR nutrition assistance"
legislature.py watch run snap-issues --new-only

# Prepare for upcoming hearings
legislature.py jbc schedule --week next
legislature.py jbc documents --department "Human Services"

# Track a specific bill
legislature.py bill info HB26-1001
legislature.py bills search "housing"

# Find allies and champions
legislature.py committee "Health & Human Services"
legislature.py bills list --limit 20  # Look for sponsors of related bills
```

## Workflow 1: Track a Specific Issue

**Goal**: Monitor all legislative activity related to your issue (e.g., SNAP, housing, education funding)

**Steps**:

1. **Initial Discovery** - Find what's happening now
   ```bash
   # Search for single words
   legislature.py search "SNAP"

   # Search for exact phrases (use quotes)
   legislature.py search '"food assistance"'

   # Mix phrases and words
   legislature.py search '"food assistance" SNAP housing'
   ```
   This searches across:
   - JBC schedules (upcoming hearings)
   - Committee recordings (past testimony)
   - Budget documents (funding discussions)
   - Bills and legislation

   **Quote Tips**:
   - Use quotes for exact phrases: `"food assistance"` matches only the phrase (1 result)
   - Without quotes, matches any word: `food assistance` matches "food" OR "assistance" (17 results)
   - Helpful for avoiding false positives (e.g., "child care assistance" when you want "food assistance")
   - Testing confirmed: quoted searches have 100% accuracy, unquoted provide broader coverage
   - Watch for pluralization: "food bank" vs "food banks" can make a difference

2. **Create Watchlist** - Automate monitoring
   ```bash
   legislature.py watch create snap-monitor "SNAP OR food stamps OR nutrition assistance OR TANF"
   ```
   Use OR to capture different terms for the same issue.

3. **Daily Check** - See what's new
   ```bash
   legislature.py watch run snap-monitor --new-only
   ```
   Shows only items added since last run.

4. **Weekly Review** - See everything
   ```bash
   legislature.py watch run snap-monitor
   ```
   Shows all items matching your keywords.

**Tips**:
- Use broad keywords to catch everything, then filter manually
- Check weekly schedules on Fridays to prepare for next week
- Save watchlist output to share with team: `legislature.py watch run snap-monitor > this-week.md`

## Workflow 2: Prepare for a Hearing

**Goal**: Know what to expect, who will testify, and what questions to ask

**Steps**:

1. **Check Upcoming Schedules**
   ```bash
   legislature.py jbc schedule --week next
   ```
   Look for your department's hearing date.

2. **Get Background Documents**
   ```bash
   legislature.py jbc documents --department "Human Services"
   ```
   Review:
   - Budget briefings (agency's request)
   - Figure settings (JBC's recommendation)
   - Analyses (fiscal notes, context)

3. **Listen to Past Testimony**
   ```bash
   legislature.py jbc recordings --week 3
   ```
   Find relevant recordings from earlier hearings on the same topic.

4. **Find Related Bills**
   ```bash
   legislature.py bills search "child care"
   ```
   See what legislation is pending that relates to the budget discussion.

5. **Identify Committee Members**
   ```bash
   legislature.py committee "Joint Budget Committee"
   ```
   Know who to address in testimony.

**Result**: You arrive at the hearing with:
- Understanding of budget request vs. recommendation
- Questions prepared for agency/JBC
- Awareness of related legislation
- Names of committee members to address

## Workflow 3: Find Allies and Build Coalitions

**Goal**: Identify legislators and advocates working on related issues

**Steps**:

1. **Find Bills on Your Issue**
   ```bash
   legislature.py bills search "affordable housing"
   ```

2. **Check Bill Sponsors**
   ```bash
   legislature.py bill info HB26-1001
   ```
   Look at:
   - Prime sponsors (lead advocates)
   - Co-sponsors (supporters)
   - Committee assignment (where it goes next)

3. **Find Committee Members**
   ```bash
   legislature.py committee "Transportation, Housing & Local Government"
   ```
   Identify:
   - Committee chair (gatekeeper)
   - Members (who votes on the bill)

4. **Search for Related Issues**
   ```bash
   legislature.py search "homelessness OR housing OR shelter"
   ```
   Find mentions across different contexts.

5. **Track Multiple Bills**
   ```bash
   legislature.py watch create housing-coalition "housing OR homelessness OR shelter OR affordable"
   ```

**Result**: You know:
- Who champions housing issues (build relationships)
- Which committees handle housing (where to testify)
- What related issues connect to housing (coalition opportunities)

## Workflow 4: Hold Legislators Accountable

**Goal**: Document legislator actions and promises

**Steps**:

1. **Track Bill Progress**
   ```bash
   legislature.py bill info HB26-1001
   ```
   Shows:
   - Vote history (who voted how)
   - Amendments (what changed)
   - Status (where it is now)

2. **Find Voting Records**
   Check "Votes" section in bill info output:
   ```
   | Date | Chamber | Action | Yeas | Nays | Result |
   ```

3. **Check Committee Actions**
   ```bash
   legislature.py committee "Finance"
   ```
   See who's on the committee that heard the bill.

4. **Document Over Time**
   Save outputs regularly:
   ```bash
   legislature.py bill info HB26-1001 > bill-1001-week6.md
   ```
   Compare to earlier saves to see changes.

**Result**: You can show:
- How your legislator voted on key bills
- Whether amendments weakened or strengthened the bill
- Timeline of actions (for campaign materials)

## Workflow 5: Spot Budget Transparency Issues

**Goal**: Find funding changes that don't require legislation

**Steps**:

1. **Monitor Budget Hearings**
   ```bash
   legislature.py jbc schedule --week current
   legislature.py jbc schedule --week next
   ```

2. **Check Department Requests**
   ```bash
   legislature.py jbc documents --department "Corrections"
   ```
   Look for:
   - Increases vs. decreases
   - New line items
   - Eliminated programs

3. **Search for Context**
   ```bash
   legislature.py search "Corrections AND budget"
   ```
   Find mentions in other documents.

4. **Create Budget Watchlist**
   ```bash
   legislature.py watch create budget-watch "budget briefing OR figure setting"
   ```

**Result**: You catch:
- Administrative funding changes (not requiring bills)
- Cuts disguised as "technical adjustments"
- New programs without public announcement

## Tips for All Workflows

### Keyword Strategy
- **Too narrow**: "SNAP benefits increase" (might miss related discussions)
- **Too broad**: "benefits" (catches everything)
- **Just right**: "SNAP OR food stamps OR nutrition assistance"

Use OR for synonyms, AND to narrow:
```bash
legislature.py search "housing AND (affordability OR vouchers)"
```

### Watchlist Hygiene
- Review watchlists monthly
- Delete inactive watchlists
- Update keywords as language evolves
- List all watchlists: `legislature.py watch list`

### Sharing with Team
- Markdown output is readable and shareable
- Copy/paste into team docs, emails, reports
- Save to files: `legislature.py search "keywords" > findings.md`

### Frequency
- **Daily**: Check watchlists (--new-only)
- **Weekly**: Review schedules, prep for hearings
- **Monthly**: Search for strategic patterns, update watchlists

## Getting Help

```bash
legislature.py --help                # All commands
legislature.py jbc --help           # JBC commands
legislature.py watch --help         # Watchlist commands
legislature.py bill --help          # Bill commands
```

## Common Issues

**Issue**: Too many results
**Solution**: Use more specific keywords or combine with AND

**Issue**: Missing expected results
**Solution**: Try synonyms or broader keywords with OR

**Issue**: Watchlist shows old items
**Solution**: Use `--new-only` flag to see only new items

**Issue**: Need to share with team
**Solution**: Redirect output to file: `legislature.py search "keywords" > results.md`
