from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import datetime

from db import (
    Base,
    engine,
    get_db,
    BarrierEntry,
    BarrierCategoryResult,
    BarrierIncentiveResult,
    BarrierIncentiveResultLink,
    CustomKPIDefinition,
    KPIAssessment,
    KPIAssessmentEntry,
)

from contextlib import asynccontextmanager


from data.climate_vulnerability.Climate_vulnerability import Climate_vulnerability_dic
from data.climate_vulnerability.Weather_variables import Weather_variables_dic
from data.barriers_disadvantages.Barriers_Disadvantages import Barriers_disadvantages_dic

from schemas import (
    BarrierAssessmentRequest,
    BarriersPageResponse,
    SavedBarrierAssessmentResponse,
    KPIPageResponse,
    KPICustomDefinitionCreate,
    KPICustomDefinitionUpdate,
    KPICustomDefinitionResponse,
    KPIAssessmentCreateRequest,
    KPIAssessmentDetailResponse,
)

from functions import (
    build_barrier_catalog,
    delete_previous_barrier_state,
    save_barrier_entries,
    compute_barrier_category_results,
    save_barrier_category_results,
    compute_incentive_results,
    save_incentive_results,
    VALID_BARRIER_IDS,
)

from kpi_functions import (
    build_kpi_catalog,
    dumps_list,
    loads_list,
    get_next_custom_kpi_code,
    get_next_kpi_assessment_version,
    validate_assessment_entries_against_project,
    serialize_entry_snapshot,
    compute_assessment_results,
)



@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(lifespan=lifespan)




@app.get("/climate-vulnerability")
def get_climate_vulnerability_data():
    return Climate_vulnerability_dic

@app.get("/weather-variables")
def get_weather_variables_data():
    return Weather_variables_dic


@app.get(
    "/rat-assessments/{rat_assessment_id}/barriers-disadvantages",
    response_model=BarriersPageResponse,
)
async def get_barriers_disadvantages(
    rat_assessment_id: int,
    session: AsyncSession = Depends(get_db),
):
    catalog = build_barrier_catalog(Barriers_disadvantages_dic)

    entries = (
        await session.execute(
            select(BarrierEntry).where(BarrierEntry.rat_assessment_id == rat_assessment_id)
        )
    ).scalars().all()

    category_results = (
        await session.execute(
            select(BarrierCategoryResult).where(
                BarrierCategoryResult.rat_assessment_id == rat_assessment_id
            )
        )
    ).scalars().all()

    incentive_rows = (
        await session.execute(
            select(BarrierIncentiveResult).where(
                BarrierIncentiveResult.rat_assessment_id == rat_assessment_id
            )
        )
    ).scalars().all()

    if not entries and not category_results and not incentive_rows:
        return {
            "catalog": catalog,
            "saved_assessment": None,
        }

    incentives_response = []
    for incentive in incentive_rows:
        links = (
            await session.execute(
                select(BarrierIncentiveResultLink).where(
                    BarrierIncentiveResultLink.barrier_incentive_result_id == incentive.id
                )
            )
        ).scalars().all()

        incentives_response.append({
            "incentive_id": incentive.incentive_id,
            "incentive_name": incentive.incentive_name,
            "incentive_type": incentive.incentive_type,
            "incentive_category": incentive.incentive_category,
            "explanation": incentive.explanation,
            "source": incentive.source,
            "addresses_barriers": [
                {
                    "barrier_id": link.barrier_id,
                    "barrier_category": link.barrier_category,
                    "barrier_name": link.barrier_name,
                }
                for link in links
            ]
        })

    return {
        "catalog": catalog,
        "saved_assessment": {
            "entries": [
                {
                    "barrier_id": e.barrier_id,
                    "barrier_category": e.barrier_category,
                    "barrier_name": e.barrier_name,
                    "likelihood": e.likelihood,
                    "impact": e.impact,
                    "score": e.score,
                }
                for e in entries
            ],
            "category_results": [
                {
                    "category_name": r.category_name,
                    "persona_impact": r.persona_impact,
                    "persona_likelihood": r.persona_likelihood,
                    "persona_risk_score": r.persona_risk_score,
                    "risk_level": r.risk_level,
                    "risk_percentage": r.risk_percentage,
                }
                for r in category_results
            ],
            "incentives": incentives_response,
        },
    }


