# Conversation Management Feature - Product Requirements Document (PRD)

**Project**: Speekium
**Version**: 1.1
**Date**: 2025-01-13
**Status**: Draft - Ready for Implementation
**Owner**: Product Team

---

## 📋 Executive Summary

### Problem Statement
Speekium currently provides basic session management (list, create, delete) but lacks **content value management capabilities**. As a **completely new project with zero users**, we need to build foundational features that will enable future users to effectively **find**, **save**, and **organize** valuable conversation content.

### Approach: "Build to Learn" Strategy
Since this is a **completely new project** with no user data, we're taking a pragmatic approach:

1. **Build MVP features based on best practices** from competitors (ChatGPT, Otter.ai, Apple Voice Memos)
2. **Start collecting data from Day 1** - every interaction becomes learning
3. **Rapid iteration cycles** - 2-week sprints with built-in feedback loops
4. **Beta testing approach** - release to early users quickly, learn from real usage

### Hypothesis
If we provide basic conversation management tools (auto-titles, starring), early users will:
- Find Speekium more useful for knowledge management
- Establish patterns we can learn from
- Provide feedback for iterative improvements

### Key Difference from Data-Driven Approach
**Data-Driven**: Validate first → build if data supports (requires existing users)
**Build-to-Learn**: Build MVP → learn from early users → iterate rapidly (new projects)

---

## 🎯 Success Criteria

### Primary Metrics (First 2 Weeks)

| Metric | Target | Definition |
|--------|--------|------------|
| **Feature Completeness** | 100% | MVP features built and tested |
| **First User Feedback** | ≥5 beta users | Recruit initial testers |
| **Star Adoption** | ≥20% | % of beta users who star at least 1 conversation |
| **Title Generation** | ≥80% | % of conversations with auto-titles |

### Learning Metrics (Week 3-4)

| Metric | Target | Definition |
|--------|--------|------------|
| **User Patterns** | Identify 3+ patterns | How users actually organize conversations |
| **Pain Points** | Document top 5 | What users struggle with most |
| **Feature Requests** | Prioritize list | What users want next |
| **Usage Frequency** | ≥2x/week | Beta users return to use features |

### Quality Gates

| Metric | Threshold | Action if Failed |
|--------|-----------|------------------|
| **Bug Count** | >5 critical | Fix before beta release |
| **Title Generation Time** | >5 seconds | Optimize or simplify |
| **Crash Rate** | >1% | Block on release |

---

## 📊 Phase 0: Competitive Analysis & Best Practices (4 Hours)

### Goal
Since we have **no user data**, we'll:
1. **Learn from competitors** - What works for ChatGPT, Otter.ai, Apple Voice Memos?
2. **Establish baseline features** - Build industry-standard conversation management
3. **Prepare for data collection** - Design analytics from Day 1

### Timeline
- **Day 1 Morning**: Competitive analysis (2 hours)
- **Day 1 Afternoon**: Technical design + data collection plan (2 hours)
- **Day 2**: Start implementation (no waiting needed)

---

### 1.1 Competitive Analysis

#### Reference Products

**ChatGPT (Conversation Management)**
- **Auto-titles**: ✅ Yes (first message preview)
- **Search**: ✅ Yes (full-text, semantic)
- **Organization**: ✅ Folders/archive
- **Export**: ✅ Yes (Markdown, JSON)
- **Star/Favorite**: ❌ No
- **Key Insight**: Simple folder system + powerful search = sufficient for most users

**Otter.ai (Voice Meeting Notes)**
- **Auto-titles**: ✅ Yes (AI-generated from content)
- **Search**: ✅ Yes (full-text + speaker attribution)
- **Organization**: ✅ Folders + labels
- **Export**: ✅ Yes (multiple formats)
- **Star/Favorite**: ✅ Yes (star important conversations)
- **Key Insight**: Voice-first products NEED auto-titles + starring

