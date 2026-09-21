---
name: case-study-creation
description: >
  Build a Reacher customer case study for a TikTok Shop brand from its live Reacher
  account data, patterned on Reacher's published customer stories (e.g.
  reacherapp.com/customers/colourpop): a headline built on the account's biggest win, a
  summary of how Reacher made it possible, all-time KPIs since the brand joined Reacher,
  about / challenge / solution / result sections, before-vs-after lifts and
  month-by-month trend charts. Sends a verification note in chat first, asks for a brand
  logo and product photo, and only after the user confirms renders a designed PDF. Use
  this skill WHENEVER the user asks for a case study, customer story, success story,
  client win write-up, testimonial page, "results story", or a "show what Reacher did for
  [brand]" document, even if they don't say "case study". Requires the Reacher connector.
  Not for weekly/monthly performance reports or audits (use those skills).
---

# Case Study Creation

A case study is a sales document. Its job is to make a prospect think "Reacher could do
that for us", so every section drives toward one claim: **Reacher ran this brand's
creator program end to end, and the shop scaled because of it.** The numbers make that
claim credible; the narrative explains how the platform produced them.

The flow has a hard gate in the middle: **pull and analyze → send the verification note
→ wait → build the PDF.** Never render the PDF before the user confirms the note, because
a case study goes in front of prospects and the client, and a wrong number there is
expensive.

## Reference pattern

Mirror the structure of Reacher's published stories (ColourPop is the model):

1. Headline "How [Brand] [did X, with a number] in [time]" + one-line subhead
2. Brand × Reacher lockup, industry, product category
3. Three hero stats (e.g. 163× creators reached, 6.5× sample requests, 5× approvals)
4. About the brand (+ product photo strip) → The Challenge → The Solution (named
   pillars) → The Result (narrative + "Wins" list) → Before vs. with Reacher
   comparisons → growth charts → CTA ("Want results like this?")

For Reacher Plus Managed Service accounts, credit "Reacher Plus" as the actor, use the
brand-managed period as the "before", and for brand-new shops label the story
"Customer Story · Cold Start".

The PDF adds what the user asked for on top of that pattern: an all-time "By the
numbers" KPI grid since joining Reacher, and month-by-month trend charts showing where
the program improved the most.

## Step 1 — Confirm the shop

Call `list_shops`. If the user named a brand, match it and confirm the shop_id in one
line; if not, ask which brand. Never assume. Also call `shop_connection_health` for
that shop: if `is_collecting` is false, recent months may read as zero because
collection stopped, not because activity did. Flag that in the note.

## Step 2 — Pull the data

Load tools with `tool_search` first. Pull everything before writing anything.