@app.post(
    "/rat-assessments/{rat_assessment_id}/barriers-disadvantages/assess",
    response_model=SavedBarrierAssessmentResponse,
)
async def assess_barriers_disadvantages(
    rat_assessment_id: int,
    payload: BarrierAssessmentRequest,
    session: AsyncSession = Depends(get_db),
):
    # validate no duplicate barrier codes
    barrier_ids = [entry.barrier_id for entry in payload.entries]
    if len(barrier_ids) != len(set(barrier_ids)):
        raise HTTPException(status_code=400, detail="Duplicate barrier ids are not allowed")

    for entry in payload.entries:
        if entry.barrier_id not in VALID_BARRIER_IDS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid barrier id '{entry.barrier_id}'"
            )

    # delete previous saved state
    await delete_previous_barrier_state(session, rat_assessment_id)

    # create and save new entries
    saved_entries = await save_barrier_entries(session, rat_assessment_id, payload.entries)

    # compute category results
    computed_results = compute_barrier_category_results(saved_entries)

    # save category results
    await save_barrier_category_results(session, rat_assessment_id, computed_results)

    # compute unique incentives with addressed barriers
    computed_incentives = compute_incentive_results(saved_entries)

    # save incentives + links
    await save_incentive_results(session, rat_assessment_id, computed_incentives)

    await session.commit()

    return {
        "entries": saved_entries,
        "category_results": computed_results,
        "incentives": computed_incentives,
    }


@app.get(
    "/rat-assessments/{rat_assessment_id}/kpi-assessments",
    response_model=KPIPageResponse,
)
async def get_kpis(
    rat_assessment_id: int,
    session: AsyncSession = Depends(get_db),
):
    catalog, custom_defs, merged_flat = await build_kpi_catalog(session, rat_assessment_id)

    assessment_rows = (
        await session.execute(
            select(KPIAssessment)
            .where(KPIAssessment.rat_assessment_id == rat_assessment_id)
            .order_by(KPIAssessment.version.desc())
        )
    ).scalars().all()

    history = []
    latest_assessment_response = None

    for assessment in assessment_rows:
        selected_kpis_count = (
            await session.execute(
                select(func.count(KPIAssessmentEntry.id)).where(
                    KPIAssessmentEntry.kpi_assessment_id == assessment.id
                )
            )
        ).scalar_one()

        history.append({
            "id": assessment.id,
            "version": assessment.version,
            "project_name": assessment.project_name,
            "project_start_date": {
                "year": assessment.project_start_year,
                "month": assessment.project_start_month,
            },
            "project_end_date": {
                "year": assessment.project_end_year,
                "month": assessment.project_end_month,
            },
            "assessed_at": assessment.assessed_at,
            "selected_kpis_count": selected_kpis_count,
        })

    if assessment_rows:
        latest = assessment_rows[0]
        latest_entries = (
            await session.execute(
                select(KPIAssessmentEntry).where(
                    KPIAssessmentEntry.kpi_assessment_id == latest.id
                )
            )
        ).scalars().all()

        latest_assessment_response = {
            "id": latest.id,
            "rat_assessment_id": latest.rat_assessment_id,
            "version": latest.version,
            "project_name": latest.project_name,
            "project_start_date": {
                "year": latest.project_start_year,
                "month": latest.project_start_month,
            },
            "project_end_date": {
                "year": latest.project_end_year,
                "month": latest.project_end_month,
            },
            "assessed_at": latest.assessed_at,
            "assessment_month_index": latest.assessment_month_index,
            "results_by_ab": compute_assessment_results(latest, latest_entries),
        }

    return {
        "catalog": catalog,
        "custom_kpis": [
            {
                "id": item["id"],
                "custom_kpi_code": item["kpi_code"],
                "category_name": item["category_name"],
                "name": item["name"],
                "primary_uses": item["primary_uses"],
                "units_of_measurement": item["units_of_measurement"],
                "description": item["description"],
                "roles": item["roles"],
                "is_active": item["is_active"],
            }
            for item in custom_defs
        ],
        "assessments_history": history,
        "latest_assessment": latest_assessment_response,
    }


@app.post(
    "/rat-assessments/{rat_assessment_id}/custom-kpis",
    response_model=KPICustomDefinitionResponse,
)
async def create_custom_kpi(
    rat_assessment_id: int,
    payload: KPICustomDefinitionCreate,
    session: AsyncSession = Depends(get_db),
):
    code = await get_next_custom_kpi_code(session, rat_assessment_id)

    row = CustomKPIDefinition(
        rat_assessment_id=rat_assessment_id,
        custom_kpi_code=code,
        category_name=payload.category_name,
        name=payload.name,
        primary_uses_json=dumps_list(payload.primary_uses),
        units_of_measurement=payload.units_of_measurement or "",
        description=payload.description or "",
        roles_json=dumps_list(payload.roles),
        is_active=True,
    )

    session.add(row)
    await session.commit()
    await session.refresh(row)

    return {
        "id": row.id,
        "custom_kpi_code": row.custom_kpi_code,
        "category_name": row.category_name,
        "name": row.name,
        "primary_uses": loads_list(row.primary_uses_json),
        "units_of_measurement": row.units_of_measurement,
        "description": row.description,
        "roles": loads_list(row.roles_json),
        "is_active": row.is_active,
    }


