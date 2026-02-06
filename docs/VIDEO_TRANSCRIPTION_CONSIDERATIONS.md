# Video Transcription Scraping: Technical Considerations

**Date**: February 5, 2026
**Status**: Planning Phase
**Audience**: Propel Engineering Team

## Executive Summary

Video recordings are a critical data source for legislative monitoring, containing testimony, debate, and discussion not captured in written documents. This document outlines technical approaches, challenges, and recommendations for adding searchable video transcription to the Colorado Legislature Monitor.

## Current State

**What We Have:**
- Links to Granicus video recordings for JBC meetings
- Meeting metadata (date, time, agenda)
- No transcription or searchable content

**Example URLs:**
```
https://granicus.com/player/...
```

## Goals

1. **Searchable Transcripts**: Enable keyword search across all hearing recordings
2. **Speaker Attribution**: Identify who said what (legislators, testifiers, staff)
3. **Time-Stamped Content**: Link search results to specific video timestamps
4. **Cross-Reference**: Connect testimony to related bills, budget items, documents

## Technical Approaches

### Option 1: Granicus API/Platform Features

**Description**: Check if Granicus provides transcription services or API access

**Pros:**
- May already have transcripts (auto-generated or manual)
- Speaker identification might be built-in
- No additional transcription cost if already available
- Most accurate timing sync with video

**Cons:**
- May not exist or require expensive subscription
- Limited control over quality/format
- Vendor lock-in

**Investigation Needed:**
- Does Granicus offer transcription services?
- Is there a public or authenticated API?
- What's the cost model?
- Are transcripts already available but not exposed publicly?

**Recommendation**: **Start here** - investigate before building custom solution

---

### Option 2: Legislative Website Transcript Scraping

**Description**: Many legislatures provide official transcripts separate from video

**Pros:**
- Official, accurate transcripts
- Speaker attribution already done
- No transcription cost
- Authoritative source

**Cons:**
- May not exist for all hearings
- May be delayed (published days/weeks after hearing)
- Format varies (PDF, HTML, proprietary)
- May only cover floor sessions, not committee hearings

**Investigation Needed:**
- Does Colorado Legislature publish official transcripts?
- What formats are they in?
- What's the coverage (JBC only? All committees? Floor sessions?)
- What's the lag time between hearing and transcript publication?

**Recommendation**: **High priority investigation** - free and authoritative if available

---

### Option 3: YouTube Auto-Captions

**Description**: If videos are mirrored on YouTube, use their auto-generated captions

**Pros:**
- Free (YouTube does transcription automatically)
- API access via YouTube Data API
- Already time-stamped
- Reasonable accuracy for clear audio

**Cons:**
- Only works if videos are on YouTube
- No speaker identification
- Lower accuracy than professional services
- May have delays before captions are generated

**Investigation Needed:**
- Are Colorado Legislature hearings on YouTube?
- Do they have auto-captions enabled?
- What's the accuracy like for legislative content?

**API Example:**
```python
# YouTube captions can be fetched via youtube-transcript-api
from youtube_transcript_api import YouTubeTranscriptApi

transcript = YouTubeTranscriptApi.get_transcript(video_id)
# Returns: [{'text': '...', 'start': 0.0, 'duration': 2.5}, ...]
```

**Recommendation**: **Quick win if available** - test accuracy with sample videos

---

### Option 4: Custom Speech-to-Text (ASR)

**Description**: Download video/audio and run through speech recognition service

**Services:**
- **OpenAI Whisper** (open source, self-hosted or API)
- **Google Cloud Speech-to-Text**
- **AWS Transcribe**
- **Azure Speech Services**
- **AssemblyAI**

#### 4a. OpenAI Whisper

