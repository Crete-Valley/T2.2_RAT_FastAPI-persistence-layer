## 1. What this project is

This repository is a **FastAPI backend** prototype of the Readiness Assessment Toolkit. It uses **SQLite + SQLAlchemy async ORM** for persistence and **Pydantic** for request/response validation.

- **static reference datasets**
  - climate vulnerability data
  - weather-variable reference data
  - barriers and disadvantages catalogs
  - incentive catalogs and barrier-to-incentive mappings
  - predefined KPI catalogs
- **user-scored assessments**, persisted in a database
  - barrier/disadvantage assessments
  - custom KPI definitions
  - KPI assessment runs with versioning and historical snapshots

The API supports two analytical modules:

1. **Barrier / disadvantage assessment**
   - the user scores barriers with **likelihood** and **impact**
   - the backend computes barrier-level scores, category-level risk metrics, and linked incentives

2. **KPI assessment**
   - the user selects predefined and/or custom KPIs for a project timeline
   - the backend stores a **versioned assessment snapshot**
   - it computes per-category KPI performance across multiple **(a, b)** parameter combinations using time- and data-quality-adjusted formulas


---

## 2. Structure

Relevant project files:

```text
RAT/
├── main.py
├── db.py
├── schemas.py
├── functions.py
├── kpi_functions.py
├── seed_data.py
├── test.db
└── data/
    ├── barriers_disadvantages/
    │   └── Barriers_Disadvantages.py
    ├── climate_vulnerability/
    │   ├── Climate_vulnerability.py
    │   └── Weather_variables.py
    ├── incentives/
    │   ├── Incentives.py
    │   └── Incentives_id.py
    └── kpis/
        ├── Economic_KPIs.py
        ├── Environmental_KPIs.py
        ├── Social_KPIs.py
        ├── Technological_KPIs.py
        └── Cobenefits_KPIs.py
```

### Module responsibilities

#### `main.py`
The API entry point. It:
- creates the FastAPI app
- initializes the database schema in the application lifespan
- defines all REST endpoints
- orchestrates validation, persistence, scoring, and response shaping

#### `db.py`
Defines:
- database URL
- async SQLAlchemy engine and session factory
- ORM models / tables
- `get_db()` dependency used by FastAPI endpoints

#### `schemas.py`
Defines all Pydantic request and response models. This is the contract layer that enforces:
- allowed categories
- valid input modes
- date consistency
- value ranges for likelihood, impact, and data quality

#### `functions.py`
Implements the **barriers/disadvantages domain logic**:
- catalog generation
- risk-level mapping
- barrier lookup helpers
- delete-and-replace persistence flow for barrier assessments
- category result aggregation
- incentive mapping and persistence

#### `kpi_functions.py`
Implements the **KPI domain logic**:
- static KPI catalog flattening
- merging predefined and custom KPI catalogs
- custom KPI code generation
- KPI assessment version generation
- timeline validation against the project window
- KPI scoring formulas
- category aggregation of KPI results

#### `seed_data.py`
Seeds a placeholder `RatAssessment` row with `id=1`, because the rest of the API assumes an existing `rat_assessment_id` and there is **no endpoint in this repository to create RAT assessments**.

#### `data/...`
Static knowledge base used by the API.

---

## 3. Static data used by the tool

The backend is partly database-driven and partly dictionary-driven.

### 3.1 Climate vulnerability data
From:
- `data/climate_vulnerability/Climate_vulnerability.py`
- `data/climate_vulnerability/Weather_variables.py`

These files expose:
- `Climate_vulnerability_dic`
- `Weather_variables_dic`

The API returns these dictionaries directly. They are reference datasets, not computed outputs.

### 3.2 Barrier catalog
From:
- `data/barriers_disadvantages/Barriers_Disadvantages.py`

This dictionary is the source of truth for valid barrier IDs and labels.

Structure:
- **4 barrier categories**
  - Resource Scarcity: 10 barriers
  - Public Resistance: 9 barriers
  - Short-Term Focus: 3 barriers
  - Regulatory Delay: 4 barriers

