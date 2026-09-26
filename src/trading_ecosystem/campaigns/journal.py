"""Append-only, hash-chained local campaign records; finalized evidence is never overwritten."""

import json
import os
from pathlib import Path

from trading_ecosystem.behavioral_research.contracts import canonical, identity
from trading_ecosystem.campaigns.contracts import RealEaQualificationCampaign
from trading_ecosystem.mt5.client import Record


def create(root: Path, spec: RealEaQualificationCampaign) -> None:
    root.mkdir(parents=True, exist_ok=False)
    (root / "journal").mkdir()
    write_new(root / "campaign.json", spec.model_dump(mode="json"))


def write_new(path: Path, body: object) -> None:
    data = (canonical(body) + "\n").encode()
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def read(root: Path) -> list[Record]:
    rows: list[Record] = []
    spec_hash = identity(json.loads((root / "campaign.json").read_bytes()))
    for i, path in enumerate(sorted((root / "journal").glob("*.json")), 1):
        row: Record = json.loads(path.read_bytes())
        content = {k: v for k, v in row.items() if k != "hash"}
        if (
            path.name != f"{i:08d}.json"
            or row["sequence"] != i
            or row["previous_hash"] != (rows[-1]["hash"] if rows else None)
            or identity(content) != row["hash"]
            or row.get("campaign_hash") != spec_hash
        ):
            raise ValueError("CAMPAIGN_JOURNAL_INTEGRITY_FAILURE")
        rows.append(row)
    return rows


def append(root: Path, kind: str, body: Record) -> None:
    if (root / "manifest.json").exists():
        raise ValueError("FINALIZED_CAMPAIGN_IS_IMMUTABLE")
    rows = read(root)
    value = dict(
        campaign_hash=identity(json.loads((root / "campaign.json").read_bytes())),
        sequence=len(rows) + 1,
        previous_hash=rows[-1]["hash"] if rows else None,
        kind=kind,
        body=body,
    )
    value["hash"] = identity(value)
    write_new(root / "journal" / f"{len(rows) + 1:08d}.json", value)


def status(root: Path) -> Record:
    rows = read(root)
    if (root / "manifest.json").exists():
        from trading_ecosystem.campaigns.finalize import validate

        return validate(root)
    last = rows[-1] if rows else None
    return dict(
        status="INCOMPLETE_REQUIRES_RECONCILIATION",
        last_record=last,
        automatic_resume=False,
        qualification="BLOCKED",
    )


class Journal:
    """Single foreground writer. Revalidate once on open, never replay the journal per poll."""

    def __init__(self, root: Path) -> None:
        self.root = root
        rows = read(root)
        self.sequence = len(rows)
        self.previous_hash = rows[-1]["hash"] if rows else None
        self.campaign_hash = identity(json.loads((root / "campaign.json").read_bytes()))

    def record(self, kind: str, body: Record) -> None:
        if (self.root / "manifest.json").exists():
            raise ValueError("FINALIZED_CAMPAIGN_IS_IMMUTABLE")
        value = dict(
            campaign_hash=self.campaign_hash,
            sequence=self.sequence + 1,
            previous_hash=self.previous_hash,
            kind=kind,
            body=body,
        )
        value["hash"] = identity(value)
        write_new(self.root / "journal" / f"{self.sequence + 1:08d}.json", value)
        self.sequence += 1
        self.previous_hash = value["hash"]