@app.put(
    "/rat-assessments/{rat_assessment_id}/custom-kpis/{custom_kpi_code}",
    response_model=KPICustomDefinitionResponse,
)
async def update_custom_kpi(
    rat_assessment_id: int,
    custom_kpi_code: str,
    payload: KPICustomDefinitionUpdate,
    session: AsyncSession = Depends(get_db),
):
    row = (
        await session.execute(
            select(CustomKPIDefinition).where(
                CustomKPIDefinition.rat_assessment_id == rat_assessment_id,
                CustomKPIDefinition.custom_kpi_code == custom_kpi_code,
            )
        )
    ).scalar_one_or_none()

    if not row:
        raise HTTPException(status_code=404, detail="Custom KPI not found")

    if payload.category_name is not None:
        row.category_name = payload.category_name
    if payload.name is not None:
        row.name = payload.name
    if payload.primary_uses is not None:
        row.primary_uses_json = dumps_list(payload.primary_uses)
    if payload.units_of_measurement is not None:
        row.units_of_measurement = payload.units_of_measurement
    if payload.description is not None:
        row.description = payload.description
    if payload.roles is not None:
        row.roles_json = dumps_list(payload.roles)
    if payload.is_active is not None:
        row.is_active = payload.is_active

    await session.commit()
    await session.refresh(row)

    return {
        "id": row.id,
        "custom_kpi_code": row.custom_kpi_code,
        "category_name": row.category_name,
        "name": row.name,
        "primary_uses": loads_list(row.primary_uses_json),
        "units_of_measurement": row.units_of_measurement,
        "description": row.description,
        "roles": loads_list(row.roles_json),
        "is_active": row.is_active,
    }


@app.delete("/rat-assessments/{rat_assessment_id}/custom-kpis/{custom_kpi_code}")
async def delete_custom_kpi(
    rat_assessment_id: int,
    custom_kpi_code: str,
    session: AsyncSession = Depends(get_db),
):
    row = (
        await session.execute(
            select(CustomKPIDefinition).where(
                CustomKPIDefinition.rat_assessment_id == rat_assessment_id,
                CustomKPIDefinition.custom_kpi_code == custom_kpi_code,
            )
        )
    ).scalar_one_or_none()

    if not row:
        raise HTTPException(status_code=404, detail="Custom KPI not found")

    await session.delete(row)
    await session.commit()

    return {"message": f"Custom KPI '{custom_kpi_code}' deleted successfully."}


