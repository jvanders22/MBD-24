#!/usr/bin/env python3
"""Build a compliant B2B2C lead CSV from user-supplied contacts.

This tool does NOT scrape personal emails. It transforms and validates
contacts from lawful/public/consented sources into a clean CSV for outreach.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

FREE_EMAIL_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "aol.com",
    "proton.me",
    "protonmail.com",
    "icloud.com",
}


@dataclass
class Lead:
    first_name: str
    last_name: str
    title: str
    company: str
    email: str
    source: str
    region: str
    legal_basis: str
    specific_detail: str

    @property
    def domain(self) -> str:
        return self.email.split("@", 1)[1].lower() if "@" in self.email else ""


REQUIRED_COLUMNS = [
    "first_name",
    "last_name",
    "title",
    "company",
    "email",
    "source",
    "region",
    "legal_basis",
]

OPTIONAL_COLUMNS = ["specific_detail"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and normalize a leads CSV.")
    parser.add_argument("--input", required=True, help="Path to source CSV")
    parser.add_argument("--output", required=True, help="Path to cleaned CSV")
    return parser.parse_args()


def _normalize(value: str) -> str:
    return (value or "").strip()


def load_leads(path: Path) -> list[Lead]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("Input file is missing a header row.")

        missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing:
            raise ValueError(f"Input CSV missing required columns: {', '.join(missing)}")

        leads: list[Lead] = []
        for row in reader:
            required_values = {col: _normalize(row.get(col, "")) for col in REQUIRED_COLUMNS}
            specific_detail = _normalize(row.get("specific_detail", ""))
            if not specific_detail:
                specific_detail = f"institutional allocation strategy at {required_values['company']}"
            lead = Lead(**required_values, specific_detail=specific_detail)
            leads.append(lead)
        return leads


def validate_leads(leads: Iterable[Lead]) -> tuple[list[Lead], list[str]]:
    valid: list[Lead] = []
    issues: list[str] = []
    seen: set[str] = set()

    for idx, lead in enumerate(leads, start=2):
        if not lead.email or "@" not in lead.email:
            issues.append(f"Row {idx}: invalid email format")
            continue

        key = lead.email.lower()
        if key in seen:
            issues.append(f"Row {idx}: duplicate email {lead.email}")
            continue
        seen.add(key)

        if lead.domain in FREE_EMAIL_DOMAINS:
            issues.append(
                f"Row {idx}: skipped free/personal mailbox domain {lead.domain} for {lead.email}"
            )
            continue

        if not lead.company:
            issues.append(f"Row {idx}: missing company for {lead.email}")
            continue

        valid.append(lead)

    return valid, issues


def write_leads(path: Path, leads: Iterable[Lead]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = REQUIRED_COLUMNS + OPTIONAL_COLUMNS + ["status", "segment", "owner"]

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for lead in leads:
            writer.writerow(
                {
                    **{c: getattr(lead, c) for c in REQUIRED_COLUMNS + OPTIONAL_COLUMNS},
                    "status": "ready",
                    "segment": "b2b2c",
                    "owner": "",
                }
            )


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    leads = load_leads(input_path)
    valid, issues = validate_leads(leads)
    write_leads(output_path, valid)

    print(f"Loaded {len(leads)} rows")
    print(f"Wrote {len(valid)} valid rows to {output_path}")
    if issues:
        print("\nValidation notes:")
        for issue in issues:
            print(f"- {issue}")


if __name__ == "__main__":
    main()
