"""위험진단 Rule-based Fallback 엔진.

정식 ML 학습용 feature table(processed_risk_features_v1.parquet)이 없고, CODEF 등기부는 여전히
100% mock, 공시가격 3종도 VWorld URL 미확정으로 mock 상태다(docs_summary.md 충돌사항 6 참고).
따라서 이 모듈은 ML 추론을 흉내내지 않고, "확인된 사실만 점수화 + 데이터 공백은 확신도/완결성으로
별도 표기"하는 규칙 기반 엔진만 구현한다.

지켜야 할 3가지 구분(과제 지시사항 4절):
  1) 실제로 위험이 낮음        -> 확인 가능한 데이터가 위험 신호 없음을 보여줄 때만
  2) 데이터 부족으로 판단 불가  -> registry/official_price가 mock이거나 없으면 항상 이 상태
  3) 실제 위험 신호가 확인됨    -> live 데이터에서 임계값을 넘는 신호가 확인된 경우만

절대 규칙: jeonse_ratio/mortgage_ratio/rights_burden_ratio/has_seizure는 registry 또는
공시가격 출처가 "api_live"일 때만 계산한다. mock/미확보 상태에서는 절대 계산하지 않고
missing_fields + source_status로만 드러낸다(과제 지시사항 4절 "계산 금지 또는 제한").
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.enums import RiskGrade

# 데이터 완결성/확신도 계산에 사용하는 카테고리별 가중치. registry/official_price가
# 위험도 산정에 가장 결정적이므로 가중치를 높게 둔다.
_COMPLETENESS_WEIGHTS: dict[str, float] = {
    "registry": 0.35,
    "official_price": 0.25,
    "building_registry": 0.15,
    "business_status": 0.15,
    "dart": 0.10,
}


@dataclass
class RiskFactorItem:
    code: str
    title: str
    severity: str  # low | medium | high
    description: str


@dataclass
class RiskEngineInputs:
    deposit: int
    landlord_type: str
    housing_type: str

    registry_status: str  # live | mock | missing
    has_seizure: bool | None = None
    mortgage_ratio: float | None = None
    rights_burden_ratio: float | None = None

    official_price_status: str = "missing"  # live | mock | missing
    official_price: int | None = None
    jeonse_ratio: float | None = None

    building_registry_status: str = "missing"
    building_age_years: int | None = None

    business_status_source_status: str = "missing"
    business_closed_flag: bool | None = None

    dart_status: str = "missing"
    dart_disclosure_flag: bool | None = None


@dataclass
class RiskEngineResult:
    risk_score: int
    risk_grade: str
    confidence: float
    data_completeness: float
    risk_factors: list[RiskFactorItem] = field(default_factory=list)
    positive_factors: list[RiskFactorItem] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    required_documents: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
    source_status: dict[str, str] = field(default_factory=dict)
    risk_reasons: list[str] = field(default_factory=list)
    resolvable_risks: list[str] = field(default_factory=list)
    unresolvable_risks: list[str] = field(default_factory=list)


def evaluate(inputs: RiskEngineInputs) -> RiskEngineResult:
    score = 0
    risk_factors: list[RiskFactorItem] = []
    positive_factors: list[RiskFactorItem] = []
    missing_fields: list[str] = []
    required_documents: list[str] = ["등기사항전부증명서", "국세 및 지방세 완납증명서"]
    recommended_actions: list[str] = []
    risk_reasons: list[str] = []
    resolvable_risks: list[str] = []
    unresolvable_risks: list[str] = []
    source_status: dict[str, str] = {
        "registry": inputs.registry_status,
        "official_price": inputs.official_price_status,
        "building_registry": inputs.building_registry_status,
        "business_status": inputs.business_status_source_status,
        "dart": inputs.dart_status,
    }

    forced_high = False

    # --- 등기부(근저당/권리부담/압류) : live일 때만 계산 ---
    if inputs.registry_status == "live":
        if inputs.has_seizure:
            score += 40
            forced_high = True
            risk_factors.append(
                RiskFactorItem(
                    code="SEIZURE_CONFIRMED",
                    title="압류·가압류 확인",
                    severity="high",
                    description="등기부 조회 결과 압류 또는 가압류가 등재되어 있습니다.",
                )
            )
            risk_reasons.append("압류·가압류 확인")
            unresolvable_risks.append("압류 상태에서는 계약 진행을 권장하지 않습니다.")
        elif inputs.has_seizure is False:
            positive_factors.append(
                RiskFactorItem(
                    code="NO_SEIZURE",
                    title="압류 없음",
                    severity="low",
                    description="등기부 조회 결과 압류·가압류가 확인되지 않았습니다.",
                )
            )

        if inputs.mortgage_ratio is not None:
            if inputs.mortgage_ratio > 0.6:
                score += 25
                risk_factors.append(
                    RiskFactorItem(
                        code="MORTGAGE_RATIO_HIGH",
                        title="근저당 비율 높음",
                        severity="high",
                        description=f"근저당 채권최고액 비율이 {inputs.mortgage_ratio:.0%}로 높습니다.",
                    )
                )
                risk_reasons.append("근저당설정 비율 높음")
                resolvable_risks.append("근저당 말소 또는 감액 후 재계약 여부 확인 필요")
            elif inputs.mortgage_ratio > 0.3:
                score += 10
                risk_factors.append(
                    RiskFactorItem(
                        code="MORTGAGE_RATIO_MEDIUM",
                        title="근저당 설정 확인",
                        severity="medium",
                        description=f"근저당 채권최고액 비율이 {inputs.mortgage_ratio:.0%}입니다.",
                    )
                )
                risk_reasons.append("근저당설정")
            else:
                positive_factors.append(
                    RiskFactorItem(
                        code="MORTGAGE_RATIO_LOW",
                        title="근저당 비율 낮음",
                        severity="low",
                        description="근저당 채권최고액 비율이 낮은 수준입니다.",
                    )
                )

        if inputs.rights_burden_ratio is not None and inputs.rights_burden_ratio > 0.8:
            score += 25
            risk_factors.append(
                RiskFactorItem(
                    code="RIGHTS_BURDEN_HIGH",
                    title="권리부담 비율 높음",
                    severity="high",
                    description=f"보증금과 선순위채권을 합한 권리부담 비율이 {inputs.rights_burden_ratio:.0%}입니다.",
                )
            )
            risk_reasons.append("권리부담 비율 높음")
    else:
        missing_fields.extend(["registry", "mortgage_ratio", "rights_burden_ratio", "has_seizure"])
        risk_factors.append(
            RiskFactorItem(
                code="REGISTRY_DATA_MISSING",
                title="등기부 데이터 미확보",
                severity="high",
                description="소유권 및 근저당 상태를 확인할 수 없습니다.",
            )
        )
        unresolvable_risks_note = "등기부 확인 전 계약금을 송금하지 마십시오."
        recommended_actions.append(unresolvable_risks_note)
        resolvable_risks.append("등기사항전부증명서 발급 후 재진단 필요")

    # --- 공시가격/전세가율 : live일 때만 계산 ---
    if inputs.official_price_status == "live" and inputs.official_price:
        if inputs.jeonse_ratio is not None:
            if inputs.jeonse_ratio > 0.8:
                score += 20
                risk_factors.append(
                    RiskFactorItem(
                        code="JEONSE_RATIO_HIGH",
                        title="전세가율 높음",
                        severity="high",
                        description=f"공시가격 대비 보증금 비율이 {inputs.jeonse_ratio:.0%}로 높습니다.",
                    )
                )
                risk_reasons.append("전세가율 높음")
            elif inputs.jeonse_ratio > 0.6:
                score += 10
                risk_factors.append(
                    RiskFactorItem(
                        code="JEONSE_RATIO_MEDIUM",
                        title="전세가율 다소 높음",
                        severity="medium",
                        description=f"공시가격 대비 보증금 비율이 {inputs.jeonse_ratio:.0%}입니다.",
                    )
                )
            else:
                positive_factors.append(
                    RiskFactorItem(
                        code="JEONSE_RATIO_LOW",
                        title="전세가율 안정적",
                        severity="low",
                        description="공시가격 대비 보증금 비율이 안정적인 수준입니다.",
                    )
                )
    else:
        missing_fields.append("official_price")
        missing_fields.append("jeonse_ratio")
        risk_factors.append(
            RiskFactorItem(
                code="OFFICIAL_PRICE_MISSING",
                title="공시가격 데이터 미확보",
                severity="medium",
                description="공시가격이 확정되지 않아 전세가율을 계산할 수 없습니다.",
            )
        )

    # --- 건축물대장 ---
    if inputs.building_registry_status == "live":
        if inputs.building_age_years is not None:
            if inputs.building_age_years > 30:
                score += 10
                risk_factors.append(
                    RiskFactorItem(
                        code="BUILDING_AGE_OLD",
                        title="건물 노후도 높음",
                        severity="medium",
                        description=f"사용승인 후 {inputs.building_age_years}년이 경과했습니다.",
                    )
                )
            else:
                positive_factors.append(
                    RiskFactorItem(
                        code="BUILDING_AGE_OK",
                        title="건물 연식 양호",
                        severity="low",
                        description=f"사용승인 후 {inputs.building_age_years}년으로 비교적 최근 건물입니다.",
                    )
                )
    else:
        missing_fields.append("building_registry")
        required_documents.append("건축물대장")

    # --- 임대인 사업자 상태 ---
    if inputs.business_status_source_status == "live" and inputs.business_closed_flag is not None:
        if inputs.business_closed_flag:
            score += 15
            risk_factors.append(
                RiskFactorItem(
                    code="LANDLORD_BUSINESS_CLOSED",
                    title="임대인 사업자 폐업 확인",
                    severity="high",
                    description="임대인(사업자)이 폐업 상태로 조회되었습니다.",
                )
            )
            risk_reasons.append("임대인 사업자 폐업")
            required_documents.append("임대인 사업자등록 상태 확인서")
        else:
            positive_factors.append(
                RiskFactorItem(
                    code="LANDLORD_BUSINESS_ACTIVE",
                    title="임대인 사업자 계속사업 확인",
                    severity="low",
                    description="임대인(사업자)이 계속사업자 상태로 조회되었습니다.",
                )
            )
    elif inputs.landlord_type != "INDIVIDUAL":
        missing_fields.append("business_status")

    # --- DART 공시 ---
    if inputs.dart_status == "live":
        if inputs.dart_disclosure_flag:
            positive_factors.append(
                RiskFactorItem(
                    code="DART_DISCLOSURE_FOUND",
                    title="법인 공시 확인",
                    severity="low",
                    description="OpenDART에서 임대인 법인의 공시 정보가 확인되었습니다.",
                )
            )
        elif inputs.landlord_type == "CORPORATION":
            score += 5
            risk_factors.append(
                RiskFactorItem(
                    code="DART_DISCLOSURE_NOT_FOUND",
                    title="법인 공시 미확인",
                    severity="low",
                    description="법인 임대인이지만 OpenDART 공시 정보를 확인하지 못했습니다.",
                )
            )
    elif inputs.landlord_type == "CORPORATION":
        missing_fields.append("dart_disclosure")

    # --- 전세보증보험(항상 권장) ---
    required_documents.append("전세보증보험 가입 확인서")

    # --- data_completeness / confidence 계산 ---
    resolved_weight = 0.0
    for category, weight in _COMPLETENESS_WEIGHTS.items():
        status = source_status.get(category, "missing")
        if status == "live":
            resolved_weight += weight
        elif status == "mock":
            resolved_weight += weight * 0.3  # mock은 "일부 참고 가능"이지만 신뢰도는 낮게 반영
    data_completeness = round(resolved_weight, 2)

    critical_weight = _COMPLETENESS_WEIGHTS["registry"] + _COMPLETENESS_WEIGHTS["official_price"]
    critical_resolved = 0.0
    for category in ("registry", "official_price"):
        status = source_status.get(category, "missing")
        if status == "live":
            critical_resolved += _COMPLETENESS_WEIGHTS[category]
        elif status == "mock":
            critical_resolved += _COMPLETENESS_WEIGHTS[category] * 0.3
    confidence = round(critical_resolved / critical_weight, 2) if critical_weight else 0.0

    # --- 등급 산정 ---
    if score >= 60:
        grade = RiskGrade.HIGH
    elif score >= 30:
        grade = RiskGrade.MEDIUM
    else:
        grade = RiskGrade.LOW

    # 데이터가 불충분하면 "낮은 위험"으로 단정하지 않는다(과제 지시사항 4절 핵심 원칙).
    if data_completeness < 0.4 and grade == RiskGrade.LOW:
        grade = RiskGrade.MEDIUM
        risk_factors.append(
            RiskFactorItem(
                code="INSUFFICIENT_DATA_FOR_LOW_GRADE",
                title="데이터 부족으로 최종 판단 보류",
                severity="medium",
                description="핵심 데이터(등기부/공시가격) 확보율이 낮아 '위험 낮음'으로 단정할 수 없습니다.",
            )
        )
    if forced_high:
        grade = RiskGrade.HIGH

    if grade in (RiskGrade.MEDIUM, RiskGrade.HIGH) and not recommended_actions:
        recommended_actions.append("계약 전 보완 서류 확인 및 아이엔 상담을 권장합니다.")
    if not risk_reasons and grade != RiskGrade.LOW:
        risk_reasons.append("핵심 데이터 미확보로 인한 보수적 판단")

    # dedupe preserving order
    def _dedupe(seq: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in seq:
            if item not in seen:
                seen.add(item)
                out.append(item)
        return out

    return RiskEngineResult(
        risk_score=min(score, 100),
        risk_grade=grade.value,
        confidence=confidence,
        data_completeness=data_completeness,
        risk_factors=risk_factors,
        positive_factors=positive_factors,
        missing_fields=_dedupe(missing_fields),
        required_documents=_dedupe(required_documents),
        recommended_actions=_dedupe(recommended_actions),
        source_status=source_status,
        risk_reasons=_dedupe(risk_reasons),
        resolvable_risks=_dedupe(resolvable_risks),
        unresolvable_risks=_dedupe(unresolvable_risks),
    )