The code derives `VALID_BARRIER_IDS` directly from this dictionary.

### 3.3 Incentive catalog and barrier-to-incentive mapping
From:
- `data/incentives/Incentives.py`
- `data/incentives/Incentives_id.py`

Used as:
- full incentive metadata catalog: **35 incentives**
- barrier-to-incentive mapping rows: **26 mappings**

The logic maps a saved barrier's **barrier name** to one or more incentive IDs, then resolves those IDs against the main incentive catalog.

### 3.4 KPI catalog
From:
- `data/kpis/Economic_KPIs.py`
- `data/kpis/Environmental_KPIs.py`
- `data/kpis/Social_KPIs.py`
- `data/kpis/Technological_KPIs.py`
- `data/kpis/Cobenefits_KPIs.py`

Catalog size:
- Economic KPIs: 41
- Environmental KPIs: 6
- Social KPIs: 9
- Technological KPIs: 54
- Cobenefits KPIs: 9

Total predefined KPIs in the static catalog: **119**.

Each KPI entry is normalized into a common structure with fields such as:
- `kpi_code`
- `category_name`
- `subcategory_name`
- `name`
- `primary_uses`
- `units_of_measurement`
- `description`
- `roles`

---

## 4. Technology stack

The codebase uses:

- **FastAPI** for the web API
- **Pydantic** for schema validation
- **SQLAlchemy async ORM** for persistence
- **aiosqlite** as the SQLite async driver
- **SQLite** database file: `test.db`

Database URL in `db.py`:

```python
DATABASE_URL = "sqlite+aiosqlite:///./test.db"
```

The engine is created with:

```python
engine = create_async_engine(DATABASE_URL, echo=True)
```

`echo=True` (generated SQL is logged to the console in this implementation)

---

## 5. Application lifecycle and startup behavior

