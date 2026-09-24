"""Descriptive-only, pairwise-complete statistics with explicit null handling."""

from decimal import Decimal

from trading_ecosystem.domain.arithmetic import arithmetic_context
from trading_ecosystem.features.indicators import mean, quantile, std
from trading_ecosystem.features.registry import CATALOG
from trading_ecosystem.mt5.client import Record
from trading_ecosystem.mt5.normalization import number


def describe(rows: list[Record], *, causal: bool) -> Record:
    result: Record = {}
    with arithmetic_context():
        for d in CATALOG:
            if d.causal != causal:
                continue
            values = [r[d.name] for r in rows if r[d.name] is not None]
            summary: Record = dict(count=len(values), missing_count=len(rows) - len(values))
            if d.dtype in ("decimal", "integer"):
                numeric = [number(v) for v in values]
                for key, value in dict(
                    mean=mean(numeric),
                    median=quantile(numeric, Decimal(".5")),
                    std=std(numeric),
                    min=min(numeric) if numeric else None,
                    p25=quantile(numeric, Decimal(".25")),
                    p75=quantile(numeric, Decimal(".75")),
                    p95=quantile(numeric, Decimal(".95")),
                    max=max(numeric) if numeric else None,
                ).items():
                    summary[key] = str(value) if value is not None else None
            elif d.dtype in ("string", "boolean"):
                counts = {str(v): sum(w == v for w in values) for v in sorted(set(values), key=str)}
                summary["counts"] = counts
                summary["proportions"] = {
                    k: str(Decimal(v) / len(values)) for k, v in counts.items()
                }
            result[d.name] = summary
    return result


def correlation(
    pairs: list[tuple[Decimal | None, Decimal | None]], *, spearman: bool = False
) -> Record:
    clean = [(a, b) for a, b in pairs if a is not None and b is not None]
    if any(not a.is_finite() or not b.is_finite() for a, b in clean):
        raise ValueError("NONFINITE_CORRELATION_INPUT")
    if len(clean) < 3:
        return dict(value=None, count=len(clean), reason="INSUFFICIENT_SAMPLE")
    x, y = [a for a, _ in clean], [b for _, b in clean]
    with arithmetic_context():
        if spearman:

            def ranks(values: list[Decimal]) -> list[Decimal]:
                ordered = sorted(values)
                return [
                    sum((Decimal(i + 1) for i, v in enumerate(ordered) if v == value), Decimal(0))
                    / sum(v == value for v in ordered)
                    for value in values
                ]

            x, y = ranks(x), ranks(y)
        mx, my = sum(x, Decimal(0)) / len(x), sum(y, Decimal(0)) / len(y)
        vx, vy = (
            sum(((v - mx) ** 2 for v in x), Decimal(0)),
            sum(((v - my) ** 2 for v in y), Decimal(0)),
        )
        if vx == 0 or vy == 0:
            return dict(value=None, count=len(clean), reason="CONSTANT_COLUMN")
        value = (
            sum(((a - mx) * (b - my) for a, b in zip(x, y, strict=True)), Decimal(0))
            / (vx * vy).sqrt()
        )
        return dict(value=str(value), count=len(clean), reason=None)
