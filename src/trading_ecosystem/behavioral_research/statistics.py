"""Count-aware Decimal statistics. Intervals describe sampling assumptions, not EA rules."""

from collections.abc import Sequence
from decimal import Decimal
from random import Random

from trading_ecosystem.behavioral_research.contracts import Record, ResearchConfig
from trading_ecosystem.domain.arithmetic import arithmetic_context
from trading_ecosystem.features.indicators import quantile, std
from trading_ecosystem.features.statistics import correlation

D = Decimal


def number(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("BOOLEAN_IS_NOT_NUMERIC")
    result = D(str(value))
    if not result.is_finite():
        raise ValueError("NONFINITE_RESEARCH_VALUE")
    return result


def counts(n: int, known: int) -> Record:
    if not 0 <= known <= n:
        raise ValueError("INVALID_SAMPLE_COUNTS")
    return dict(n=n, known_count=known, missing_count=n - known)


def tier(n: int, config: ResearchConfig) -> str:
    return (
        "STRONGER_EVIDENCE"
        if n >= config.stronger_n
        else "USABLE"
        if n >= config.usable_n
        else "PRELIMINARY"
        if n >= config.preliminary_n
        else "INSUFFICIENT"
    )


def numeric(values: Sequence[object]) -> Record:
    clean = [v for x in values if (v := number(x)) is not None]
    result = counts(len(values), len(clean))
    with arithmetic_context():
        result.update(
            {
                k: str(v) if v is not None else None
                for k, v in dict(
                    mean=sum(clean, D(0)) / len(clean) if clean else None,
                    median=quantile(clean, D(".5")),
                    std=std(clean),
                    min=min(clean) if clean else None,
                    max=max(clean) if clean else None,
                    p25=quantile(clean, D(".25")),
                    p75=quantile(clean, D(".75")),
                ).items()
            }
        )
    return result


def rate(values: list[bool | None]) -> Record:
    if any(v is not None and type(v) is not bool for v in values):
        raise ValueError("RATE_REQUIRES_BOOLEAN_OR_NULL")
    clean = [v for v in values if v is not None]
    n, successes = len(clean), sum(clean)
    result = dict(**counts(len(values), n), successes=successes, value=None, interval=None)
    if n:
        with arithmetic_context():
            p, z = D(successes) / n, D("1.959963984540054")
            denominator = 1 + z * z / n
            center = (p + z * z / (2 * n)) / denominator
            radius = z * ((p * (1 - p) + z * z / (4 * n)) / n).sqrt() / denominator
            result.update(
                value=str(p),
                interval=[str(max(D(0), center - radius)), str(min(D(1), center + radius))],
            )
    result["interval_basis"] = "WILSON_95_IID_EPISODES_EXPLORATORY_DEPENDENCE_NOT_CORRECTED"
    return result


def categories(values: Sequence[object]) -> Record:
    known = [str(v) for v in values if v is not None]
    result = counts(len(values), len(known))
    result["categories"] = {
        k: rate([None if v is None else str(v) == k for v in values]) for k in sorted(set(known))
    }
    return result


def association(a: list[object], b: list[object], *, spearman: bool = True) -> Record:
    if len(a) != len(b):
        raise ValueError("UNPAIRED_ASSOCIATION")
    pairs = [(number(x), number(y)) for x, y in zip(a, b, strict=True)]
    value = correlation(pairs, spearman=spearman)
    return dict(
        **counts(len(pairs), value["count"]),
        value=value["value"],
        reason=value["reason"],
        method="SPEARMAN" if spearman else "PEARSON",
        interpretation="DESCRIPTIVE_ASSOCIATION_ONLY",
    )


def cramers_v(a: list[object], b: list[object]) -> Record:
    if len(a) != len(b):
        raise ValueError("UNPAIRED_ASSOCIATION")
    pairs = [(str(x), str(y)) for x, y in zip(a, b, strict=True) if x is not None and y is not None]
    result = dict(
        **counts(len(a), len(pairs)),
        value=None,
        reason=None,
        method="CRAMERS_V_UNCORRECTED_DESCRIPTIVE",
    )
    xs, ys = sorted({x for x, _ in pairs}), sorted({y for _, y in pairs})
    if len(pairs) < 3 or min(len(xs), len(ys)) < 2:
        result["reason"] = "INSUFFICIENT_OR_CONSTANT_CATEGORIES"
        return result
    with arithmetic_context():
        chi = D(0)
        for x in xs:
            for y in ys:
                expected = (
                    D(sum(u == x for u, _ in pairs)) * sum(v == y for _, v in pairs) / len(pairs)
                )
                observed = sum(u == x and v == y for u, v in pairs)
                chi += (observed - expected) ** 2 / expected
        result["value"] = str((chi / (len(pairs) * min(len(xs) - 1, len(ys) - 1))).sqrt())
    return result


def median_interval(values: list[object], groups: list[str], config: ResearchConfig) -> Record:
    if len(values) != len(groups):
        raise ValueError("UNPAIRED_BOOTSTRAP_GROUPS")
    clean: dict[str, list[Decimal]] = {}
    for value, group in zip(values, groups, strict=True):
        parsed = number(value)
        if parsed is not None:
            clean.setdefault(group, []).append(parsed)
    result = dict(
        **counts(len(values), sum(map(len, clean.values()))),
        interval=None,
        independent_units=len(clean),
        reason=None,
        seed=config.seed,
        method="SESSION_CLUSTER_PERCENTILE_MEDIAN_95_EXPLORATORY",
    )
    if len(clean) < 2:
        result["reason"] = "AT_LEAST_TWO_KNOWN_SESSIONS_REQUIRED"
        return result
    rng, keys, medians = Random(config.seed), sorted(clean), []
    with arithmetic_context():
        for _ in range(config.bootstrap_replicates):
            sample = [v for _ in keys for v in clean[rng.choice(keys)]]
            median = quantile(sample, D(".5"))
            assert median is not None
            medians.append(median)
        result["interval"] = [str(quantile(medians, D(".025"))), str(quantile(medians, D(".975")))]
    return result


def bin_values(values: list[object], edges: list[Decimal]) -> list[str | None]:
    if edges != sorted(set(edges)) or any(not v.is_finite() for v in edges):
        raise ValueError("INVALID_BIN_EDGES")
    # Right-open bins: a value exactly at an edge belongs to the upper bin.
    return [
        None if (v := number(x)) is None else f"bin_{sum(v >= e for e in edges)}" for x in values
    ]


def quantile_edges(values: list[object], config: ResearchConfig) -> list[Decimal]:
    clean = [v for x in values if (v := number(x)) is not None]
    with arithmetic_context():
        return sorted(
            {v for p in config.quantile_probabilities if (v := quantile(clean, p)) is not None}
        )


def proportion_effect(a: list[bool | None], b: list[bool | None]) -> Record:
    left, right = rate(a), rate(b)
    result: Record = dict(
        left=left, right=right, difference=None, odds_ratio=None, odds_reason=None
    )
    if left["value"] is None or right["value"] is None:
        result["odds_reason"] = "MISSING_GROUP"
        return result
    with arithmetic_context():
        result["difference"] = str(D(left["value"]) - D(right["value"]))
        ac, bc = left["successes"], left["known_count"] - left["successes"]
        cc, dc = right["successes"], right["known_count"] - right["successes"]
        if bc * cc == 0:
            result["odds_reason"] = "ZERO_DENOMINATOR_NO_PSEUDOCOUNT"
        else:
            result["odds_ratio"] = str(D(ac * dc) / (bc * cc))
    return result
