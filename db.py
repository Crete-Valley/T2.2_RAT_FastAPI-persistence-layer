from collections.abc import AsyncGenerator
from datetime import datetime

from sqlalchemy import (
    String,
    Text,
    DateTime,
    ForeignKey,
    Integer,
    Float,
    Boolean,
    UniqueConstraint,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


DATABASE_URL = "sqlite+aiosqlite:///./test.db"

class Base(DeclarativeBase):
    pass

class RatAssessment(Base):
    __tablename__ = "rat_assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    initiative_id: Mapped[int] = mapped_column(Integer, index=True)

class BarrierEntry(Base):
    __tablename__ = "barrier_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    rat_assessment_id: Mapped[int] = mapped_column(
        ForeignKey("rat_assessments.id", ondelete="CASCADE"),
        index=True
    )

    barrier_id: Mapped[str] = mapped_column(String, index=True)
    barrier_category: Mapped[str] = mapped_column(String, index=True)
    barrier_name: Mapped[str] = mapped_column(String)

    likelihood: Mapped[int] = mapped_column(Integer)
    impact: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

class BarrierCategoryResult(Base):
    __tablename__ = "barrier_category_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    rat_assessment_id: Mapped[int] = mapped_column(
        ForeignKey("rat_assessments.id", ondelete="CASCADE"),
        index=True
    )

    category_name: Mapped[str] = mapped_column(String, index=True)

    persona_impact: Mapped[float] = mapped_column(Float)
    persona_likelihood: Mapped[float] = mapped_column(Float)
    persona_risk_score: Mapped[float] = mapped_column(Float)
    risk_level: Mapped[str] = mapped_column(String)
    risk_percentage: Mapped[float] = mapped_column(Float)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

class BarrierIncentiveResult(Base):
    __tablename__ = "barrier_incentive_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    rat_assessment_id: Mapped[int] = mapped_column(
        ForeignKey("rat_assessments.id", ondelete="CASCADE"),
        index=True
    )

    incentive_id: Mapped[int] = mapped_column(Integer, index=True)
    incentive_name: Mapped[str] = mapped_column(String)
    incentive_type: Mapped[str] = mapped_column(String)
    incentive_category: Mapped[str] = mapped_column(String)
    explanation: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

class BarrierIncentiveResultLink(Base):
    __tablename__ = "barrier_incentive_result_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    barrier_incentive_result_id: Mapped[int] = mapped_column(
        ForeignKey("barrier_incentive_results.id", ondelete="CASCADE"),
        index=True
    )

    barrier_id: Mapped[str] = mapped_column(String, index=True)
    barrier_category: Mapped[str] = mapped_column(String, index=True)
    barrier_name: Mapped[str] = mapped_column(String)


class CustomKPIDefinition(Base):
    __tablename__ = "custom_kpi_definitions"
    __table_args__ = (
        UniqueConstraint("rat_assessment_id", "custom_kpi_code", name="uq_custom_kpi_code_per_rat"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    rat_assessment_id: Mapped[int] = mapped_column(
        ForeignKey("rat_assessments.id", ondelete="CASCADE"),
        index=True
    )

    custom_kpi_code: Mapped[str] = mapped_column(String, index=True)  # e.g. custom_KPI_1
    category_name: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)
    primary_uses_json: Mapped[str] = mapped_column(Text, default="[]")
    units_of_measurement: Mapped[str] = mapped_column(String, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    roles_json: Mapped[str] = mapped_column(Text, default="[]")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class KPIAssessment(Base):
    __tablename__ = "kpi_assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    rat_assessment_id: Mapped[int] = mapped_column(
        ForeignKey("rat_assessments.id", ondelete="CASCADE"),
        index=True
    )

    version: Mapped[int] = mapped_column(Integer, index=True)
    project_name: Mapped[str] = mapped_column(String)
    project_start_year: Mapped[int] = mapped_column(Integer)
    project_start_month: Mapped[int] = mapped_column(Integer)
    project_end_year: Mapped[int] = mapped_column(Integer)
    project_end_month: Mapped[int] = mapped_column(Integer)

    project_duration_months: Mapped[int] = mapped_column(Integer)

    assessment_year: Mapped[int] = mapped_column(Integer)
    assessment_month: Mapped[int] = mapped_column(Integer)

    # clamped month index used for scoring
    assessment_month_index: Mapped[int] = mapped_column(Integer)

    # exact audit timestamp
    assessed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class KPIAssessmentEntry(Base):
    __tablename__ = "kpi_assessment_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    kpi_assessment_id: Mapped[int] = mapped_column(
        ForeignKey("kpi_assessments.id", ondelete="CASCADE"),
        index=True
    )

    # snapshot / identity
    source_type: Mapped[str] = mapped_column(String)  # "predefined" | "custom"
    kpi_code: Mapped[str] = mapped_column(String, index=True)
    category_name: Mapped[str] = mapped_column(String, index=True)
    subcategory_name: Mapped[str | None] = mapped_column(String, nullable=True)

    # snapshot metadata
    kpi_name: Mapped[str] = mapped_column(String)
    primary_uses_json: Mapped[str] = mapped_column(Text, default="[]")
    units_of_measurement: Mapped[str] = mapped_column(String, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    roles_json: Mapped[str] = mapped_column(Text, default="[]")

    # user input
    kpi_start_year: Mapped[int] = mapped_column(Integer)
    kpi_start_month: Mapped[int] = mapped_column(Integer)
    kpi_end_year: Mapped[int] = mapped_column(Integer)
    kpi_end_month: Mapped[int] = mapped_column(Integer)

    kpi_start_month_index: Mapped[int] = mapped_column(Integer)
    kpi_end_month_index: Mapped[int] = mapped_column(Integer)
    data_quality: Mapped[int] = mapped_column(Integer)

    input_mode: Mapped[str] = mapped_column(String)  # "qualitative" | "numeric"
    progress_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    current_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_value: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session