@app.post(
    "/rat-assessments/{rat_assessment_id}/kpi-assessments",
    response_model=KPIAssessmentDetailResponse,
)
async def create_kpi_assessment(
    rat_assessment_id: int,
    payload: KPIAssessmentCreateRequest,
    session: AsyncSession = Depends(get_db),
):
    try:
        validated_entries, project_duration_months = validate_assessment_entries_against_project(
            payload.project_start,
            payload.project_end,
            payload.entries,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    _, _, merged_flat = await build_kpi_catalog(session, rat_assessment_id)

    version = await get_next_kpi_assessment_version(session, rat_assessment_id)

    now = datetime.utcnow()

    raw_assessment_month_index = (
        (now.year - payload.project_start.year) * 12
        + (now.month - payload.project_start.month)
        + 1
    )

    if raw_assessment_month_index < 1:
        assessment_month_index = 1
    elif raw_assessment_month_index > project_duration_months:
        assessment_month_index = project_duration_months
    else:
        assessment_month_index = raw_assessment_month_index

    assessment = KPIAssessment(
        rat_assessment_id=rat_assessment_id,
        version=version,
        project_name=payload.project_name,
        project_start_year=payload.project_start.year,
        project_start_month=payload.project_start.month,
        project_end_year=payload.project_end.year,
        project_end_month=payload.project_end.month,
        project_duration_months=project_duration_months,
        assessment_year=now.year,
        assessment_month=now.month,
        assessment_month_index=assessment_month_index,
        assessed_at=now,
    )
    session.add(assessment)
    await session.flush()

    for item in validated_entries:
        entry = item["entry"]
        kpi_start_month_index = item["kpi_start_month_index"]
        kpi_end_month_index = item["kpi_end_month_index"]

        definition = merged_flat.get(entry.kpi_code)
        if not definition:
            raise HTTPException(
                status_code=400,
                detail=f"KPI '{entry.kpi_code}' was not found for this rat_assessment_id"
            )

        if definition["source_type"] != entry.source_type:
            raise HTTPException(
                status_code=400,
                detail=f"KPI '{entry.kpi_code}' has source_type '{definition['source_type']}', not '{entry.source_type}'"
            )

        if definition["category_name"] != entry.category_name:
            raise HTTPException(
                status_code=400,
                detail=f"KPI '{entry.kpi_code}' belongs to category '{definition['category_name']}', not '{entry.category_name}'"
            )

        snapshot = serialize_entry_snapshot(definition)

        row = KPIAssessmentEntry(
            kpi_assessment_id=assessment.id,
            source_type=snapshot["source_type"],
            kpi_code=snapshot["kpi_code"],
            category_name=snapshot["category_name"],
            subcategory_name=snapshot["subcategory_name"],
            kpi_name=snapshot["kpi_name"],
            primary_uses_json=snapshot["primary_uses_json"],
            units_of_measurement=snapshot["units_of_measurement"],
            description=snapshot["description"],
            roles_json=snapshot["roles_json"],

            kpi_start_year=entry.kpi_start_date.year,
            kpi_start_month=entry.kpi_start_date.month,
            kpi_end_year=entry.kpi_end_date.year,
            kpi_end_month=entry.kpi_end_date.month,
            kpi_start_month_index=kpi_start_month_index,
            kpi_end_month_index=kpi_end_month_index,
            data_quality=entry.data_quality,

            input_mode=entry.input_mode,
            progress_stage=entry.progress_stage,
            current_value=entry.current_value,
            target_value=entry.target_value,
        )

        session.add(row)

    await session.commit()
    await session.refresh(assessment)

    saved_entries = (
        await session.execute(
            select(KPIAssessmentEntry).where(
                KPIAssessmentEntry.kpi_assessment_id == assessment.id
            )
        )
    ).scalars().all()

    return {
        "id": assessment.id,
        "rat_assessment_id": assessment.rat_assessment_id,
        "version": assessment.version,
        "project_name": assessment.project_name,
        "project_start_date": {
            "year": assessment.project_start_year,
            "month": assessment.project_start_month,
        },
        "project_end_date": {
            "year": assessment.project_end_year,
            "month": assessment.project_end_month,
        },
        "assessed_at": assessment.assessed_at,
        "assessment_month_index": assessment.assessment_month_index,
        "results_by_ab": compute_assessment_results(assessment, saved_entries),
    }



@app.get(
    "/rat-assessments/{rat_assessment_id}/kpi-assessments/{assessment_id}",
    response_model=KPIAssessmentDetailResponse,
)
async def get_kpi_assessment_detail(
    rat_assessment_id: int,
    assessment_id: int,
    session: AsyncSession = Depends(get_db),
):
    assessment = (
        await session.execute(
            select(KPIAssessment).where(
                KPIAssessment.id == assessment_id,
                KPIAssessment.rat_assessment_id == rat_assessment_id,
            )
        )
    ).scalar_one_or_none()

    if not assessment:
        raise HTTPException(status_code=404, detail="KPI assessment not found")

    entries = (
        await session.execute(
            select(KPIAssessmentEntry).where(
                KPIAssessmentEntry.kpi_assessment_id == assessment.id
            )
        )
    ).scalars().all()

    return {
        "id": assessment.id,
        "rat_assessment_id": assessment.rat_assessment_id,
        "version": assessment.version,
        "project_name": assessment.project_name,
        "project_start_date": {
            "year": assessment.project_start_year,
            "month": assessment.project_start_month,
        },
        "project_end_date": {
            "year": assessment.project_end_year,
            "month": assessment.project_end_month,
        },
        "assessed_at": assessment.assessed_at,
        "assessment_month_index": assessment.assessment_month_index,
        "results_by_ab": compute_assessment_results(assessment, entries),
    }



@app.delete("/rat-assessments/{rat_assessment_id}/kpi-assessments/{assessment_id}")
async def delete_kpi_assessment(
    rat_assessment_id: int,
    assessment_id: int,
    session: AsyncSession = Depends(get_db),
):
    assessment = (
        await session.execute(
            select(KPIAssessment).where(
                KPIAssessment.id == assessment_id,
                KPIAssessment.rat_assessment_id == rat_assessment_id,
            )
        )
    ).scalar_one_or_none()

    if not assessment:
        raise HTTPException(status_code=404, detail="KPI assessment not found")

    await session.delete(assessment)
    await session.commit()

    return {"message": f"KPI assessment '{assessment_id}' deleted successfully."}