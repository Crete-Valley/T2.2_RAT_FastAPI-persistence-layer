from datetime import datetime
from typing import List, Optional, Literal, Union
from pydantic import BaseModel, Field, StrictInt, model_validator

AllowedPrimaryUse = Literal["Planning", "Tracking", "Performance"]
AllowedKPICategory = Literal[
    "Economic_KPIs",
    "Environmental_KPIs",
    "Social_KPIs",
    "Technological_KPIs",
    "Cobenefits_KPIs",
]

class YearMonthInput(BaseModel):
    year: int = Field(ge=1900, le=3000)
    month: int = Field(ge=1, le=12)

class BarrierEntryInput(BaseModel):
    barrier_id: str
    likelihood: StrictInt = Field(ge=1, le=5)
    impact: StrictInt = Field(ge=1, le=5)

class BarrierAssessmentRequest(BaseModel):
    entries: List[BarrierEntryInput]

class BarrierEntryResponse(BaseModel):
    barrier_id: str
    barrier_category: str
    barrier_name: str
    likelihood: int
    impact: int
    score: float


class BarrierCategoryResultResponse(BaseModel):
    category_name: str
    persona_impact: float
    persona_likelihood: float
    persona_risk_score: float
    risk_level: str
    risk_percentage: float


class IncentiveAddressedBarrierResponse(BaseModel):
    barrier_id: str
    barrier_category: str
    barrier_name: str


class IncentiveResultResponse(BaseModel):
    incentive_id: int
    incentive_name: str
    incentive_type: str
    incentive_category: str
    explanation: str
    source: str
    addresses_barriers: List[IncentiveAddressedBarrierResponse]


class SavedBarrierAssessmentResponse(BaseModel):
    entries: List[BarrierEntryResponse]
    category_results: List[BarrierCategoryResultResponse]
    incentives: List[IncentiveResultResponse]


class BarrierCatalogItem(BaseModel):
    barrier_id: str
    barrier_name: str


class BarriersPageResponse(BaseModel):
    catalog: dict[str, List[BarrierCatalogItem]]
    saved_assessment: Optional[SavedBarrierAssessmentResponse] = None


class KPICatalogItemResponse(BaseModel):
    kpi_code: str
    source_type: Literal["predefined", "custom"]
    category_name: str
    subcategory_name: Optional[str] = None
    name: str
    primary_uses: List[str]
    units_of_measurement: str
    description: str
    roles: List[str]


class KPICustomDefinitionCreate(BaseModel):
    category_name: AllowedKPICategory
    name: str = Field(min_length=1, max_length=255)
    primary_uses: List[AllowedPrimaryUse] = []
    units_of_measurement: Optional[str] = ""
    description: Optional[str] = ""
    roles: List[str] = []


class KPICustomDefinitionUpdate(BaseModel):
    category_name: Optional[AllowedKPICategory] = None
    name: Optional[str] = None
    primary_uses: Optional[List[AllowedPrimaryUse]] = None
    units_of_measurement: Optional[str] = None
    description: Optional[str] = None
    roles: Optional[List[str]] = None
    is_active: Optional[bool] = None


class KPICustomDefinitionResponse(BaseModel):
    id: int
    custom_kpi_code: str
    category_name: str
    name: str
    primary_uses: List[str]
    units_of_measurement: str
    description: str
    roles: List[str]
    is_active: bool


class KPIEntryInput(BaseModel):
    kpi_code: str
    source_type: Literal["predefined", "custom"]
    category_name: AllowedKPICategory

    kpi_start_date: YearMonthInput
    kpi_end_date: YearMonthInput
    data_quality: StrictInt = Field(ge=1, le=5)

    input_mode: Literal["qualitative", "numeric"]
    progress_stage: Optional[str] = None
    current_value: Optional[Union[int, float]] = Field(default=None, ge=0)
    target_value: Optional[Union[int, float]] = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_mode_fields(self):
        if (self.kpi_end_date.year, self.kpi_end_date.month) <= (self.kpi_start_date.year, self.kpi_start_date.month):
            raise ValueError("kpi_end_date must be bigger than kpi_start_date")

        if self.input_mode == "qualitative":
            if not self.progress_stage:
                raise ValueError("progress_stage is required when input_mode='qualitative'")
            if self.current_value is not None or self.target_value is not None:
                raise ValueError("current_value and target_value must be empty when input_mode='qualitative'")

        if self.input_mode == "numeric":
            if self.current_value is None or self.target_value is None:
                raise ValueError("current_value and target_value are required when input_mode='numeric'")
            if self.progress_stage is not None:
                raise ValueError("progress_stage must be empty when input_mode='numeric'")

        return self


class KPIAssessmentCreateRequest(BaseModel):
    project_name: str = Field(min_length=1)
    project_start: YearMonthInput
    project_end: YearMonthInput
    entries: List[KPIEntryInput]

    @model_validator(mode="after")
    def validate_project_dates(self):
        if (self.project_end.year, self.project_end.month) <= (self.project_start.year, self.project_start.month):
            raise ValueError("project_end must be bigger than project_start")
        return self


class KPIAssessmentHistoryItemResponse(BaseModel):
    id: int
    version: int
    project_name: str
    project_start_date: YearMonthInput
    project_end_date: YearMonthInput
    assessed_at: datetime
    selected_kpis_count: int


class KPIAssessmentEntryResponse(BaseModel):
    kpi_code: str
    source_type: str
    category_name: str
    subcategory_name: Optional[str]
    kpi_name: str
    primary_uses: List[str]
    units_of_measurement: str
    description: str
    roles: List[str]

    kpi_start_date: YearMonthInput
    kpi_end_date: YearMonthInput
    kpi_start_month_index: int
    kpi_end_month_index: int
    data_quality: int
    input_mode: str
    progress_stage: Optional[str]
    current_value: Optional[float]
    target_value: Optional[float]

    progress_percentage: Optional[float]
    score: Optional[float]


class KPICategoryResultResponse(BaseModel):
    category_name: str
    score: Optional[float]
    level: str
    score_1_to_5: Optional[float]
    kpis: List[KPIAssessmentEntryResponse]


class KPIABCombinationResponse(BaseModel):
    a: int
    b: int
    category_scores: List[KPICategoryResultResponse]


class KPIAssessmentDetailResponse(BaseModel):
    id: int
    rat_assessment_id: int
    version: int
    project_name: str
    project_start_date: YearMonthInput
    project_end_date: YearMonthInput
    assessed_at: datetime
    assessment_month_index: int
    results_by_ab: List[KPIABCombinationResponse]


class KPIPageResponse(BaseModel):
    catalog: dict[str, dict[str, List[KPICatalogItemResponse]]]
    custom_kpis: List[KPICustomDefinitionResponse]
    assessments_history: List[KPIAssessmentHistoryItemResponse]
    latest_assessment: Optional[KPIAssessmentDetailResponse] = None