**Apple Voice Memos**
- **Auto-titles**: ❌ No (manual rename only)
- **Search**: ✅ Yes (iOS 17+, full-text transcription)
- **Organization**: ❌ No folders (just chronological list)
- **Export**: ✅ Yes (save to Files)
- **Star/Favorite**: ✅ Yes (starred recordings appear in folder)
- **Key Insight**: Extreme simplicity - just star + search works

#### Key Takeaways for MVP

**Must-Have (Phase 1)**:
1. **Auto-generated titles** - All competitors have this or manual rename
2. **Star/Favorite** - Otter and Apple have this, ChatGPT doesn't (differentiation opportunity)
3. **Export** - Universal feature, but defer to Phase 2 (scope management)

**Nice-to-Have (Phase 2)**:
1. **Search** - All competitors have, but defer to validate need
2. **Folders** - ChatGPT has, Otter has, Apple doesn't (maybe overkill for MVP)

**Never Build**:
- Complex tagging systems (Apple proves simplicity wins)
- Social features (out of scope for voice assistant)

---

### 1.2 Technical Design: Analytics from Day 1

Since we're building without user data, we must **start collecting data from the first user**.

#### Events to Track

```typescript
// Frontend: Track user interactions
interface AnalyticsEvent {
  event: string;
  timestamp: number;
  session_id: string;
  properties: Record<string, any>;
}

// Key Events
events_to_track = [
  'session_created',
  'session_opened',
  'session_renamed',           // Manual vs auto title
  'session_starred',
  'session_unstarred',
  'session_deleted',
  'title_generated',           // Success/failure
  'filter_changed',            // all/starred
  'search_performed',          // Phase 2
  'export_triggered',          // Phase 2
]

// Backend: Log to file for analysis
// Location: ~/Library/Application Support/speekium/analytics.jsonl
```

#### Database Schema for Analytics

```sql
-- Create analytics table (v2 migration)
CREATE TABLE IF NOT EXISTS analytics_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    session_id TEXT,
    properties TEXT, -- JSON
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_analytics_events_type ON analytics_events(event_type);
CREATE INDEX idx_analytics_events_date ON analytics_events(created_at);
```

#### Metrics to Collect Weekly

**Weekly Summary Query** (run every Sunday):
```sql
SELECT
    DATE(created_at) as week,
    COUNT(DISTINCT session_id) as total_sessions,
    SUM(CASE WHEN event_type = 'title_generated' THEN 1 ELSE 0 END) as titles_generated,
    SUM(CASE WHEN event_type = 'session_renamed' THEN 1 ELSE 0 END) as manual_renames,
    SUM(CASE WHEN event_type = 'session_starred' THEN 1 ELSE 0 END) as stars,
    COUNT(DISTINCT session_id) FILTER (WHERE event_type = 'session_opened'
        AND created_at <= datetime('now', '-7 days')) as old_sessions_opened
FROM analytics_events
WHERE created_at >= datetime('now', '-7 days')
GROUP BY DATE(created_at);
```

---

### 1.3 Beta Testing Plan

Since we have no users, we need to **recruit beta testers from Day 1**.

#### Recruitment Strategy

**Target**: 5-10 beta testers by end of Week 1

**Channels**:
1. **GitHub README** - Add "Beta Testing" section with issue tracker link
2. **Social Media** - Twitter/X, Reddit (r/LocalLLaMA, r/Privacy), Hacker News
3. **Communities** - Discord servers for AI/Privacy enthusiasts
4. **Direct Outreach** - Friends, colleagues, local AI meetups

#### Beta Tester Onboarding

**In-App Feedback Mechanism**:
```typescript
// Add feedback button to Settings
<Button onClick={() => openGitHubIssue()}>
  💬 Give Feedback
</Button>

// Pre-fill GitHub issue template:
export const ISSUE_TEMPLATE = `
## Feedback on Conversation Management

**What were you trying to do?**
[Describe your goal]

**What did you expect to happen?**
[Describe expected behavior]

**What actually happened?**
[Describe actual behavior]

