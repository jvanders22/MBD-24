# MBD-24 — Debita.io B2B2C Outreach Builder

This project creates send-ready CSVs for a Debita.io outreach cadence using your four provided templates.

## What gets generated

1. `output/leads_clean.csv`: validated and normalized lead list.
2. `output/campaign_queue.csv`: one row per email per lead with personalized subject/body and scheduled date.
3. `output/campaign_tracker.csv`: per-lead tracking status (opened/clicked/replied/etc.).

Sender identity in queue rows is set to:
- `from_name`: Joshua Vanderspuy
- `from_email`: jvanderspuy@neitec.io

Email bodies intentionally end with just:
- `Regards,`

This is so your Gmail signature can append automatically.

## Scripts

- `scripts/build_leads.py`
  - Validates required columns.
  - Deduplicates by email.
  - Filters common free/personal email domains.
  - Preserves optional `specific_detail` for personalization.

- `scripts/generate_campaign_assets.py`
  - Applies your exact 4 templates.
  - Personalizes `{first_name}`, `{firm_name}`, `{specific_detail}`.
  - Schedules cadence at Day 0, Day 5, Day 10, Day 24.
  - Produces queue and tracker CSVs.

## Input format

Required columns:
- `first_name`, `last_name`, `title`, `company`, `email`, `source`, `region`, `legal_basis`

Optional column:
- `specific_detail`

## Run (step-by-step)

```bash
python3 scripts/build_leads.py \
  --input data/leads_input_template.csv \
  --output output/leads_clean.csv

python3 scripts/generate_campaign_assets.py \
  --leads output/leads_clean.csv \
  --queue output/campaign_queue.csv \
  --tracker output/campaign_tracker.csv \
  --start-date 2026-02-11
```

## How to use it in practice

1. Fill `data/leads_input_template.csv` with your real prospects.
2. Run the two commands above.
3. Open `output/campaign_queue.csv` and filter by `scheduled_date` and `step`.
4. Use those rows in your sender workflow (mail merge tool/CRM/Gmail workflow) and keep Gmail signature enabled.
5. Update `output/campaign_tracker.csv` after each send or engagement event:
   - set `opened`, `clicked`, `replied`, etc.
   - set `stop_cadence=true` when someone replies/unsubscribes/bounces.
