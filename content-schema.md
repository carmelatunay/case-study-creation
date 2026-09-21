# content.json schema for build_case_study.py

Every value is display-ready text. The builder formats nothing except chart axes, the
monthly table, and the highlighted chart bar. `**double asterisks**` inside body text
renders bold. Sections whose key is missing are skipped, so omit rather than pad.

```json
{
  "brand": {
    "name": "Brand Name",                       // required
    "industry": "Beauty & Cosmetics",
    "category": "Lip, cheek and face products",
    "since": "February 2026",                   // first month on Reacher
    "period": "Feb 2026 – Aug 2026",            // window the stats cover
    "logo_path": "/mnt/user-data/uploads/logo.png",   // optional; transparent PNG ideal
    "photo_path": "/mnt/user-data/uploads/hero.jpg",  // optional; center-cropped to fit
    "photo_fit": "natural"                      // optional; keeps the photo's own aspect (use for square
                                                // product lineups so products aren't cropped)
  },
  "reacher_logo_path": null,                    // optional; a Reacher logo file if the user uploads one.
                                                // Without it a neutral "R" tile + "Reacher" wordmark is drawn.
  "currency_symbol": "$",
  "eyebrow": "Customer Story",

  "headline": "How Brand grew affiliate GMV 9.4x in six months",   // cover, 6–14 words
  "summary": "2–3 sentences: how Reacher made the headline possible.",  // cover note

  "hero_stats": [                               // 3 or 4 tiles; first tile is filled brand blue
    {"value": "9.4x", "label": "Monthly affiliate GMV"},
    {"value": "412K", "label": "Creators reached"},
    {"value": "6,820", "label": "Videos generated"}
  ],

  "by_the_numbers": {
    "eyebrow": "By the numbers",
    "title": "Everything since joining Reacher",
    "intro": "All-time totals from <start> through <end>.",
    "note": "Source line, shop, exact date window."
  },
  "kpis": [                                     // 6 or 9 cells (3-column grid)
    {"value": "412,380", "label": "Creators reached", "sub": "Target Collab invites and DMs"}
  ],

  "about":     {"eyebrow": "About Brand", "title": "...", "body": "text or [paragraphs]",
                "gallery_height": 1.6,           // inches, optional (default 1.75)
                "gallery": [                     // optional, up to 3 tiles (like the ColourPop product strip)
                  {"path": "...", "fit": "contain", "bg": "#FFF8EC"},   // product cut-outs on white
                  {"path": "...", "fit": "cover"}                       // lifestyle photos
                ]},
  "challenge": {"title": "...", "body": ["..."], "quote": "optional", "quote_attribution": "optional"},
  "solution":  {"title": "...", "intro": "...",
                "pillars": [{"title": "...", "body": "...", "stat": "optional proof line"}],   // 4 ideal, 2–6 ok
                "quote": "optional", "quote_attribution": "optional"},

  "before_after": {
    "title": "The lift since joining Reacher",
    "intro": "Which months are compared.",
    "rows": [                                   // 3–5 rows; only rows with a real, non-zero baseline
      {"label": "Monthly affiliate GMV", "before": "$38,020", "after": "$357,400",
       "before_num": 38020, "after_num": 357400, "multiplier": "9.4x",
       "before_label": "Jan 2026", "after_label": "Aug 2026"}     // bar labels, optional
    ],
    "note": "optional footnote"
  },

  "monthly": {
    "title": "Where the program grew the most",
    "insight": "One or two sentences naming the biggest jump and what drove it.",
    "labels": ["Jan 26", "Feb 26"],             // use analyze_monthly.py chart_labels
    "series": [                                 // up to 4 charts, 2x2
      {"name": "Total shop GMV vs. affiliate GMV", "money": true, "values": [affiliate..],
       "values2": [total..], "name1": "Affiliate GMV", "name2": "Total shop GMV"},  // combined chart
      {"name": "Creators reached", "values": [..], "highlight_index": 3}   // optional override
    ],
    "table_series": [                           // optional; defaults to series. Up to 6 columns
      {"name": "Views", "compact": true, "values": [..]}           // compact = 2.1M style
    ],
    "best_month_index": 4,                      // optional; tints that table row
    "show_table": true,
    "note": "Data caveats shown under the table (MTD month, untracked months, definitions)"
  },

  "result": {"title": "...", "body": "text or [paragraphs]",
             "wins": ["**163x creators reached** (context)", "..."],   // 3–5
             "quote": "optional", "quote_attribution": "optional"},

  "page_breaks_before": ["challenge", "result", "monthly"],   // optional, conditional breaks
  "cta": {"title": "Want results like this?", "body": "Book a demo at reacherapp.com."},
  "footnote_short": "Cover footer source line",
  "footnote": "Full data note at the end of the document"
}
```

Notes
- Charts highlight the month with the largest month-over-month increase automatically;
  pass `highlight_index` only if the verified note named a different month.
- If the current month is partial, drop it from `labels`/`series` so charts don't end in a
  misleading dip, or keep it and say "(month to date)" in the insight. Be consistent with
  what the verification note said.
- Keep the headline under ~14 words; the cover steps the font down automatically for
  long ones, but shorter reads better.

- Section order in the PDF follows Reacher's published stories: cover → by the numbers →
  about (+gallery) → challenge → solution → result/wins → before vs. with Reacher →
  month by month → CTA. Put data caveats in `monthly.note` rather than `footnote`; a
  long `footnote` after the CTA can spill onto a page of its own.
- After building, always check the page count and the last page. If the CTA or a note
  lands alone on the final page, shorten text (insight, result body) and rebuild.
