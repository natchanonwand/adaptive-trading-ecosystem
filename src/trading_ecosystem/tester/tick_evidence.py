"""Offline real-tick evidence: mode, history quality and coverage are separate facts."""

import re
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from trading_ecosystem.domain.primitives import FrozenModel
from trading_ecosystem.tester.parser import Cells, decode_report


class Coverage(StrEnum):
    VERIFIED = "REAL_TICK_COVERAGE_VERIFIED_100"
    PARTIAL = "REAL_TICK_COVERAGE_PARTIAL"
    UNVERIFIED = "REAL_TICK_EVIDENCE_UNVERIFIED"
    UNAVAILABLE = "REAL_TICKS_POSITIVELY_UNAVAILABLE"


class TickEvidence(FrozenModel):
    requested_model: str
    native_model_evidence: tuple[str, ...]
    real_tick_coverage_percentage: Decimal | None
    coverage_source: tuple[str, ...]
    coverage_confidence: Literal["EXPLICIT", "CONFLICTING", "UNKNOWN"]
    fallback_generated_tick_evidence: tuple[str, ...]
    unavailable_evidence: tuple[str, ...]
    history_range_evidence: tuple[str, ...]
    history_quality: str | None
    modeling_quality: str | None
    ticks_count: int | None
    bars_count: int | None
    classification: Coverage
    full_real_tick_requirement: Literal["PASS", "FAIL", "UNVERIFIED"]


def extract(requested_model: str, log: str, report: bytes | None = None) -> TickEvidence:
    """Accept explicit real-tick percentages from labelled cells or native journal text.

    A generic History/Modeling Quality percentage is never a real-tick percentage.
    Duplicate/conflicting evidence and generated-tick substitution cannot establish 100%.
    HTML is parsed as text only; scripts, charts and assets are never executed/fetched.
    """
    fields: dict[str, list[str]] = {}
    if report is not None:
        parser = Cells()
        parser.feed(decode_report(report))
        for row in parser.rows:
            for i, cell in enumerate(row[:-1]):
                fields.setdefault(cell.rstrip(":").casefold(), []).append(row[i + 1])
    percentages: list[Decimal] = []
    sources: list[str] = []
    invalid = False

    def percentage(value: str, source: str) -> None:
        nonlocal invalid
        parsed = Decimal(value)
        if not 0 <= parsed <= 100:
            invalid = True
        else:
            percentages.append(parsed)
            sources.append(source)

    for log_match in re.finditer(r"(?<![\d.])(\d+(?:\.\d+)?)%\s+real ticks\b", log, re.I):
        percentage(log_match[1], "NATIVE_LOG_EXPLICIT_REAL_TICKS")
    for label in ("history quality", "real ticks", "real tick coverage", "real ticks (%)"):
        for value in fields.get(label, []):
            match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*%\s+real ticks", value, re.I)
            if match is None and label != "history quality":
                match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*%", value)
            if match:
                percentage(match[1], "REPORT:" + label)
    fallback = tuple(
        line.strip()
        for line in log.splitlines()
        if re.search(r"generated ticks|tick generation|discarded|ticks? substituted", line, re.I)
    )
    unavailable = tuple(
        line.strip()
        for line in log.splitlines()
        if re.search(r"real ticks (?:absent|unavailable)|no real ticks available", line, re.I)
    )
    native = tuple(
        line.strip()
        for line in log.splitlines()
        if re.search(r"generating based on real ticks|real ticks begin from", line, re.I)
    ) + tuple("REPORT:Model=" + value for value in fields.get("model", []))
    ranges = tuple(fields.get("period", [])) + tuple(
        line.strip()
        for line in log.splitlines()
        if re.search(r"history (?:ticks )?synchronized from|history begins from", line, re.I)
    )
    distinct = set(percentages)
    conflict = invalid or len(distinct) > 1 or (Decimal(100) in distinct and bool(fallback))
    conflict = conflict or (bool(percentages) and bool(unavailable))
    coverage = percentages[0] if len(distinct) == 1 and not invalid else None
    if conflict:
        classification = Coverage.UNVERIFIED
    elif unavailable:
        classification = Coverage.UNAVAILABLE
    elif coverage is not None:
        classification = Coverage.VERIFIED if coverage == 100 else Coverage.PARTIAL
    elif fallback:
        classification = Coverage.PARTIAL
    else:
        classification = Coverage.UNVERIFIED

    def one(label: str) -> str | None:
        values = fields.get(label, [])
        return values[0] if len(values) == 1 else None

    def count(label: str) -> int | None:
        value = one(label)
        return int(value) if value and re.fullmatch(r"\d+", value) else None

    return TickEvidence(
        requested_model=requested_model,
        native_model_evidence=native,
        real_tick_coverage_percentage=coverage,
        coverage_source=tuple(sources),
        coverage_confidence=(
            "CONFLICTING" if conflict else "EXPLICIT" if coverage is not None else "UNKNOWN"
        ),
        fallback_generated_tick_evidence=fallback,
        unavailable_evidence=unavailable,
        history_range_evidence=ranges,
        history_quality=one("history quality"),
        modeling_quality=one("modeling quality"),
        ticks_count=count("ticks"),
        bars_count=count("bars"),
        classification=classification,
        full_real_tick_requirement=(
            "PASS"
            if classification == Coverage.VERIFIED
            else "UNVERIFIED"
            if classification == Coverage.UNVERIFIED
            else "FAIL"
        ),
    )
