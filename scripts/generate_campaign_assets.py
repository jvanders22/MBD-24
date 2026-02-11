#!/usr/bin/env python3
"""Generate personalized email cadence and tracker CSVs for Debita outreach."""

from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

SENDER_EMAIL = "jvanderspuy@neitec.io"
SENDER_NAME = "Joshua Vanderspuy"
CAMPAIGN_NAME = "debita_institutional_outbound"

TEMPLATES = [
    {
        "step": 1,
        "subject": "Structured Private Credit Access for {firm_name}",
        "body": """Dear {first_name},

I am reaching out because your role in {specific_detail} aligns closely with what we are building at Debita.

We operate a private credit marketplace for institutional asset-based finance. We originate short-duration, asset-backed opportunities—primarily trade finance and receivables portfolios from LATAM and European operators—and provide direct access via a Luxembourg SPV structure.

For allocators, the key points are:

Yield: Target net returns of 12-17%.

Structure: Bankruptcy-remote local trust for receivables; investor capital in Lux SPV.

Transparency: Covenant monitoring with data rooms updated daily/weekly.

The platform is built for institutions seeking efficient, direct access to structured cash flows from hard assets.

If this type of programmatic access is relevant to {firm_name}'s current strategy, I would welcome a brief introductory call.

Regards,""",
        "delay_days": 0,
    },
    {
        "step": 2,
        "subject": "Following up: Debita's model in practice",
        "body": """Hi {first_name},

Following up on my previous note regarding Debita's private credit marketplace.

To make our model more concrete, we recently facilitated a facility for a regional agri-exporter. The structure involved:

Asset: Short-term receivables from investment-grade off-takers.

Vehicle: Investor participation via a Luxembourg-domiciled SPV.

Control: Daily data room updates on collateral pool and covenants.

Yield: Mid-teens net to investors.

This is representative of the asset-backed, institutionally structured opportunities we channel.

If seeing a detailed, anonymized term sheet or case study would be useful for your evaluation, I can arrange it.

Regards,""",
        "delay_days": 5,
    },
    {
        "step": 3,
        "subject": "A specific question for {firm_name}",
        "body": """Hello {first_name},

Circling back once more on the potential fit with Debita.

I understand calendars fill up. My specific question is this: is the primary barrier to evaluating a new channel like ours currently capacity/timing, or a need for more detail on a specific aspect—such as the legal structure, originator quality, or settlement process?

If it's the former, I am happy to connect at a more suitable time next quarter. If it's the latter, I can provide precise information in a two-minute email.

Either way, I aim to be a resource.

Regards,""",
        "delay_days": 10,
    },
    {
        "step": 4,
        "subject": "Closing the loop",
        "body": """Dear {first_name},

I've attempted to reach out a few times regarding Debita's institutional private credit marketplace but have not received a response.

I will therefore assume that sourcing asset-backed credit via our platform is not a priority for {firm_name} at this moment and will not take up more of your inbox.

Should your strategy evolve and direct access to structured, short-duration private credit (12-17% yield, daily data rooms) become relevant, please feel free to reach out.

I wish you success with your current initiatives.

Regards,""",
        "delay_days": 24,
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate campaign queue + tracker CSVs.")
    parser.add_argument("--leads", required=True, help="Path to cleaned leads CSV")
    parser.add_argument("--queue", required=True, help="Output queue CSV")
    parser.add_argument("--tracker", required=True, help="Output tracker CSV")
    parser.add_argument(
        "--start-date",
        default=str(date.today()),
        help="Cadence start date in YYYY-MM-DD format (default: today)",
    )
    return parser.parse_args()


def read_leads(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return rows

    required = {"first_name", "company", "email"}
    missing = [column for column in required if column not in rows[0]]
    if missing:
        raise ValueError(f"Lead file missing required columns: {', '.join(missing)}")

    for lead in rows:
        if not lead.get("specific_detail"):
            lead["specific_detail"] = f"institutional allocation strategy at {lead.get('company', '')}"

    return rows


def write_queue(path: Path, leads: Iterable[dict[str, str]], start_at: date) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "campaign",
        "step",
        "scheduled_date",
        "to_email",
        "to_name",
        "company",
        "from_email",
        "from_name",
        "subject",
        "body",
        "status",
    ]

    written = 0
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for lead in leads:
            first_name = lead.get("first_name", "there").strip() or "there"
            company = lead.get("company", "your firm").strip() or "your firm"
            to_name = f"{lead.get('first_name', '').strip()} {lead.get('last_name', '').strip()}".strip()
            specific_detail = lead.get("specific_detail", "your investment strategy").strip()
            for template in TEMPLATES:
                scheduled_date = start_at + timedelta(days=template["delay_days"])
                writer.writerow(
                    {
                        "campaign": CAMPAIGN_NAME,
                        "step": template["step"],
                        "scheduled_date": scheduled_date.isoformat(),
                        "to_email": lead.get("email", ""),
                        "to_name": to_name,
                        "company": company,
                        "from_email": SENDER_EMAIL,
                        "from_name": SENDER_NAME,
                        "subject": template["subject"].format(
                            first_name=first_name,
                            firm_name=company,
                            specific_detail=specific_detail,
                        ),
                        "body": template["body"].format(
                            first_name=first_name,
                            firm_name=company,
                            specific_detail=specific_detail,
                        ),
                        "status": "scheduled",
                    }
                )
                written += 1
    return written


def write_tracker(path: Path, leads: Iterable[dict[str, str]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "campaign",
        "email",
        "company",
        "current_step",
        "last_sent_date",
        "replied",
        "clicked",
        "opened",
        "bounced",
        "unsubscribed",
        "stop_cadence",
        "notes",
    ]

    written = 0
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for lead in leads:
            writer.writerow(
                {
                    "campaign": CAMPAIGN_NAME,
                    "email": lead.get("email", ""),
                    "company": lead.get("company", ""),
                    "current_step": 0,
                    "last_sent_date": "",
                    "replied": "false",
                    "clicked": "false",
                    "opened": "false",
                    "bounced": "false",
                    "unsubscribed": "false",
                    "stop_cadence": "false",
                    "notes": "",
                }
            )
            written += 1

    return written


def main() -> None:
    args = parse_args()
    start_at = date.fromisoformat(args.start_date)
    leads = read_leads(Path(args.leads))
    queue_rows = write_queue(Path(args.queue), leads, start_at)
    tracker_rows = write_tracker(Path(args.tracker), leads)
    print(f"Generated {queue_rows} scheduled messages for {len(leads)} leads")
    print(f"Generated {tracker_rows} tracker rows")


if __name__ == "__main__":
    main()
