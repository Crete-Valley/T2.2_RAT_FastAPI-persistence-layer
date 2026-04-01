import json
import math
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import CustomKPIDefinition, KPIAssessment, KPIAssessmentEntry

# static dics import
from data.kpis.Economic_KPIs import Economic_KPIs
from data.kpis.Environmental_KPIs import Environmental_KPIs
from data.kpis.Social_KPIs import Social_KPIs
from data.kpis.Technological_KPIs import Technological_KPIs
from data.kpis.Cobenefits_KPIs import Co_benefits_KPIs


KPI_CATEGORIES = {
    "Economic_KPIs": Economic_KPIs,
    "Environmental_KPIs": Environmental_KPIs,
    "Social_KPIs": Social_KPIs,
    "Technological_KPIs": Technological_KPIs,
    "Cobenefits_KPIs": Co_benefits_KPIs,
}

AB_VALUES = [3, 4, 5]
AB_COMBINATIONS = [(a, b) for a in AB_VALUES for b in AB_VALUES]

STAGE_TO_DISTANCE = {
    "Very early stage": 0.1,
    "Early progress": 0.3,
    "Midway": 0.5,
    "Advanced": 0.7,
    "Near/at completion": 0.9,
}


def dumps_list(value: list[str]) -> str:
    return json.dumps(value or [])