`main.py` defines a FastAPI lifespan function:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
```


---

## 6. Database schema

### 6.1 `rat_assessments`
Represents the parent assessment context.

Fields:
- `id` (PK)
- `initiative_id`

Important: this repo assumes `rat_assessment_id` already exists.

### 6.2 `barrier_entries`
Stores each barrier scored by the user for a given `rat_assessment_id`.

Fields:
- `id`
- `rat_assessment_id` (FK)
- `barrier_id`
- `barrier_category`
- `barrier_name`
- `likelihood`
- `impact`
- `score`
- timestamps

### 6.3 `barrier_category_results`
Stores aggregated risk results per barrier category.

Fields:
- `id`
- `rat_assessment_id` (FK)
- `category_name`
- `persona_impact`
- `persona_likelihood`
- `persona_risk_score`
- `risk_level`
- `risk_percentage`
- timestamps

### 6.4 `barrier_incentive_results`
Stores incentives recommended for the current barrier assessment.

Fields:
- `id`
- `rat_assessment_id` (FK)
- `incentive_id`
- `incentive_name`
- `incentive_type`
- `incentive_category`
- `explanation`
- `source`
- timestamps

### 6.5 `barrier_incentive_result_links`
Stores the many-to-many-style linkage between a saved incentive result row and the barriers it addresses.

Fields:
- `id`
- `barrier_incentive_result_id` (FK)
- `barrier_id`
- `barrier_category`
- `barrier_name`

### 6.6 `custom_kpi_definitions`
Stores user-defined KPIs under a RAT assessment.

Fields:
- `id`
- `rat_assessment_id` (FK)
- `custom_kpi_code`
- `category_name`
- `name`
- `primary_uses_json`
- `units_of_measurement`
- `description`
- `roles_json`
- `is_active`
- timestamps

Constraint:
- unique per RAT assessment on `(rat_assessment_id, custom_kpi_code)`

### 6.7 `kpi_assessments`
Stores a versioned KPI assessment run.

Fields:
- `id`
- `rat_assessment_id` (FK)
- `version`
- `project_name`
- `project_start_year`, `project_start_month`
- `project_end_year`, `project_end_month`
- `project_duration_months`
- `assessment_year`, `assessment_month`
- `assessment_month_index`
- `assessed_at`
- `created_at`

### 6.8 `kpi_assessment_entries`
Stores the KPI-level snapshot rows belonging to one KPI assessment.

Fields:
- `id`
- `kpi_assessment_id` (FK)
- snapshot identity fields:
  - `source_type`
  - `kpi_code`
  - `category_name`
  - `subcategory_name`
- snapshot metadata fields:
  - `kpi_name`
  - `primary_uses_json`
  - `units_of_measurement`
  - `description`
  - `roles_json`
- timeline / user input fields:
  - `kpi_start_year`, `kpi_start_month`
  - `kpi_end_year`, `kpi_end_month`
  - `kpi_start_month_index`, `kpi_end_month_index`
  - `data_quality`
  - `input_mode`
  - `progress_stage`
  - `current_value`
  - `target_value`
- `created_at`

A key design choice here is that assessment entries store a **snapshot** of KPI metadata. That means if the source catalog changes later, historical assessments still preserve what was used at the time of scoring.

---

## 7. API endpoints overview

**11 exposed endpoints**:

### Static data
1. `GET /climate-vulnerability`
2. `GET /weather-variables`

### Barrier workflow
3. `GET /rat-assessments/{rat_assessment_id}/barriers-disadvantages`
4. `POST /rat-assessments/{rat_assessment_id}/barriers-disadvantages/assess`

### KPI catalog and assessment workflow
5. `GET /rat-assessments/{rat_assessment_id}/kpi-assessments`
6. `POST /rat-assessments/{rat_assessment_id}/custom-kpis`
7. `PUT /rat-assessments/{rat_assessment_id}/custom-kpis/{custom_kpi_code}`
8. `DELETE /rat-assessments/{rat_assessment_id}/custom-kpis/{custom_kpi_code}`
9. `POST /rat-assessments/{rat_assessment_id}/kpi-assessments`
10. `GET /rat-assessments/{rat_assessment_id}/kpi-assessments/{assessment_id}`
11. `DELETE /rat-assessments/{rat_assessment_id}/kpi-assessments/{assessment_id}`

---

## 8. Endpoint-by-endpoint explanation

## 8.1 `GET /climate-vulnerability`

### Purpose
Returns the full climate vulnerability reference dictionary.

### Implementation
```python
@app.get("/climate-vulnerability")
def get_climate_vulnerability_data():
    return Climate_vulnerability_dic
```

### Behavior
- no database access
- no transformation
- returns the static data object as-is

### Use case
The frontend can use this endpoint to populate the climate vulnerability module's cards

---

## 8.2 `GET /weather-variables`

### Purpose
Returns the full weather variable reference dictionary.

### Implementation
```python
@app.get("/weather-variables")
def get_weather_variables_data():
    return Weather_variables_dic
