"""HUG 업무대장·공공집계·합성참조·시연 Seed의 출처 메타데이터."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

DataMode = Literal["REFERENCE", "DEMO", "LIVE"]
SourceType = Literal[
    "live_api",
    "public_aggregate",
    "provided_synthetic",
    "demo_scenario",
    "model_poc",
    "user_submitted",
    "cached_demo_prediction",
]


class SourceMetadata(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    data_mode: DataMode
    source_type: SourceType
    source_dataset: str
    as_of_date: str
    scenario_id: str | None = None
    model_version: str | None = None
    input_snapshot: dict[str, Any] | None = None
    is_demo: bool = False
    basis: str


def source_metadata(
    *,
    data_mode: DataMode,
    source_type: SourceType,
    source_dataset: str,
    as_of_date: str,
    basis: str,
    scenario_id: str | None = None,
    model_version: str | None = None,
    input_snapshot: dict[str, Any] | None = None,
    is_demo: bool | None = None,
) -> dict[str, Any]:
    """동일한 출처 구조를 문서 저장과 API 응답에서 재사용한다."""

    return SourceMetadata(
        data_mode=data_mode,
        source_type=source_type,
        source_dataset=source_dataset,
        as_of_date=as_of_date,
        scenario_id=scenario_id,
        model_version=model_version,
        input_snapshot=input_snapshot,
        is_demo=(data_mode == "DEMO") if is_demo is None else is_demo,
        basis=basis,
    ).model_dump()