**How can we make this better?**
[Any suggestions?]
`;
```

#### Feedback Collection Checklist

- [ ] GitHub issues configured with templates
- [ ] In-app feedback button added
- [ ] Analytics events logging properly
- [ ] Weekly review schedule set (every Monday)

---

### 1.4 Implementation Decision Matrix

**Build Decision**: ✅ **PROCEED WITH MVP**

**Rationale**:
- ✅ Competitive analysis shows standard features are valuable
- ✅ Best practices from 3 competitors align with our MVP scope
- ✅ Low technical risk (well-understood patterns)
- ✅ Analytics from Day 1 will validate/invalidate assumptions quickly
- ✅ Beta testing plan provides learning path

**Scope**:
- **Build**: Auto-titles + Star/Favorite (3-5 days)
- **Defer**: Search, Export, Folders (Phase 2, based on data)
- **Never**: Social features, complex tagging

**No Go/No-Go Decision Needed** - We're building to learn, not validating first.

---

## 🚀 Phase 1: MVP Features (3-5 Days)

### Start Condition
✅ **READY TO BUILD** - Based on competitive analysis and best practices, no validation needed.

**What Changed**:
- **Old approach**: Wait for user data → validate → build (doesn't work for new projects)
- **New approach**: Build MVP → learn from early users → iterate rapidly

### Scope: Two Features Only

---

### Feature 1: Auto-Generated Titles (2-3 days)

#### Problem
Current session titles are generic ("New Session 1", "New Session 2") making it hard to distinguish conversations.

#### Solution
Use AI to generate meaningful titles based on conversation content.

#### User Stories
- **As a user**, I want conversations to have descriptive titles so I can identify them at a glance
- **As a user**, I want titles to be automatically generated so I don't have to manually rename

#### Requirements

**Functional:**
- Generate title from first 3-5 message exchanges
- Title length: 20-50 characters
- Update title automatically after conversation ends
- Allow manual override (rename still available)

**Technical:**
```typescript
// Frontend: Trigger title generation
await invoke('generate_title', { sessionId: session.id });

// Rust Backend (proposal)
#[tauri::command]
async fn generate_title(session_id: String) -> Result<String, String> {
    let messages = db.get_messages(&session_id, 1, 5)?;
    let first_exchange = format!("User: {}\nAssistant: {}",
        messages[0].content,
        messages[1].content
    );

    // Use existing LLM backend (Ollama/Claude)
    let title = llm_backend.generate_summary(&first_exchange, 50).await?;

    // Update session
    db.update_session_title(&session_id, &title)?;
    Ok(title)
}
```

**UI/UX:**
- Display generated title in HistoryDrawer
- Show "AI generating..." indicator during processing
- Fallback: Use first user message if generation fails

#### Success Metrics
- **Engagement**: >60% of sessions have custom titles (vs. "New Session X")
- **User Feedback**: >70% positive on title quality
- **Performance**: Title generation <3 seconds

#### Out of Scope
- Regenerate titles (manual rename only)
- Custom title templates
- Title suggestions to choose from

---

### Feature 2: Star/Favorite (1 day)

#### Problem
Users have no way to mark important conversations for quick access.

#### Solution
Add star icon to conversation cards, filter to show only starred conversations.

#### User Stories
- **As a user**, I want to mark important conversations so I can quickly find them later
- **As a user**, I want to filter to only starred conversations so I can focus on what matters

#### Requirements

**Functional:**
- Star/unstar toggle on each conversation card
- Star icon state: Filled (yellow) vs. Outline
- Filter option: "Show only starred"

**Technical:**
```sql
-- Database Migration
ALTER TABLE sessions ADD COLUMN is_favorite INTEGER DEFAULT 0;
CREATE INDEX idx_sessions_favorite ON sessions(is_favorite, updated_at);

-- Rust Backend
#[tauri::command]
async fn db_toggle_favorite(session_id: String) -> Result<bool, String> {
    let state = db.toggle_favorite(&session_id)?;
    Ok(state)  // Returns new state (true/false)
}

#[tauri::command]
async fn db_list_sessions(include_favorite: Option<bool>) -> Result<Vec<Session>, String> {
    db.list_sessions(include_favorite)
}
```

**UI/UX:**
```typescript
// HistoryDrawer.tsx
<Select value={filter}>
  <option value="all">All Conversations</option>
  <option value="starred">⭐ Starred Only</option>
</Select>

// Session Card
<Button
  variant="ghost"
  size="icon"
  onClick={() => toggleFavorite(session.id)}
>
  <Star className={session.is_favorite ? 'fill-yellow-400' : ''} />
</Button>
```

**Keyboard Shortcut (Polish):**
- `Cmd+Shift+S`: Toggle star on selected/focused conversation

#### Success Metrics
- **Adoption**: >40% of users star at least 1 conversation
- **Usage**: Users filter to "Starred Only" at least 2x/week
- **Retention**: Users with starred conversations have +15% Day-7 retention

#### Out of Scope
- Multiple star levels (just binary: starred/not)
- Star folders/categories
- Star sync across devices (local-only for now)

---

## 📅 Week 2-4: Learning & Iteration Framework

### Week 2: Beta Testing & Data Collection

**Goal**: Collect first real user data

**Activities**:
1. **Recruit 5-10 beta testers**
   - Post on GitHub, Reddit, Twitter
   - Direct outreach to friends/colleagues
   - Target: Privacy enthusiasts, AI tinkerers

2. **Monitor analytics daily**
   - Star rate: How many users star conversations?
   - Title generation: Success rate, quality feedback
   - Feature usage: Which features get used most?

3. **Collect feedback actively**
   - GitHub issues for bug reports
   - In-app feedback button for general feedback
   - Direct messages to beta testers for qualitative insights

**Weekly Review Questions**:
- What surprised you about user behavior?
- What features do users love/hate?
- What's the #1 requested feature?
- What bugs are blocking adoption?

---

### Week 3: Analyze & Decide

**Goal**: Make data-informed decisions about Phase 2

**Analysis Framework**:

**Signal Analysis**:
| Metric | Strong Signal | Weak Signal | No Signal |
|--------|--------------|-------------|-----------|
| **Star Adoption** | >40% beta users | 20-40% | <20% |
| **Title Quality** | >70% positive | 50-70% | <50% |
| **Feature Requests** | Clear pattern | Mixed | No pattern |
| **Bug Count** | <3 critical | 3-10 | >10 |

**Decision Paths**:

**Path A: Strong Positive Signal**
- **Indicators**: High star adoption, positive title quality, clear feature requests
- **Action**: Plan Phase 2 based on top requested features
- **Next**: Prioritize Search or Export (whichever users requested more)

**Path B: Mixed/Weak Signal**
- **Indicators**: Some adoption, mixed feedback, unclear patterns
- **Action**: Deeper user research (5 depth interviews with beta testers)
- **Next**: Ask "What would make this 10x better?" and "What's missing?"

**Path C: No Signal/Negative**
- **Indicators**: Low adoption, negative feedback, many bugs
- **Action**: Fix critical bugs, pause new features, reconsider core value prop
- **Next**: May need to pivot to core experience improvements

---

### Week 4: Iterate or Pivot

**Goal**: Execute on Week 3 decision

**If Iterating (Path A or B)**:
1. **Plan Phase 2** (2-3 days)
   - Create feature spec based on user feedback
   - Estimate effort (target: 3-5 days)
   - Update PRD with Phase 2 scope

2. **Implement Phase 2** (5-7 days)
   - Build top requested feature
   - Add analytics for new feature
   - Test with beta users

3. **Release & Learn** (ongoing)
   - Release to beta testers
   - Collect feedback
   - Continue cycle

**If Pivoting (Path C)**:
1. **Root Cause Analysis** (2-3 days)
   - Why aren't users engaging?
   - Is it a UI/UX issue?
   - Is it a core value prop issue?
   - Is it technical quality (bugs, performance)?

2. **Fix Core Issues** (3-5 days)
   - Address critical bugs
   - Improve performance
   - Simplify UX if needed

3. **Re-test** (ongoing)
   - Release fixes
   - Re-engage beta testers
   - Measure improvement

---

## 🎨 UI/UX Mockups

### HistoryDrawer with New Features

```
┌─────────────────────────────────────────┐
│  🔍 Search...           [⭐ All  [📅]     │  ← Future Phase 2
├─────────────────────────────────────────┤
│  ⭐ Product Strategy Discussion        │  ← Starred
│     AI-generated title    今天 10:30    │  ← Auto-title
│     ┌───────────┬───────────┐          │
│     │ ⭐ ★ ☆   │ 📤 ✏️ 🗑️  │          │  ← Actions
│     └───────────┴───────────┘          │
│                                          │
│  User Interview Notes                   │
│     First user message...  昨天 15:45  │  ← Auto-title
│     ┌───────────┬───────────┐          │
│     │ ☆ ☆ ☆   │ 📤 ✏️ 🗑️  │          │
│     └───────────┴───────────┘          │
└─────────────────────────────────────────┘
```

**Components:**
1. **Search Bar** (Phase 2) - Full-text search input
2. **Filter Dropdown** - All / Starred Only
3. **Star Rating** - 0-5 stars on each card
4. **Auto-Title** - Generated from conversation content
5. **Action Menu** - Export / Rename / Delete

---

## 🔧 Technical Implementation

### Database Schema Changes

```sql
-- Migration v1: Add is_favorite column
ALTER TABLE sessions ADD COLUMN is_favorite INTEGER DEFAULT 0;
CREATE INDEX idx_sessions_favorite ON sessions(is_favorite, updated_at);

-- Migration v2: Add title_source column (auto vs manual)
ALTER TABLE sessions ADD COLUMN title_source TEXT DEFAULT 'auto';
-- Values: 'auto', 'manual'
```

### API Endpoints

```typescript
// Toggle star
invoke('db_toggle_favorite', { sessionId: string })
  → Promise<boolean>

// List sessions (with optional filter)
invoke('db_list_sessions', {
  filter: 'all' | 'starred',
  timeRange: 'today' | 'week' | 'month'
})
  → Promise<Session[]>

// Generate title
invoke('generate_title', { sessionId: string })
  → Promise<string>
```

### Component Architecture

```typescript
// HistoryDrawer.tsx (enhanced)
interface HistoryDrawerProps {
  filter: 'all' | 'starred';
  onFilterChange: (filter: string) => void;
}

// SessionCard.tsx (new)
interface SessionCardProps {
  session: Session;
  onToggleFavorite: (id: string) => void;
  onExport: (id: string) => void;
  onRename: (id: string, newTitle: string) => void;
  onDelete: (id: string) => void;
}
```

---

## ⚠️ Risks & Mitigations

### Risk 1: Low User Adoption

**Probability:** Medium
**Impact:** High

**Mitigation:**
- Start with data collection (Phase 0)
- Build only if evidence supports it
- Quick iteration (3-5 days) to minimize waste

**Contingency Plan:**
- If adoption <20% after Week 2 → Stop, pivot to core experience

---

### Risk 2: Auto-Title Quality

**Probability:** Medium
**Impact:** Medium

**Mitigation:**
- Allow manual rename as fallback
- Use first N messages (not just first)
- Show "AI generating..." indicator to set expectations

**Contingency Plan:**
- If titles are poor quality >30% of time → Fall back to first message preview

---

### Risk 3: Database Performance

**Probability:** Low
**Impact:** Low

**Mitigation:**
- Indexes on `is_favorite` and `updated_at`
- Local SQLite can handle 1000s of sessions easily
- Defer FTS5 (full-text search) to Phase 2

**Contingency Plan:**
- If >1000 sessions per user → Add pagination or virtual scrolling

---

### Risk 4: Opportunity Cost

**Probability:** High
**Impact:** High

**Mitigation:**
- Strict 7-day timebox
- Phase 0 decision gates prevent wasted effort
- Focus on MVP (2 features, not 6)

**Contingency Plan:**
- If core metrics drop (retention, satisfaction) → Immediately pivot

---

## 📈 Success Metrics & Tracking

### Week 1: Development Metrics

| Metric | Measurement Method | Target |
|--------|-------------------|--------|
| **Feature Completeness** | Task completion checklist | 100% |
| **Bug Count** | QA testing | <3 critical |
| **Performance** | Title generation time | <3 seconds |
| **Code Quality** | Linting + review | No warnings |

### Week 2-4: Learning Metrics

| Metric | Measurement Method | Target |
|--------|-------------------|--------|
| **Beta Tester Count** | Signup tracking | ≥5 testers |
| **Star Adoption** | Analytics events | ≥20% of users |
| **Title Success Rate** | Analytics events | ≥80% generated |
| **Feature Requests** | GitHub issues + feedback | Document all |

### Measurement Tools

**Analytics Events** (logged from Day 1):
```typescript
// Track all user interactions
await logEvent({
  event: 'session_starred',
  session_id: 'abc123',
  properties: {
    timestamp: Date.now(),
    user_action: 'click'
  }
});

// Backend saves to analytics_events table
// Weekly query generates summary report
```

**Weekly Review Dashboard**:
```sql
-- Run every Monday morning
SELECT
    'Beta Testers' as metric,
    COUNT(DISTINCT session_id) as value
FROM analytics_events
WHERE created_at >= datetime('now', '-7 days')

UNION ALL

SELECT
    'Star Rate',
    SUM(CASE WHEN event_type = 'session_starred' THEN 1 ELSE 0 END) * 100.0 /
        COUNT(DISTINCT session_id)
FROM analytics_events
WHERE created_at >= datetime('now', '-7 days')

UNION ALL

SELECT
    'Title Success Rate',
    SUM(CASE WHEN event_type = 'title_generated'
        AND JSON_EXTRACT(properties, '$.success') = true THEN 1 ELSE 0 END) * 100.0 /
        COUNT(*) FILTER (WHERE event_type = 'title_generated')
FROM analytics_events
WHERE created_at >= datetime('now', '-7 days');
```

**Feedback Collection**:
- GitHub Issues (with templates)
- In-app feedback button
- Direct beta tester communication

---

## 🚫 Out of Scope (Explicitly NOT in Phase 1)

### Deferred to Phase 2
- **Search functionality** - Build only if data shows need (Phase 2)
- **Export functionality** - Build only if users request (Phase 2)
- **Tags/Labels** - Over-engineering for MVP (use Star instead)
- **Folders/Collections** - Complexity not justified yet
- **Advanced Filtering** - Date range, multiple filters

### Deferred to Phase 3
- **Conversation Sharing** - Export implies sharing, but not focus yet
- **Collaboration Features** - Multi-user, comments, etc.
- **Cloud Sync** - Local-first for now
- **Mobile Apps** - Desktop-only in Phase 1

### Never Build (YAGNI)
- **AI-Powered Summaries** - Too expensive, unclear value
- **Conversation Branching** - Over-complication
- **Templates** - Not core to voice assistant workflow
- **Social Features** - Following, likes, etc. (different product)

---

## 📝 Open Questions

### To Answer During Development (Week 1)

1. **What's the best title generation approach?**
   - Use LLM summary? First message preview? Topic extraction?
   - How long should titles be? (20-50 chars target)

2. **Star interaction design details**
   - Where exactly should star button be placed?
   - Should star filter be prominent or subtle?

3. **Analytics implementation**
   - File-based vs. database-based?
   - Privacy: How to make analytics opt-in only?

### To Answer in Beta Testing (Week 2-4)

1. **Do users actually star conversations?**
   - What makes a conversation "star-worthy"?
   - How often do they filter to starred only?

2. **Are auto-titles helpful or annoying?**
   - Do users manually rename often?
   - What makes a "good" title?

3. **What do users want next?**
   - Search vs. Export vs. Folders?
   - What's the #1 pain point?

### To Answer Long-Term (Phase 2+)

1. **What patterns emerge in real usage?**
   - How do users organize their conversations?
   - What workflows naturally develop?

2. **What's the retention curve?**
   - Do users come back after first week?
   - What features drive retention?

3. **What makes Speekium indispensable?**
   - What can we NOT remove without breaking the product?

---

## 🔄 Revision History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2025-01-13 | Initial PRD based on PM discussion | Product Team |
| | | 9-day plan → 2-week phased validation | |
| | | Added Phase 0 data collection (for existing users) | |
| | | Reduced scope from 6 features to 2 | |
| **1.1** | **2025-01-13** | **Revised for "completely new project"** | **Product Team** |
| | | **Changed approach: Data-driven → Build-to-learn** | |
| | | **Phase 0: Data collection → Competitive analysis** | |
| | | **Added analytics from Day 1** | |
| | | **Added beta testing plan** | |
| | | **Removed all user-data dependencies** | |

---

## ✅ Pre-Implementation Checklist

Before starting Phase 1 development:

- [ ] **Phase 0: Competitive Analysis Complete**
  - [ ] Reviewed 3+ competitor products
  - [ ] Documented key features and insights
  - [ ] Identified best practices for MVP
  - [ ] Confirmed MVP scope (Auto-titles + Star)

- [ ] **Technical Feasibility Confirmed**
  - [ ] Database schema designed (with analytics table)
  - [ ] API endpoints specified
  - [ ] Auto-title implementation approach chosen
  - [ ] Effort estimates confirmed (≤5 days)

- [ ] **Analytics & Feedback Ready**
  - [ ] Analytics events defined
  - [ ] Database schema for analytics created
  - [ ] In-app feedback button designed
  - [ ] GitHub issue templates created
  - [ ] Weekly review process defined

- [ ] **Beta Testing Plan Ready**
  - [ ] Recruitment channels identified
  - [ ] Beta tester onboarding flow designed
  - [ ] Feedback collection mechanism ready
  - [ ] Success metrics defined

- [ ] **Ready to Build**
  - [ ] All dependencies identified
  - [ ] Development environment set up
  - [ ] Task breakdown created
  - [ ] Timeline agreed (3-5 days)

---

## 📚 Appendix

### A. Interview Templates

**User Recruitment Script:**
```
Subject: Help improve Speekium (30 min, $20 gift card)

Hi [Name],

We're working on making Speekium better and would love your input.
We're looking for users who have used Speekium at least 5 times in the
last week.

We'll discuss:
- How you currently use Speekium
- What works well for you
- What could be better

No preparation needed. Reply to this email if interested!

Thanks,
Speekium Product Team
```

**Interview Guide:**
- Record interviews (with permission)
- Take notes in shared doc
- Code responses immediately after
- Look for patterns across interviews

### B. Data Analysis Queries

**Retention Analysis:**
```sql
-- Cohort analysis: users who joined in Week X
-- What % return in Week 1, Week 2, etc.
WITH user_cohorts AS (
    SELECT
        user_id,
        DATE(MIN(created_at)) as cohort_date,
        DATE(created_at) as activity_date
    FROM sessions
    GROUP BY user_id, DATE(MIN(created_at)), DATE(created_at)
)
SELECT
    cohort_date,
    SUM(CASE WHEN activity_date = cohort_date THEN 1 ELSE 0 END) as day_0,
    SUM(CASE WHEN activity_date = DATE(cohort_date, '+1 day') THEN 1 ELSE 0 END) as day_1,
    SUM(CASE WHEN activity_date = DATE(cohort_date, '+7 days') THEN 1 ELSE 0 END) as day_7
FROM user_cohorts
GROUP BY cohort_date
ORDER BY cohort_date;
```

### C. Competitive Analysis

**Feature Comparison:**

| Feature | Speekium | ChatGPT | Otter.ai | Apple Memos |
|---------|----------|---------|----------|--------------|
| Search | ❌ Phase 2 | ✅ | ✅ | ❌ |
| Star/Favorite | ⏳ Phase 1 | ❌ | ✅ | ❌ |
| Folders | ❌ | ✅ | ✅ | ✅ |
| Auto-titles | ⏳ Phase 1 | ❌ | ✅ | ❌ |
| Export | ❌ Phase 2 | ✅ | ✅ | ✅ |
| Tags | ❌ Overkill | ✅ | ✅ | ✅ |
| Local-only | ✅ | ❌ | ✅ | ✅ |
| Voice-first | ✅ | ❌ | ✅ | ❌ |

**Differentiation:**
- Speekium = Local + Privacy + Voice
- Not trying to match ChatGPT's feature set
- Focus on core voice assistant use cases

---

## 🎯 Next Steps

### Week 1: Prepare & Build

**Day 1 (Morning)**: Competitive Analysis (2 hours)
- [ ] Review ChatGPT, Otter.ai, Apple Voice Memos
- [ ] Document key features and best practices
- [ ] Confirm MVP scope (no changes expected)

**Day 1 (Afternoon)**: Technical Setup (2 hours)
- [ ] Design database schema for analytics
- [ ] Define analytics events to track
- [ ] Create GitHub issue templates
- [ ] Plan in-app feedback button

**Day 2-5**: Implementation (3-4 days)
- [ ] Database migration: Add `is_favorite` column + analytics table
- [ ] Backend: Implement star toggle + title generation
- [ ] Frontend: Update HistoryDrawer with star/filter
- [ ] Frontend: Add auto-title generation trigger
- [ ] Testing: QA all features, fix bugs

**Day 6-7**: Polish & Deploy
- [ ] Add keyboard shortcuts
- [ ] Performance testing
- [ ] Code review
- [ ] Deploy to beta testers

---

### Week 2: Beta Testing

**Day 8-10**: Recruitment & Onboarding
- [ ] Post on GitHub, Reddit, Twitter
- [ ] Direct outreach to friends/colleagues
- [ ] Target: 5-10 beta testers
- [ ] Onboard testers, provide feedback guide

**Day 11-14**: Monitor & Collect
- [ ] Daily analytics review
- [ ] Respond to GitHub issues promptly
- [ ] Collect qualitative feedback
- [ ] Document learnings

---

### Week 3: Analyze & Decide

**Day 15-17**: Analysis
- [ ] Compile all analytics data
- [ ] Categorize feedback (bugs/features/UX)
- [ ] Identify patterns
- [ ] Make decision (iterate/pivot)

**Day 18-21**: Execute
- [ ] If iterating: Plan Phase 2
- [ ] If pivoting: Root cause analysis + fix core issues
- [ ] Continue learning loop

---

## 📊 Key Differences: Data-Driven vs Build-to-Learn

| Aspect | Data-Driven (Old) | Build-to-Learn (New) |
|--------|------------------|---------------------|
| **Starting Point** | Requires existing users | Works with zero users |
| **Phase 0** | Collect user data (48 hrs) | Competitive analysis (4 hrs) |
| **Validation** | Pre-build validation | Post-build learning |
| **Success Criteria** | Quantitative metrics | Learning + feedback |
| **Decision Gates** | Go/No-Go before building | Iterate/Pivot after learning |
| **Timeline** | 2 weeks validation + build | 1 week build + learn immediately |
| **Risk** | Building wrong features | Building without validation |

**Why the Change?**
- Speekium is a **completely new project** with **no users**
- Cannot validate assumptions without users to validate with
- Competitive analysis + best practices = sufficient for MVP
- Building quickly + learning from real users = faster product-market fit

---

**End of PRD v1.1**

*This document is a living draft and will be updated as we learn more from beta testing and real user feedback.*