```

### Behavior
- no database access
- returns static weather-variable data directly

### Use case
inside climate vulnerability module, present informative descriptions.

---

## 8.3 `GET /rat-assessments/{rat_assessment_id}/barriers-disadvantages`

### Purpose
Returns:
- the static barrier catalog
- any previously saved barrier (last) assessment for the specified `rat_assessment_id`

### Response model
`BarriersPageResponse`

### What it does internally
1. Builds the barrier catalog from the static dictionary using `build_barrier_catalog()`.
2. Loads from DB:
   - `BarrierEntry`
   - `BarrierCategoryResult`
   - `BarrierIncentiveResult`
3. If nothing is saved yet, returns:
   - `catalog`
   - `saved_assessment: null`
4. If an assessment exists, it also queries linked barriers for each saved incentive using `BarrierIncentiveResultLink`.
5. Returns the catalog plus a fully reconstructed saved state.

### This is effectively the **page bootstrap endpoint** for the barrier assessment screen. It gives the frontend both:

- all available options to display
- any previously persisted answers/results to prefill the UI

### Important note
The endpoint does **not** create an assessment. It only reads static data plus any saved state.

---

## 8.4 `POST /rat-assessments/{rat_assessment_id}/barriers-disadvantages/assess`

### Purpose
Saves a complete barrier assessment and computes all dependent results.

### Request model
`BarrierAssessmentRequest`

Payload shape:
```json
{
  "entries": [
    {
      "barrier_id": "...",
      "likelihood": 1,
      "impact": 1
    }
  ]
}
```

### Input validation
The endpoint validates:
- no duplicate `barrier_id` values in the submitted payload
- every `barrier_id` exists in `VALID_BARRIER_IDS`
- `likelihood` and `impact` are strict integers in `[1, 5]` via Pydantic

### Full processing workflow
1. **Validate barrier uniqueness**
2. **Validate barrier IDs**
3. **Delete any previous saved barrier state** for that RAT assessment
4. **Save new barrier entries**
5. **Compute category-level results**
6. **Save category-level results**
7. **Compute incentive recommendations and addressed-barrier links**
8. **Save incentive rows and link rows**
9. **Commit** transaction
10. Return computed result payload

### Replace-not-patch behavior
This endpoint is designed as a **full replacement write** for the barrier assessment. It deletes the previous state before saving the new one.

That means the frontend should send the **entire current barrier state**, not only deltas.

### Barrier-level formula
For each selected barrier:

```text
score = likelihood * impact
```

with both values restricted to integers from 1 to 5.

So barrier scores range from **1 to 25** for submitted barriers.

### Category-level formulas
For each barrier category, the code aggregates:

- `sum_numerator = Σ(score)`
- `sum_likelihood = Σ(likelihood)`
- `sum_impact = Σ(impact)`

Then computes:

```text
persona_impact = sum_numerator / sum_impact        if sum_impact > 0 else 0
persona_likelihood = sum_numerator / sum_likelihood if sum_likelihood > 0 else 0
persona_risk_score = persona_impact × persona_likelihood
```

Then:

```text
risk_percentage = (persona_risk_score / total_score) × 100
```

where:

```text
total_score = Σ(persona_risk_score across all categories)
```

### Risk-level thresholds
`determine_risk_level(score)` maps category risk score to labels:

- `0` → `None`
- `1 <= score < 5` → `Very Low`
- `< 10` → `Low`
- `< 15` → `Medium`
- `< 20` → `High`
- `<= 25` → `Very High`
- otherwise → `Invalid`


### Incentive mapping logic
For each saved barrier:
1. resolve the `barrier_name`
2. find the first row in `incentives_id` where `item["barrier"] == barrier_name`
3. get the list of mapped incentive IDs
4. resolve each incentive ID against `incentives_dic`
5. create a unique incentive result object
6. attach all barriers addressed by that incentive
7. deduplicate barriers by `barrier_name`

### Output
Returns:
- saved entries
- computed category results
- computed incentives

This response is suitable for directly updating the frontend after submission.

---

## 8.5 `GET /rat-assessments/{rat_assessment_id}/kpi-assessments`

### Purpose
Returns the KPI page bootstrap data:
- the merged KPI catalog (predefined + custom created)
- KPI assessment history
- the latest KPI assessment with computed results

### Response model
`KPIPageResponse`

### Internal workflow
1. Builds the KPI catalog using `build_kpi_catalog()`.
   - predefined KPI dictionaries are flattened
   - active custom KPIs for the assessment are loaded and merged in
2. Loads all `KPIAssessment` rows for the RAT assessment, sorted by descending version.
3. Builds `assessments_history`, including selected KPI counts.
4. If at least one KPI assessment exists:
   - load all `KPIAssessmentEntry` rows for the latest one
   - compute `results_by_ab` dynamically using `compute_assessment_results()`
5. Return the full page payload.

### This is the **main read endpoint for the KPI module**. It gives the frontend everything it needs to render:

- the KPI selection catalog
- previously defined custom KPIs
- historical assessments
- the latest computed assessment summary

### Catalog structure
Returned `catalog` is nested as:

```text
category_name -> subcategory_name -> [kpi items]
```

Predefined KPIs keep their domain subcategories, while custom KPIs are placed under:

```text
subcategory_name = "Custom"
```

---

## 8.6 `POST /rat-assessments/{rat_assessment_id}/custom-kpis`

### Purpose
Creates a new custom KPI under a given RAT assessment.

### Request model
`KPICustomDefinitionCreate`

Important constraints:
- `category_name` must be one of:
  - `Economic_KPIs`
  - `Environmental_KPIs`
  - `Social_KPIs`
  - `Technological_KPIs`
  - `Cobenefits_KPIs`
- `primary_uses` values must be from:
  - `Planning`
  - `Tracking`
  - `Performance`

### Internal workflow
1. Generate the next custom KPI code with `get_next_custom_kpi_code()`.
   - existing codes are scanned for `custom_KPI_{n}`
   - next number is `max + 1`
2. Insert a `CustomKPIDefinition` row.
3. Store list fields as JSON strings via `dumps_list()`.
4. Commit and return the created object.

### Output example semantics
A successful response returns fields like:
- `id`
- `custom_kpi_code`
- `category_name`
- `name`
- `primary_uses`
- `units_of_measurement`
- `description`
- `roles`
- `is_active`

### Design note
Custom KPIs are **scoped per RAT assessment**, not global.

---

## 8.7 `PUT /rat-assessments/{rat_assessment_id}/custom-kpis/{custom_kpi_code}`

### Purpose
Updates an existing custom KPI.

### Request model
`KPICustomDefinitionUpdate`

### Internal workflow
1. Query the custom KPI by:
   - `rat_assessment_id`
   - `custom_kpi_code`
2. If not found, return `404 Custom KPI not found`
3. Update only fields that are not `None`
4. Commit and return the updated definition



---

## 8.8 `DELETE /rat-assessments/{rat_assessment_id}/custom-kpis/{custom_kpi_code}`

### Purpose
Deletes a custom KPI.

### Internal workflow
1. Load the target row by assessment + code
2. Return 404 if not found
3. Delete the row
4. Commit
5. Return a success message

### Important implication
Deleting a custom KPI removes it from the live catalog, but old KPI assessments still retain historical snapshots in `kpi_assessment_entries`.

---

## 8.9 `POST /rat-assessments/{rat_assessment_id}/kpi-assessments`

### Purpose
Creates a new KPI assessment version and computes KPI results.

### Request model
`KPIAssessmentCreateRequest`

### Payload content
The payload includes:
- project metadata
- project start and end dates
- a list of KPI entries

Each KPI entry includes:
- `kpi_code`
- `source_type` (`predefined` or `custom`)
- `category_name`
- KPI timeline within the project
- `data_quality` from 1 to 5
- `input_mode`
  - `qualitative`
  - `numeric`
- either:
  - `progress_stage` for qualitative mode
  - `current_value` + `target_value` for numeric mode

### Pydantic validation rules
#### Project-level
`project_end` must be strictly later than `project_start`.

#### KPI-entry-level
`kpi_end_date` must be strictly later than `kpi_start_date`.

If `input_mode == "qualitative"`:
- `progress_stage` is required
- `current_value` and `target_value` must be empty

If `input_mode == "numeric"`:
- `current_value` and `target_value` are required
- `target_value > 0`
- `progress_stage` must be empty

### Internal workflow
1. Validate all entry timelines are within the project timeline using `validate_assessment_entries_against_project()`.
2. Build merged KPI catalog (predefined + active custom KPIs).
3. Determine next assessment version using `get_next_kpi_assessment_version()`.
4. Compute the current assessment month index relative to the project start.
5. Clamp the assessment month index into the valid project range.
6. Create a `KPIAssessment` row.
7. For each submitted KPI entry:
   - confirm the KPI exists in the merged catalog
   - confirm the submitted `source_type` matches the catalog definition
   - confirm the submitted `category_name` matches the catalog definition
   - serialize a snapshot of the KPI metadata
   - create a `KPIAssessmentEntry` row
8. Commit
9. Reload saved entries
10. Return the saved assessment with computed `results_by_ab`

### Versioning logic
Assessment versions are per `rat_assessment_id`:

```text
version = max(existing_versions_for_this_rat_assessment) + 1
```

So each new KPI assessment is a full new version rather than an overwrite.

### Project duration formula
The code uses inclusive month counting:

```text
project_duration_months = (end_year - start_year) * 12 + (end_month - start_month) + 1
```

### KPI month index formula
A KPI's timeline is converted to project-relative month indices:

```text
project_relative_month_index = (target_year - base_year) * 12 + (target_month - base_month) + 1
```

This is used for both KPI start and KPI end positions inside the project schedule.

### Assessment month index formula
The current UTC date at submission time is compared against the project start:

```text
raw_assessment_month_index =
    (now.year - project_start.year) * 12
    + (now.month - project_start.month)
    + 1