**Monthly series (the backbone).** `timeseries_metrics` with `granularity: "month"`,
`start_date` = today minus 729 days (the tool's max is 730), `end_date` = today, and
metrics: `creators_reached`, `tc_invites_sent`, `creators_messaged`, `sample_requests`,
`samples_approved`, `videos_posted`, `video_views`, `gmv`, `total_gmv`, `live_gmv`,
`new_creators_posting`, `gmv_driving_videos`, `creators`.

**Reacher start month.** If the user gave a start date, use it. Otherwise take the first
month where `creators_reached` or `tc_invites_sent` is meaningfully above zero, since
outreach is the activity that only exists once Reacher is running. State the detected
month in the verification note so the user can correct it. If activity starts in the
very first month of the 730-day window, the account may predate the window: say the
totals cover "the last 24 months" rather than "since joining".

**Always feature two GMV metrics side by side:** affiliate GMV (`gmv`, creator-driven)
and total shop GMV (`total_gmv`, all channels from Seller Center). Both appear in the
summary note, the cover hero stats, the KPI grid (first two cells), the before/after rows,
the monthly table, and one combined chart (total drawn behind affiliate via `values2`).
Label them consistently: "Affiliate GMV" and "Total shop GMV". Total shop GMV often
makes the stronger "biggest month ever" claim; affiliate GMV usually has the bigger
multiplier. Use whichever is stronger for the headline and feature the other right beside it.

**Creators in the program.** `crm_roster_list` with `page_size: 1` and read the total
count from the response. That is the all-time roster of creators filed under the shop.

**How Reacher was used (for the Solution pillars).** `automation_stats` for automation
counts `by_type` (Target Collab, Message, Email, Sample Request Processing, and so on)
and its rolled-up metrics. Optionally `automations_list` for the top automations and
`products_list` for the hero products by GMV. If the shop runs GMV Max, `list_campaigns`
(GMV Max) is worth one call. Only claim a pillar the data shows was used.

**Optional flex.** `si_my_benchmarks` gives `percentile_segment`; a line like "top 10%
of shops in its GMV segment" is strong if true.

## Step 3 — Analyze

Normalize the monthly pull into the shape documented at the top of
`scripts/analyze_monthly.py` (months oldest first, `start_month`, `partial_last_month`,
metric arrays) and run:

```bash
python <skill-dir>/scripts/analyze_monthly.py monthly.json
```

It returns all-time totals since the start month, before/after lifts, the best month and
biggest month-over-month jump per metric, and ranked headline candidates. Use its numbers
rather than doing arithmetic in your head.

Rules the numbers must follow:

- **All-time totals** sum only flow metrics (reached, samples, videos, views, GMV).
  `creators` is a distinct monthly count and must never be summed.
- **"Samples sent out"** = `samples_approved` summed since start. Label it "samples
  approved / sent" and say so in the note, since approved is what the data records.
- **Multipliers need a real baseline.** A metric that was zero before Reacher (usually
  outreach) is framed "from 0 to 305K", never as "∞×" or an invented multiple. Prefer the
  baseline month (the month before Reacher) vs. the latest full month; fall back to first
  Reacher month vs. latest full month when there is no baseline.
- **Partial current month** is excluded from lifts, best months and jumps. It can count
  toward totals if the window is labeled "through [date]".
- Round consistently in display: `9.4x`, `$357K` / `$1.42M`, `412K`. Full precision stays
  in the KPI grid.

**Choosing the headline.** Start from the top `headline_candidates`. GMV lifts and record
GMV months usually win because they are the business outcome; volume metrics (reach,
samples) make better hero stats and pillar proof. Pick the single most impressive *and*
defensible claim. Pattern: "How [Brand] grew affiliate GMV 9.4x in six months" or "How
[Brand] hit its biggest month ever with $1.08M in GMV". Then write the summary note: 2–3
sentences explaining which Reacher capabilities produced that result, citing one or two
supporting numbers.

## Step 4 — Send the verification note (then stop)

Post this in chat, not as a file. Keep it scannable; this is the one place in the flow
where structure matters more than prose. Then end the turn and wait.

```
**Case study draft: [Brand] × Reacher** — please verify before I design the PDF

**Headline:** How [Brand] ...
**Summary note:** [2–3 sentences on how Reacher made it possible]

**Account window:** On Reacher since [Month YYYY] (detected from first outreach — correct me if wrong) · data through [date]

**All-time stats since joining Reacher**
| Metric | Value |
| Creators reached (outreach) | 412,380 |
| Creators in the program (CRM) | 9,214 |
| Samples approved / sent | 14,905 |
| Videos generated | 6,820 |
| Total video views | 118.6M |
| Total shop GMV (all channels) | $1.71M |
| Affiliate GMV | $1.42M |
(+ any extra KPI worth featuring; keep the grid at 6, 9 or 12 cells)

**Hero stats for the cover:** 9.4x GMV · 412K reached · 6,820 videos

**Before → with Reacher:** [baseline month] vs [latest full month], one line per metric

**Month by month:** compact table of the charted metrics + "Biggest jump: [metric] in [month], +X"

**Narrative draft:** About (1–2 lines) · Challenge (inferred from the pre-Reacher numbers) · Solution pillars (only those the automation data supports) · Result + Wins

**Needs your input**
1. Upload a **brand logo** (PNG with transparent background works best) and a **product or brand photo**. They go on the cover next to the Reacher lockup.
2. Is the Challenge accurate? It's inferred from the data; you know the real story.
3. Optional: a client quote, and confirmation the brand can be named publicly.

Reply "confirmed" (or with edits) and I'll build the PDF.
```

Everything in the note must be exactly what will appear in the PDF. If the user edits
anything, apply it and use the edited version; re-send the note only if the changes are
substantial.

## Step 5 — Build the PDF (after confirmation)

`<skill-dir>` is wherever this SKILL.md lives (usually `/mnt/skills/user/case-study-creation`).
Placing the uploads: logo → `brand.logo_path`; the best product shot → cover
`brand.photo_path` (square lineups: `"photo_fit": "natural"`); up to 3 more images →
`about.gallery` (product cut-outs `contain`, lifestyle shots `cover`).

1. Check `/mnt/user-data/uploads` for the logo and photo. If the user skipped them, build
   anyway: the builder falls back to the brand name as text and a brand-tinted photo
   panel. Mention that they can send the images later for a rebuild. If only one image was
   uploaded and it's unclear which it is, look at it.
2. Write `content.json` following `references/content-schema.md`, using only confirmed
   text and numbers.
3. Build:
   ```bash
   python <skill-dir>/scripts/build_case_study.py content.json \
     /mnt/user-data/outputs/<brand-slug>-reacher-case-study.pdf
   ```
4. **Control pagination.** For 5-page layouts set
   `"page_breaks_before": ["challenge", "result", "monthly"]` so sections start on clean
   pages (the breaks are conditional, so they never create blank pages).
5. **Inspect before sending.** `pdftoppm -r 60 -png` the PDF and view the pages. Check:
   headline fits the cover band, logo is legible on the white tile, the photo crop shows
   the product, no section is orphaned at a page bottom, the monthly table isn't split.
   Fix content (shorter headline, fewer pillars, trimmed body) and rebuild if needed.
6. `present_files` with the PDF, then one or two sentences: what's in it and anything the
   user should double-check before sharing.

## Voice

Reacher's external voice, as on the published customer stories: confident, specific,
plain. Reacher is the actor ("Reacher automated...", "Through Reacher, the team...").

- Conclusion-first headlines on every section ("Growth capped by manual work", not
  "Background").
- Every claim is tied to a number from the data. No hype words (revolutionary,
  game-changing, skyrocketed).
- Section titles and pillar names are short (2–6 words). Body paragraphs 2–4 sentences.
- The Challenge describes the pre-Reacher state honestly from the data (low outreach
  volume, slow approvals, flat GMV). Mark it as inferred in the verification note.
- **Never fabricate a client quote.** Pull quotes use the user's supplied quote, or a
  sentence describing the working model written as narrative (not attributed to a person),
  or are omitted.
- Name the brand only if the user confirms it's allowed; otherwise describe it ("a clean
  beauty brand") and drop the logo.

## Solution pillars

Map what the account actually used to pillars, and give each a proof stat. Typical set
(pick 4 that the data supports):

| Pillar | Evidence in data |
|---|---|
| Automated creator outreach | Target Collab / Message automations; creators reached, TC invites |
| Sample approvals on autopilot | Sample Request Processing automations; samples approved |
| Hero product targeting | Top products by GMV; automations anchored to product IDs |
| CRM and content tracking | Creators in the CRM roster; videos posted, GMV-driving videos |
| Re-engagement / email | Email automations, emails sent |
| GMV Max amplification | GMV Max campaigns and spend |
| Reporting and strategic pivots | Always true when the user's team reports on the account; keep it generic |

## Files

- `scripts/analyze_monthly.py` — totals, lifts, jumps, headline candidates.
- `scripts/build_case_study.py` — renders the PDF (cover, KPI grid, narrative, pillar
  cards, before/after bars, 2×2 monthly charts + table, wins, CTA). Poppins fonts are
  bundled in `assets/fonts`; brand tokens match Reacher's other deliverables
  (brand `#3559E9`, ink `#101828`).
- `references/content-schema.md` — every field the builder accepts.
