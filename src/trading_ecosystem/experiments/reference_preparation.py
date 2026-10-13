"""Exact operator-approved reference protocol; no execution methods."""

from typing import Any

from trading_ecosystem.experiments.reference_contract import ReferenceDefinition


def definition(
    project_id: str,
    candidate_id: str,
    configuration_id: str,
    baseline_identity: str,
    build: dict[str, Any],
    data_identity: str,
) -> ReferenceDefinition:
    source = build["content"]["source_sha256"]
    parameters = []
    for key, baseline, choices in (
        ("InpFastEmaPeriod", "20", ["10", "20", "30"]),
        ("InpSlowEmaPeriod", "100", ["60", "100", "140"]),
    ):
        parameters.append(
            dict(
                parameter_name=key,
                native_key=key,
                kind="INTEGER",
                baseline=baseline,
                choices=choices,
                reason=(
                    "OPERATOR_DEFINED_RESEARCH_HYPOTHESIS: "
                    "bounded EMA sensitivity for pipeline qualification"
                ),
                provenance="STRATEGY_SPECIFICATION",
                source_reference="PROJECT_SOURCE SHA256:" + source,
                categorical=False,
                ordered=True,
            )
        )
    return ReferenceDefinition.model_validate(
        dict(
            project_id=project_id,
            candidate_id=candidate_id,
            baseline_configuration_id=configuration_id,
            baseline_identity=baseline_identity,
            reference_protocol="REFERENCE_EMA_PIPELINE_V1",
            source_sha256=source,
            canonical_ex5_sha256=build["content"]["canonical_ex5_sha256"],
            build_identity=build["identity"],
            hypothesis=(
                "Project-owned EMA reference validates pipeline only; "
                "NET_PROFIT is exploratory, not a production optimization rule."
            ),
            parameter_space={"parameters": parameters},
            budget=dict(
                maximum_configurations=9,
                maximum_native_executions=11,
                method="GRID",
                maximum_wall_seconds=6600,
            ),
            split_plan={
                "splits": [
                    dict(start="2026-01-01", end="2026-04-01", purpose="DEVELOPMENT"),
                    dict(start="2026-04-01", end="2026-05-16", purpose="VALIDATION"),
                    dict(start="2026-05-16", end="2026-07-01", purpose="LOCKED_OOS"),
                ]
            },
            objectives=[
                dict(
                    metric="NET_PROFIT",
                    direction="MAXIMIZE",
                    definition="Exploratory pipeline qualification only; activity constraint first",
                )
            ],
            evaluation_method="DECLARED_LEXICOGRAPHIC",
            constraints=[
                dict(
                    metric="TRADE_COUNT",
                    comparator="AT_LEAST",
                    threshold="10",
                    rationale="Minimum observed activity; zero trades is valid but ineligible",
                )
            ],
            cost_assumptions="Native NET_PROFIT; EXPLORATORY_GROSS, no newly qualified costs",
            broker="Exness",
            symbol="XAUUSDm",
            timeframe="M5",
            data_identity=data_identity,
            evidence_classification="EXPLORATORY_GROSS",
        )
    )