```

This raw index is then clamped:
- below 1 → 1
- above project duration → project duration
- otherwise unchanged

This means KPI scoring is always anchored to the **current real month** at assessment creation time, but restricted to the project window.

---

## 8.10 `GET /rat-assessments/{rat_assessment_id}/kpi-assessments/{assessment_id}`

### Purpose
Returns a single KPI assessment version in detail.

### Internal workflow
1. Load the specified `KPIAssessment` by both `assessment_id` and `rat_assessment_id`
2. If not found, return 404
3. Load all `KPIAssessmentEntry` rows for that assessment
4. Compute `results_by_ab`
5. Return a detailed assessment response

### Why this endpoint matters
Use it when the frontend needs to inspect an older KPI assessment version, not only the latest one.

---

## 8.11 `DELETE /rat-assessments/{rat_assessment_id}/kpi-assessments/{assessment_id}`

### Purpose
Deletes a KPI assessment version.

### Internal workflow
1. Load the assessment by assessment ID + RAT assessment ID
2. If not found, return 404
3. Delete the assessment row
4. Commit
5. Return a success message

Since `KPIAssessmentEntry` has a foreign key with `ondelete="CASCADE"`, dependent rows are intended to be removed with the assessment.

---

## 9. Barrier workflow 

The barrier workflow is structured like this:

### Step 1: Load the barrier page
Call:
- `GET /rat-assessments/{id}/barriers-disadvantages`

This gives:
- all available barriers grouped by category
- any previously saved entries, category scores, and incentive recommendations

### Step 2: User scores barriers
For each barrier the user provides:
- `likelihood` from 1 to 5
- `impact` from 1 to 5

### Step 3: Submit full assessment
Call:
- `POST /rat-assessments/{id}/barriers-disadvantages/assess`

### Step 4: Backend computes
- barrier score = likelihood × impact
- category risk metrics
- risk percentages
- qualitative risk levels
- mapped incentives
- barrier-to-incentive link rows

### Step 5: Results become queryable
Subsequent GET calls return the saved state.

### Architectural characteristic
This module behaves like a **derived-results persistence workflow**:
- inputs are persisted
- aggregates are computed server-side
- derived outputs are also persisted

That makes reads simpler and faster because the endpoint can return precomputed category and incentive results.

---

## 10. KPI workflow in business terms

The KPI workflow has three layers.

### Layer 1: KPI catalog
The system merges:
- predefined KPI catalog from static dictionaries
- active custom KPIs created by the user for a specific RAT assessment

### Layer 2: KPI definition management
Users can:
- create custom KPIs
- update them
- delete them

These custom KPIs live in the database but are folded into the same catalog structure as predefined KPIs.

### Layer 3: Versioned KPI assessments
A KPI assessment is a snapshot of:
- which KPIs were chosen
- which timeline each KPI has inside the project
- current progress data
- data quality
- category attribution
- metadata copied from the catalog at assessment time

Each new submission creates a **new version**.

### Typical KPI workflow
1. Call `GET /rat-assessments/{id}/kpi-assessments`
2. Display the catalog and history
3. Optionally create/update custom KPIs
4. Submit a new KPI assessment version
5. Read latest or specific assessment details
6. Compare results across `(a, b)` parameter combinations

---

## 11. KPI scoring logic in detail

## 11.1 Scoring dimensions
The score depends on:
- progress toward the KPI target or stage
- timing relative to where the project currently is
- data quality
- two parameters, `a` and `b` representing time sensitivity and data sensitivity

The code evaluates every KPI under **9 combinations**:

```text
AB_VALUES = [3, 4, 5]
AB_COMBINATIONS = [(a, b) for a in [3,4,5] for b in [3,4,5]]
```

So the backend computes results for:
- (3, 3)
- (3, 4)
- (3, 5)
- (4, 3)
- (4, 4)
- (4, 5)
- (5, 3)
- (5, 4)
- (5, 5)


---

## 11.2 Qualitative progress mapping
For qualitative KPIs, textual stages are mapped to distances:

```text
"Very early stage"     -> 0.1
"Early progress"       -> 0.3
"Midway"               -> 0.5
"Advanced"             -> 0.7
"Near/at completion"   -> 0.9
```

This is stored in `STAGE_TO_DISTANCE`.


---

## 11.3 Numeric KPI score formula
For numeric KPIs:

### Progress normalization
```text
if current_value <= target_value:
    progress = current_value / target_value