**Pros:**
- State-of-the-art accuracy
- Open source (can self-host)
- API available ($0.006/minute via OpenAI)
- Good with technical terminology
- Speaker diarization available (who's speaking)
- Multiple language support

**Cons:**
- Requires audio extraction from video
- API costs scale with usage (~$0.36/hour of video)
- Processing time (not instant)
- Self-hosting requires GPU for reasonable speed

**Cost Estimate:**
- 100 hours of hearings/month: $36/month
- 1000 hours (full archive): $360 one-time

**Code Example:**
```python
import openai

audio_file = open("hearing.mp3", "rb")
transcript = openai.Audio.transcribe(
    model="whisper-1",
    file=audio_file,
    response_format="verbose_json",  # Includes timestamps
    language="en"
)

# Returns timestamped segments
for segment in transcript['segments']:
    print(f"[{segment['start']:.2f}s] {segment['text']}")
```

#### 4b. Google Cloud Speech-to-Text

**Pros:**
- High accuracy
- Speaker diarization built-in
- Long-form audio support (up to 480 minutes)
- Automatic punctuation and formatting
- Custom vocabulary for technical terms

**Cons:**
- More expensive (~$1.44/hour with diarization)
- Requires Google Cloud account
- More complex setup

**Cost Estimate:**
- 100 hours/month: $144/month
- Enhanced model with diarization: ~$2.88/hour

#### 4c. AWS Transcribe

**Pros:**
- Similar features to Google Cloud
- Good integration if using AWS infrastructure
- Custom vocabulary support
- Speaker identification

**Cons:**
- Pricing: $1.44/hour (standard), $2.16/hour (enhanced)
- AWS account required

#### 4d. AssemblyAI

**Pros:**
- Purpose-built for transcription
- Excellent speaker diarization
- Topic detection, sentiment analysis
- Entity recognition (names, organizations)
- Competitive pricing

**Cons:**
- Third-party service dependency
- $0.65/hour (base), $1.40/hour (with all features)

**Recommendation**: **Whisper API is best balance** of cost, accuracy, and ease of use

---

## Technical Challenges

### 1. Speaker Identification

**Problem**: Knowing who said what is critical for advocacy work

**Approaches:**
- **Speaker diarization**: AI labels speakers as "Speaker 1", "Speaker 2", etc.
- **Manual mapping**: Match speaker segments to agenda/attendee list
- **Voice fingerprinting**: Train on known legislators (complex, high effort)

**Recommendation**:
- Start with diarization (who spoke when)
- Use meeting metadata to map speakers to names
- Example: "Speaker 1" appears at 10:00 when Rep. Smith is recognized → label as Rep. Smith

### 2. Accuracy with Legislative Terminology

**Problem**: Technical terms, bill numbers, proper names are critical

**Solutions:**
- Custom vocabulary/glossary
- Post-processing to fix known issues
- Human review of important segments

**Example Issues:**
- "HB 1234" transcribed as "age be twelve thirty four"
- "TANF" becomes "tan F"
- "Medicaid" becomes "medical aid"

**Recommendation**:
- Build custom vocabulary of common terms (bill numbers, programs, legislator names)
- Post-process with regex to fix predictable errors

### 3. Audio Quality

**Problem**: Poor audio affects transcription accuracy

**Factors:**
- Background noise
- Multiple speakers talking over each other
- Microphone quality
- Room acoustics

**Mitigation:**
- Audio preprocessing (noise reduction)
- Use services with noise handling (Whisper is good at this)
- Accept some accuracy loss, flag low-confidence segments

### 4. Scale and Cost

**Volume Estimate:**
- JBC: ~3 hearings/week × 3 hours each = 9 hours/week
- All committees: ~50 hours/week during session
- Annual archive: ~2000 hours

**Cost Scenarios:**

| Service | Hourly Rate | 50 hrs/week | Annual (2000 hrs) |
|---------|-------------|-------------|-------------------|
| Whisper API | $0.36 | $18/week | $720/year |
| YouTube (free) | $0 | $0 | $0 |
| Google Cloud | $1.44 | $72/week | $2,880/year |
| AssemblyAI | $0.65 | $32.50/week | $1,300/year |

**Recommendation**: Start with current session only (lower volume), expand to archive if valuable

### 5. Storage and Indexing

**Data Size:**
- Raw video: ~1GB/hour
- Audio only: ~50MB/hour
- Transcript text: ~100KB/hour
- With timestamps and metadata: ~500KB/hour

**Storage for 2000 hours:**
- Transcripts only: ~1GB
- Audio files: ~100GB
- Video files: ~2TB

**Recommendation**:
- Store transcripts and metadata only (small)
- Don't store video/audio (link to Granicus)
- Use existing search infrastructure (same as documents)

### 6. Real-Time vs. Batch Processing

**Real-Time:**
- Transcribe as hearings happen (live captions)
- Complex infrastructure
- Higher cost
- Not critical for advocacy use case

**Batch:**
- Transcribe after hearing completes
- Simpler, cheaper
- Acceptable delay (hours to 1 day)

**Recommendation**: **Batch processing** - hearings are announced in advance, advocates can plan

---

## Implementation Recommendations

### Phase 1: Investigation (1 week)

1. **Check for existing transcripts**
   - Does Colorado Legislature publish official transcripts?
   - Does Granicus provide transcripts or API access?
   - Are videos on YouTube with captions?

2. **Proof of concept**
   - Download 3-5 sample videos
   - Test Whisper API accuracy
   - Compare to YouTube captions (if available)
   - Measure speaker diarization quality

3. **Cost modeling**
   - Count total hours of video to transcribe
   - Calculate ongoing weekly volume
   - Determine budget constraints

### Phase 2: MVP (2-3 weeks)

**Scope**: Current session only (JBC hearings)

**Implementation:**
```python
# Pipeline pseudocode
1. Scrape video URLs from Granicus
2. Extract audio from video (ffmpeg)
3. Send to Whisper API
4. Parse response (text + timestamps)
5. Apply speaker diarization
6. Post-process for known issues
7. Store in database
8. Index for search
```

**Features:**
- Searchable transcripts for JBC hearings
- Basic speaker labels ("Speaker 1", "Speaker 2")
- Time-stamped segments linking to video
- Same search interface as documents

**Success Metrics:**
- Transcription accuracy >90%
- Processing time <1 hour per video
- Search finds relevant testimony

### Phase 3: Enhancement (ongoing)

1. **Speaker identification**
   - Map speaker labels to names using agenda
   - Build legislator voice profiles (advanced)

2. **Custom vocabulary**
   - List of bill numbers, programs, common terms
   - Improve accuracy for legislative jargon

3. **Expand coverage**
   - All committees (not just JBC)
   - Historical archive
   - Floor sessions

4. **Search improvements**
   - "Find all times Rep. Smith mentioned housing"
   - "Show testimony about HB-1234"
   - Topic clustering (what topics were discussed?)

---

## Technical Stack Recommendation

### Recommended Approach

**For Colorado MVP:**

```yaml
Transcription: OpenAI Whisper API
Storage: SQLite (same as current cache)
Search: Existing search infrastructure
Audio processing: ffmpeg (extract from video)
Speaker diarization: Built into Whisper
Cost: ~$18/week (current session only)
```

**Why Whisper:**
- Best accuracy-to-cost ratio
- Easy API integration
- Good with legislative content
- Speaker diarization included
- Proven at scale

**Why NOT YouTube:**
- May not be available for all hearings
- Lower accuracy
- No control over quality

**Why NOT Google/AWS:**
- 4x more expensive
- Overkill for current needs
- Can migrate later if needed

### Code Structure

```
scripts/
  scrapers/
    transcripts.py          # Fetch videos, manage transcription
    granicus.py             # Video URL scraper
  processing/
    audio_extraction.py     # ffmpeg wrapper
    whisper_client.py       # Whisper API calls
    speaker_mapping.py      # Map speakers to names
    post_processing.py      # Fix common errors
  cache/
    transcripts_cache.py    # Store transcripts
```

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Transcription accuracy too low | Users don't trust results | Test on samples first, set quality bar |
| Cost exceeds budget | Can't afford to scale | Start small, measure ROI before expanding |
| Speaker ID fails | Can't attribute quotes | Fall back to timestamp-only, manual mapping |
| Granicus blocks scraping | Can't access videos | Use official channels, respect ToS |
| Processing too slow | Delayed results | Batch overnight, prioritize recent hearings |

---

## Questions for Propel Team

1. **Budget**: What's the monthly budget for transcription services?
2. **Priority**: Is this MVP-critical or phase 2 enhancement?
3. **Coverage**: JBC only or all committees from day 1?
4. **Accuracy**: What's acceptable accuracy for launch? (90%? 95%?)
5. **Infrastructure**: Self-host (GPU required) or use APIs?
6. **Storage**: Where should transcripts be stored long-term?
7. **Legal**: Any concerns about scraping/transcribing public hearings?

---

## Next Steps

1. **Investigation sprint** (you or Propel engineers)
   - Check for official transcripts
   - Test Whisper on 3 sample videos
   - Verify Granicus access/ToS

2. **Decision meeting** (after investigation)
   - Review test results
   - Confirm budget and scope
   - Choose transcription service
   - Set accuracy bar

3. **MVP implementation** (if approved)
   - Build transcription pipeline
   - Integrate with existing search
   - Test with advocates
   - Measure value before scaling

---

## Conclusion

Video transcription is **technically feasible** and **economically viable** for the Colorado Legislature Monitor.

**Recommended path:**
1. Investigate existing transcripts first (free)
2. If none exist, use Whisper API (~$18/week for JBC)
3. Start with current session only
4. Expand based on advocate feedback

**Key success factor**: Test accuracy with real legislative content before committing to full implementation.

---

**Technical contact**: [Your name/contact]
**Last updated**: February 5, 2026
