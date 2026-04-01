from sqlalchemy import delete

from db import (
    BarrierEntry,
    BarrierCategoryResult,
    BarrierIncentiveResult,
    BarrierIncentiveResultLink,
)
from data.barriers_disadvantages.Barriers_Disadvantages import Barriers_disadvantages_dic
from data.incentives.Incentives import incentives_dic
from data.incentives.Incentives_id import incentives_id

VALID_BARRIER_IDS = {
    barrier_id
    for category in Barriers_disadvantages_dic.values()
    for barrier_id in category.keys()
}

def build_barrier_catalog(barriers_disadvantages: dict) -> dict[str, list[dict]]:
    catalog = {}
    for category, barriers in barriers_disadvantages.items():
        catalog[category] = [
            {"barrier_id": barrier_id, "barrier_name": barrier_name}
            for barrier_id, barrier_name in barriers.items()
        ]
    return catalog


def determine_risk_level(score: float) -> str:
    if score == 0:
        return "None"
    elif 1 <= score < 5:
        return "Very Low"
    elif score < 10:
        return "Low"
    elif score < 15:
        return "Medium"
    elif score < 20:
        return "High"
    elif score <= 25:
        return "Very High"
    return "Invalid"


def get_barrier_category_and_name(barrier_id: str) -> tuple[str, str]:
    for category, barriers in Barriers_disadvantages_dic.items():
        if barrier_id in barriers:
            return category, barriers[barrier_id]
    raise ValueError(f"Barrier id '{barrier_id}' not found")


async def delete_previous_barrier_state(session, rat_assessment_id: int) -> None:
    await session.execute(
        delete(BarrierEntry).where(BarrierEntry.rat_assessment_id == rat_assessment_id)
    )
    await session.execute(
        delete(BarrierCategoryResult).where(
            BarrierCategoryResult.rat_assessment_id == rat_assessment_id
        )
    )
    await session.execute(
        delete(BarrierIncentiveResult).where(
            BarrierIncentiveResult.rat_assessment_id == rat_assessment_id
        )
    )



async def save_barrier_entries(session, rat_assessment_id: int, entries_input: list):
    saved_entries = []

    for entry in entries_input:
        category, barrier_name = get_barrier_category_and_name(entry.barrier_id)
        score = float(entry.likelihood * entry.impact)

        db_entry = BarrierEntry(
            rat_assessment_id=rat_assessment_id,
            barrier_id=entry.barrier_id,
            barrier_category=category,
            barrier_name=barrier_name,
            likelihood=entry.likelihood,
            impact=entry.impact,
            score=score,
        )
        session.add(db_entry)

        saved_entries.append({
            "barrier_id": entry.barrier_id,
            "barrier_category": category,
            "barrier_name": barrier_name,
            "likelihood": entry.likelihood,
            "impact": entry.impact,
            "score": score,
        })

    await session.flush()
    return saved_entries


def compute_barrier_category_results(saved_entries: list[dict]) -> list[dict]:
    category_data = {
        category: {
            "sum_numerator": 0.0,
            "sum_likelihood": 0.0,
            "sum_impact": 0.0,
        }
        for category in Barriers_disadvantages_dic.keys()
    }

    for entry in saved_entries:
        category = entry["barrier_category"]
        likelihood = entry["likelihood"]
        impact = entry["impact"]
        score = entry["score"]

        category_data[category]["sum_numerator"] += score
        category_data[category]["sum_likelihood"] += likelihood
        category_data[category]["sum_impact"] += impact

    results = []
    total_score = 0.0

    for category, values in category_data.items():
        numerator = values["sum_numerator"]
        sum_likelihood = values["sum_likelihood"]
        sum_impact = values["sum_impact"]

        persona_impact = numerator / sum_impact if sum_impact else 0.0
        persona_likelihood = numerator / sum_likelihood if sum_likelihood else 0.0
        persona_risk_score = persona_impact * persona_likelihood

        result = {
            "category_name": category,
            "persona_impact": round(persona_impact, 2),
            "persona_likelihood": round(persona_likelihood, 2),
            "persona_risk_score": round(persona_risk_score, 2),
            "risk_level": determine_risk_level(persona_risk_score),
            "risk_percentage": 0.0,
        }

        total_score += persona_risk_score
        results.append(result)

    for result in results:
        if total_score == 0:
            result["risk_percentage"] = 0.0
        else:
            result["risk_percentage"] = round(
                (result["persona_risk_score"] / total_score) * 100, 2
            )

    return results


async def save_barrier_category_results(session, rat_assessment_id: int, computed_results: list[dict]) -> None:
    for result in computed_results:
        db_result = BarrierCategoryResult(
            rat_assessment_id=rat_assessment_id,
            category_name=result["category_name"],
            persona_impact=result["persona_impact"],
            persona_likelihood=result["persona_likelihood"],
            persona_risk_score=result["persona_risk_score"],
            risk_level=result["risk_level"],
            risk_percentage=result["risk_percentage"],
        )
        session.add(db_result)

    await session.flush()


def compute_incentive_results(saved_entries: list[dict]) -> list[dict]:
    incentive_lookup = {item["id"]: item for item in incentives_dic}

    unique_incentives = {}

    for entry in saved_entries:
        barrier_name = entry["barrier_name"]

        mapping_item = next(
            (item for item in incentives_id if item["barrier"] == barrier_name),
            None
        )

        if not mapping_item:
            continue

        matched_incentive_ids = mapping_item.get("incentives", [])

        for incentive_id in matched_incentive_ids:
            incentive_obj = incentive_lookup.get(incentive_id)
            if not incentive_obj:
                continue

            if incentive_id not in unique_incentives:
                unique_incentives[incentive_id] = {
                    "incentive_id": incentive_obj["id"],
                    "incentive_name": incentive_obj["incentive"],
                    "incentive_type": incentive_obj["type"],
                    "incentive_category": incentive_obj["category"],
                    "explanation": incentive_obj["explanation"],
                    "source": incentive_obj["source"],
                    "addresses_barriers": [],
                }

            unique_incentives[incentive_id]["addresses_barriers"].append({
                "barrier_id": entry["barrier_id"],
                "barrier_category": entry["barrier_category"],
                "barrier_name": entry["barrier_name"],
            })

    final_results = []
    for incentive in unique_incentives.values():
        seen = set()
        unique_barriers = []

        for barrier in incentive["addresses_barriers"]:
            key = barrier["barrier_name"]
            if key not in seen:
                seen.add(key)
                unique_barriers.append(barrier)

        incentive["addresses_barriers"] = unique_barriers
        final_results.append(incentive)

    return final_results


async def save_incentive_results(session, rat_assessment_id: int, computed_incentives: list[dict]) -> None:
    for incentive in computed_incentives:
        db_incentive = BarrierIncentiveResult(
            rat_assessment_id=rat_assessment_id,
            incentive_id=incentive["incentive_id"],
            incentive_name=incentive["incentive_name"],
            incentive_type=incentive["incentive_type"],
            incentive_category=incentive["incentive_category"],
            explanation=incentive["explanation"],
            source=incentive["source"],
        )
        session.add(db_incentive)
        await session.flush()

        for barrier in incentive["addresses_barriers"]:
            link = BarrierIncentiveResultLink(
                barrier_incentive_result_id=db_incentive.id,
                barrier_id=barrier["barrier_id"],
                barrier_category=barrier["barrier_category"],
                barrier_name=barrier["barrier_name"],
            )
            session.add(link)

    await session.flush()