else:
    progress = target_value / current_value
```

This design penalizes overshooting the target as well as undershooting it. The best value is obtained when current and target are equal.

### Effective current month
```text
effective_current_month = min(current_month_index, end_month_index)
```

So once the KPI window has ended, elapsed time stops increasing.

### Elapsed fraction of KPI window
```text
elapsed_fraction =
    (effective_current_month - start_month_index + 1)
    / (end_month_index - start_month_index + 1)
```

This expresses how far along the KPI schedule the project currently is.

### Time adjustment
```text
if progress >= elapsed_fraction:
    time_adjusted_progress = progress
else:
    time_adjusted_progress = progress * exp(-(elapsed_fraction ** a))
```

Interpretation:
- if actual progress is at or ahead of expected time progress, no penalty is applied
- if actual progress lags behind schedule, an exponential penalty is applied
- `a` controls how sharply schedule lag is penalized

### Data-quality adjustment
```text
final_progress = time_adjusted_progress * (data_quality / 5) ** (1 / b)
```

Interpretation:
- `data_quality` is in `[1, 5]`
- quality `5` leaves the multiplier at `1`
- lower data quality reduces the score
- `b` controls the data-quality penalty

### Final numeric score
```text
numeric_score = round(final_progress, 2)
```

Only scored if:
```text
current_month_index >= start_month_index
```
Otherwise the score is `None`.

---

## 11.4 Qualitative KPI score formula
For qualitative KPIs, the formula mirrors the numeric one but starts from stage distance instead of numeric progress.

### Base distance
```text
distance = STAGE_TO_DISTANCE[progress_stage]
```

### Elapsed fraction
Same formula as numeric mode.

### Time adjustment
```text
if distance >= elapsed_fraction:
    time_adjusted_distance = distance