def loads_list(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return json.loads(value)


def determine_kpi_level(score: float) -> str:
    if 0 <= score < 0.2:
        return "Very Low"
    elif score < 0.4:
        return "Low"
    elif score < 0.6:
        return "Medium"
    elif score < 0.8:
        return "High"
    elif score <= 1:
        return "Very High"
    return "Invalid"


def convert_score_to_five_scale(score: Optional[float]) -> Optional[float]:
    if score is None:
        return None
    return round(1 + 4 * score, 2)


def calculate_numeric_kpi_score(
    current_value: float,
    target_value: float,
    start_month_index: int,
    end_month_index: int,
    current_month_index: int,
    data_quality: int,
    a: int,
    b: int,
) -> Optional[float]:
    if current_month_index < start_month_index:
        return None

    if current_value <= target_value:
        progress = current_value / target_value
    else:
        progress = target_value / current_value

    effective_current_month = min(current_month_index, end_month_index)

    elapsed_fraction = (
        (effective_current_month - start_month_index + 1)
        / (end_month_index - start_month_index + 1)
    )

    if progress >= elapsed_fraction:
        time_adjusted_progress = progress
    else:
        time_adjusted_progress = progress * math.exp(-(elapsed_fraction ** a))

    final_progress = time_adjusted_progress * (data_quality / 5) ** (1 / b)
    return round(final_progress, 2)


def calculate_qualitative_kpi_score(
    distance: float,
    start_month_index: int,
    end_month_index: int,
    current_month_index: int,
    data_quality: int,
    a: int,
    b: int,
) -> Optional[float]:
    if current_month_index < start_month_index:
        return None

    effective_current_month = min(current_month_index, end_month_index)

    elapsed_fraction = (
        (effective_current_month - start_month_index + 1)
        / (end_month_index - start_month_index + 1)
    )

    if distance >= elapsed_fraction:
        time_adjusted_distance = distance
    else:
        time_adjusted_distance = distance * math.exp(-(elapsed_fraction ** a))

    final_score = time_adjusted_distance * (data_quality / 5) ** (1 / b)
    return round(final_score, 2)








def flatten_predefined_catalog() -> dict[str, dict[str, Any]]:

    result: dict[str, dict[str, Any]] = {}

    for category_name, subcats in KPI_CATEGORIES.items():
        for subcategory_name, items in subcats.items():
            for kpi_code, kpi_info in items.items():
                primary_uses = kpi_info.get("Primary use", [])
                if isinstance(primary_uses, str):
                    primary_uses = [x.strip() for x in primary_uses.split(",") if x.strip()]

                result[kpi_code] = {
                    "source_type": "predefined",
                    "kpi_code": kpi_code,
                    "category_name": category_name,
                    "subcategory_name": subcategory_name,
                    "name": kpi_info.get("Name", ""),
                    "primary_uses": primary_uses,
                    "units_of_measurement": kpi_info.get("Units of measurement", ""),
                    "description": kpi_info.get("Description", ""),
                    "roles": kpi_info.get("Roles", []),
                }

    return result


async def build_kpi_catalog(session: AsyncSession, rat_assessment_id: int) -> tuple[
    dict[str, dict[str, list[dict[str, Any]]]],
    list[dict[str, Any]],
    dict[str, dict[str, Any]]
]:
    predefined_flat = flatten_predefined_catalog()

    catalog: dict[str, dict[str, list[dict[str, Any]]]] = {}

    # predefined
    for kpi in predefined_flat.values():
        category = kpi["category_name"]
        subcategory = kpi["subcategory_name"] or "General"
        catalog.setdefault(category, {}).setdefault(subcategory, []).append(kpi)

    # custom
    custom_rows = (
        await session.execute(
            select(CustomKPIDefinition).where(
                CustomKPIDefinition.rat_assessment_id == rat_assessment_id,
                CustomKPIDefinition.is_active == True,
            )
        )
    ).scalars().all()

    custom_defs: list[dict[str, Any]] = []
    custom_flat: dict[str, dict[str, Any]] = {}

    for row in custom_rows:
        item = {
            "id": row.id,
            "source_type": "custom",
            "kpi_code": row.custom_kpi_code,
            "category_name": row.category_name,
            "subcategory_name": "Custom",
            "name": row.name,
            "primary_uses": loads_list(row.primary_uses_json),
            "units_of_measurement": row.units_of_measurement,
            "description": row.description,
            "roles": loads_list(row.roles_json),
            "is_active": row.is_active,
        }
        custom_defs.append(item)
        custom_flat[row.custom_kpi_code] = item
        catalog.setdefault(row.category_name, {}).setdefault("Custom", []).append(item)

    merged_flat = {**predefined_flat, **custom_flat}
    return catalog, custom_defs, merged_flat


async def get_next_custom_kpi_code(session: AsyncSession, rat_assessment_id: int) -> str:
    rows = (
        await session.execute(
            select(CustomKPIDefinition.custom_kpi_code).where(
                CustomKPIDefinition.rat_assessment_id == rat_assessment_id
            )
        )
    ).scalars().all()

    max_num = 0
    for code in rows:
        if code.startswith("custom_KPI_"):
            try:
                num = int(code.split("_")[-1])
                max_num = max(max_num, num)
            except ValueError:
                pass

    return f"custom_KPI_{max_num + 1}"


async def get_next_kpi_assessment_version(session: AsyncSession, rat_assessment_id: int) -> int:
    current_max = (
        await session.execute(
            select(func.max(KPIAssessment.version)).where(
                KPIAssessment.rat_assessment_id == rat_assessment_id
            )
        )
    ).scalar_one_or_none()

    return 1 if current_max is None else current_max + 1


def validate_assessment_entries_against_project(project_start, project_end, entries):
    seen_codes = set()

    project_duration_months = month_diff_inclusive(
        project_start.year,
        project_start.month,
        project_end.year,
        project_end.month,
    )

    validated_entries = []

    for entry in entries:
        if entry.kpi_code in seen_codes:
            raise ValueError(f"Duplicate KPI code '{entry.kpi_code}' is not allowed")
        seen_codes.add(entry.kpi_code)

        kpi_start_month_index = project_relative_month_index(
            project_start.year,
            project_start.month,
            entry.kpi_start_date.year,
            entry.kpi_start_date.month,
        )

        kpi_end_month_index = project_relative_month_index(
            project_start.year,
            project_start.month,
            entry.kpi_end_date.year,
            entry.kpi_end_date.month,
        )

        if not (1 <= kpi_start_month_index <= kpi_end_month_index <= project_duration_months):
            raise ValueError(
                f"KPI '{entry.kpi_code}' has timeline "
                f"[{entry.kpi_start_date.year}-{entry.kpi_start_date.month}, "
                f"{entry.kpi_end_date.year}-{entry.kpi_end_date.month}] outside project timeline "
                f"[{project_start.year}-{project_start.month}, {project_end.year}-{project_end.month}]"
            )

        validated_entries.append({
            "entry": entry,
            "kpi_start_month_index": kpi_start_month_index,
            "kpi_end_month_index": kpi_end_month_index,
        })

    return validated_entries, project_duration_months


def serialize_entry_snapshot(defn: dict[str, Any]):
    return {
        "source_type": defn["source_type"],
        "kpi_code": defn["kpi_code"],
        "category_name": defn["category_name"],
        "subcategory_name": defn.get("subcategory_name"),
        "kpi_name": defn["name"],
        "primary_uses_json": dumps_list(defn.get("primary_uses", [])),
        "units_of_measurement": defn.get("units_of_measurement", ""),
        "description": defn.get("description", ""),
        "roles_json": dumps_list(defn.get("roles", [])),
    }


def compute_assessment_results(assessment: KPIAssessment, entries: list[KPIAssessmentEntry]) -> list[dict[str, Any]]:
    current_month_index = assessment.assessment_month_index
    results_by_ab: list[dict[str, Any]] = []

    for a, b in AB_COMBINATIONS:
        category_scores: dict[str, dict[str, Any]] = {}

        for entry in entries:
            progress_ratio = None
            score = None

            if entry.input_mode == "numeric":
                if current_month_index >= entry.kpi_start_month_index:
                    if entry.current_value is not None and entry.target_value:
                        if entry.current_value <= entry.target_value:
                            progress_ratio = round((entry.current_value / entry.target_value) * 100, 2)
                        else:
                            progress_ratio = round((entry.target_value / entry.current_value) * 100, 2)
                        score = calculate_numeric_kpi_score(
                            current_value=entry.current_value or 0,
                            target_value=entry.target_value or 1,
                            start_month_index=entry.kpi_start_month_index,
                            end_month_index=entry.kpi_end_month_index,
                            current_month_index=current_month_index,
                            data_quality=entry.data_quality,
                            a=a,
                            b=b,
                        )

            else:
                distance = STAGE_TO_DISTANCE.get(entry.progress_stage or "")
                if distance is None:
                    raise ValueError(f"Invalid progress_stage '{entry.progress_stage}'")

                if current_month_index >= entry.kpi_start_month_index:
                    progress_ratio = round(distance * 100, 2)
                    score = calculate_qualitative_kpi_score(
                        distance=distance,
                        start_month_index=entry.kpi_start_month_index,
                        end_month_index=entry.kpi_end_month_index,
                        current_month_index=current_month_index,
                        data_quality=entry.data_quality,
                        a=a,
                        b=b,
                    )

            category_scores.setdefault(entry.category_name, {"scores": [], "kpis": []})

            if score is not None:
                category_scores[entry.category_name]["scores"].append(score)

            category_scores[entry.category_name]["kpis"].append({
                "kpi_code": entry.kpi_code,
                "source_type": entry.source_type,
                "category_name": entry.category_name,
                "subcategory_name": entry.subcategory_name,
                "kpi_name": entry.kpi_name,
                "primary_uses": loads_list(entry.primary_uses_json),
                "units_of_measurement": entry.units_of_measurement,
                "description": entry.description,
                "roles": loads_list(entry.roles_json),
                "kpi_start_date": {
                    "year": entry.kpi_start_year,
                    "month": entry.kpi_start_month,
                },
                "kpi_end_date": {
                    "year": entry.kpi_end_year,
                    "month": entry.kpi_end_month,
                },
                "kpi_start_month_index": entry.kpi_start_month_index,
                "kpi_end_month_index": entry.kpi_end_month_index,
                "data_quality": entry.data_quality,
                "input_mode": entry.input_mode,
                "progress_stage": entry.progress_stage,
                "current_value": entry.current_value,
                "target_value": entry.target_value,
                "progress_percentage": progress_ratio,
                "score": score,
            })

        category_result_list = []
        for category_name, cat_data in category_scores.items():
            scores = cat_data["scores"]
            if scores:
                avg_score = round(sum(scores) / len(scores), 2)
                level = determine_kpi_level(avg_score)
                score_1_to_5 = convert_score_to_five_scale(avg_score)
            else:
                avg_score = None
                level = "Not Available"
                score_1_to_5 = None

            category_result_list.append({
                "category_name": category_name,
                "score": avg_score,
                "level": level,
                "score_1_to_5": score_1_to_5,
                "kpis": cat_data["kpis"],
            })

        results_by_ab.append({
            "a": a,
            "b": b,
            "category_scores": category_result_list,
        })

    return results_by_ab


def month_diff_inclusive(start_year: int, start_month: int, end_year: int, end_month: int) -> int:
    return (end_year - start_year) * 12 + (end_month - start_month) + 1

def project_relative_month_index(
    base_year: int,
    base_month: int,
    target_year: int,
    target_month: int,
) -> int:
    return (target_year - base_year) * 12 + (target_month - base_month) + 1