else:
    time_adjusted_distance = distance * exp(-(elapsed_fraction ** a))
```

### Data-quality adjustment
```text
final_score = time_adjusted_distance * (data_quality / 5) ** (1 / b)
```

### Final qualitative score
```text
qualitative_score = round(final_score, 2)
```

Again, scoring only happens when the current assessment month has reached the KPI start month.

---

## 11.5 Progress percentage shown in responses
The response exposes a `progress_percentage` field.

### Numeric mode
```text
progress_percentage = min(current_value / target_value, 1.0) * 100
```

This caps visible progress at 100%, even if the scoring formula internally penalizes overshoot by using `target/current`.

### Qualitative mode
```text
progress_percentage = distance * 100
```

So the qualitative stages map to:
- 10%
- 30%
- 50%
- 70%
- 90%

---

## 11.6 Category aggregation of KPI scores
Within each `(a, b)` combination, scores are grouped by `category_name`.

For each category:
1. collect all non-`None` KPI scores
2. average them
3. classify the average
4. convert it to a 1–5 scale

### Category average score
```text
avg_score = round(sum(scores) / len(scores), 2)
```

### KPI level thresholds
`determine_kpi_level(score)` maps category score to labels:
- `0 <= score < 0.2` → `Very Low`
- `< 0.4` → `Low`
- `< 0.6` → `Medium`
- `< 0.8` → `High`
- `<= 1` → `Very High`
- otherwise → `Invalid`

### Conversion to 1–5 scale
```text
score_1_to_5 = 1 + 4 * score
```

rounded to 2 decimals.

So:
- score `0.00` → `1.00`
- score `0.50` → `3.00`
- score `1.00` → `5.00`

If a category has no active scores yet, the response returns:
- `score = null`
- `level = "Not Available"`
- `score_1_to_5 = null`

---

## 12. Request and validation rules

## 12.1 Barrier validation
From `schemas.py`:
- `likelihood`: strict int, 1 to 5
- `impact`: strict int, 1 to 5

From `main.py`:
- duplicate barrier IDs are rejected
- invalid barrier IDs are rejected

## 12.2 Custom KPI validation
- custom KPI category must be one of the allowed KPI categories
- `name` must be non-empty
- primary uses are constrained literals

## 12.3 KPI assessment validation
- project end must be later than project start
- KPI end must be later than KPI start
- each KPI code must be unique within a submission
- KPI timeline must fall completely inside the project window
- input-mode-specific field rules are enforced
- submitted source type must match the catalog definition
- submitted category must match the catalog definition
- the KPI must exist in the merged catalog for the RAT assessment

These checks make the API resilient against stale or malformed frontend payloads.

---

## 13. Why snapshotting is important in KPI assessments

When a KPI assessment is created, the backend stores a copy of KPI metadata inside `KPIAssessmentEntry`, including:
- KPI code
- name
- category/subcategory
- primary uses
- units
- description
- roles

This provides:
- historical reproducibility
- independence from future catalog edits
- reliable reporting for old versions

Without snapshotting, historical assessments could silently change meaning if a KPI definition were edited later.

---

## 14. End-to-end workflow examples

## 14.1 Barrier workflow example

### Step A
Frontend loads page:
```http
GET /rat-assessments/1/barriers-disadvantages
```

### Step B
Frontend displays barrier catalog grouped by category.

### Step C
User scores selected barriers.

### Step D
Frontend submits full selection:
```http
POST /rat-assessments/1/barriers-disadvantages/assess
Content-Type: application/json
```

Example payload:
```json
{
  "entries": [
    {"barrier_id": "B1", "likelihood": 4, "impact": 5},
    {"barrier_id": "B2", "likelihood": 3, "impact": 2}
  ]
}
```

### Step E
Backend returns:
- barrier scores
- category risk scores and percentages
- mapped incentives

### Step F
Frontend can persist or display the result immediately and later reload it with the GET endpoint.

---

## 14.2 KPI workflow example

### Step A
Load catalog/history:
```http
GET /rat-assessments/1/kpi-assessments
```

### Step B
Optional: create a custom KPI:
```http
POST /rat-assessments/1/custom-kpis
```

### Step C
Submit KPI assessment with project timeline and KPI entries:
```http
POST /rat-assessments/1/kpi-assessments
```

### Step D
Backend:
- validates timelines
- snapshots KPI metadata
- creates a new assessment version
- computes category results for all 9 `(a, b)` combinations

### Step E
Frontend reads a specific historical version when needed:
```http
GET /rat-assessments/1/kpi-assessments/{assessment_id}
```

---



## 15. Notes

### 15.1 There is no endpoint for RAT assessment creation
The rest of the API assumes `rat_assessment_id` exists, but this repository does not create it through REST. `seed_data.py` works around this for development by inserting `id=1`.

### 15.2 Barrier writes are destructive replacement writes
`POST /barriers-disadvantages/assess` deletes the previous state before inserting the new one. This is correct for “save current full assessment” behavior, but not for incremental patching.

### 15.3 KPI assessments are append-only versioned writes
Each new KPI assessment creates a new `version`. This is good for auditability and historical comparison.

### 15.4 Some results are stored, some are computed on read
- barrier category results and incentives are persisted
- KPI `results_by_ab` are recomputed on demand from stored assessment entries

### 15.5 SQLAlchemy cascade assumptions
Several foreign keys use `ondelete="CASCADE"`. In SQLite, actual cascade behavior depends on foreign-key enforcement settings. If this app is moved to production, foreign-key behavior should be explicitly verified.


---
