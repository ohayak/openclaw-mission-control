# === PACT Pipeline & Health Visualization (pact_visualization) v1 ===
# Components and pages for PACT-specific views. Pipeline visualization (embedded in project detail for PACT projects): horizontal stepper showing 8 phases (Interview→Shape→Decompose→Contract→Test→Implement→Integrate→Polish) with current phase highlighted, derived from PACT directory state. Collapsible component tree (max 3 levels) showing per-component contract status and test pass/fail. PACT Health dashboard page: computes and displays output/planning ratio, rejection rate, budget velocity, phase balance, cascade detection from raw PACT file state. Each metric has documented computation logic in code comments and shows 'insufficient data' placeholder when data is unavailable (AC17). Uses recharts for any health metric charts.

# Module invariants:
#   - All TreeNode structures have depth <= 2 (0-indexed, max 3 levels)
#   - PipelineState always contains exactly 8 PhaseStep objects in fixed order
#   - Percentage values are always in range [0.0, 100.0]
#   - Ratio values are always >= 0.0
#   - ExpansionState.expanded_ids contains only valid component IDs present in tree
#   - Phase enum values follow strict progression: Interview→Shape→Decompose→Contract→Test→Implement→Integrate→Polish
#   - All HealthMetricResult discriminated unions have exactly one of: status='computed'|'insufficient'|'error'
#   - MetricHistory.snapshots are ordered by timestamp ascending
#   - All parse functions return Result type and never throw exceptions on malformed input
#   - SSE events have version=1 for current schema

class Phase(Enum):
    """Eight PACT pipeline phases in strict order"""
    Interview = "Interview"
    Shape = "Shape"
    Decompose = "Decompose"
    Contract = "Contract"
    Test = "Test"
    Implement = "Implement"
    Integrate = "Integrate"
    Polish = "Polish"

class PhaseStatus(Enum):
    """Execution status of a single phase"""
    pending = "pending"
    active = "active"
    completed = "completed"
    error = "error"
    skipped = "skipped"

class PhaseMetadata:
    """Optional metadata for a phase step"""
    start_time: int = None                   # optional, Unix timestamp when phase started
    end_time: int = None                     # optional, Unix timestamp when phase ended
    error_message: str = None                # optional, Error details if status is error
    artifacts_count: int = None              # optional, Number of artifacts produced in this phase

class PhaseStep:
    """A single step in the pipeline visualization"""
    id: str                                  # required, Unique identifier for this step (phase name lowercased)
    label: str                               # required, Display label for the phase
    status: PhaseStatus                      # required, Current execution status
    metadata: PhaseMetadata = None           # optional, Additional phase metadata

class ContractStatus(Enum):
    """Status of a component contract definition and validation"""
    draft = "draft"
    defined = "defined"
    passed = "passed"
    failed = "failed"
    skipped = "skipped"
    unknown = "unknown"

class ComponentContractData:
    """Contract and test status for a single component"""
    component_id: str                        # required, Unique component identifier
    name: str                                # required, Human-readable component name
    contract_status: ContractStatus          # required, Contract definition status
    test_status: ContractStatus              # required, Contract test validation status
    test_count: int = None                   # optional, Total number of tests
    passed_tests: int = None                 # optional, Number of passed tests

class TreeNode:
    """Recursive tree node structure for component hierarchy. Max 3 levels enforced at parse time."""
    data: ComponentContractData              # required, Component data at this node
    children: list                           # required, Child nodes (recursive TreeNode list)
    depth: int                               # required, Current depth level (0-indexed, max 2)

class Ratio:
    """Branded type for ratio values (0.0 to infinity, unbounded)"""
    value: float                             # required, Numeric ratio value

class Percentage:
    """Branded type for percentage values (0.0 to 100.0)"""
    value: float                             # required, Percentage value between 0 and 100

class ComputedMetric:
    """Successfully computed metric value"""
    status: str                              # required, Must be 'computed'
    value: float                             # required, Computed metric value

class InsufficientDataMetric:
    """Metric could not be computed due to insufficient data"""
    status: str                              # required, Must be 'insufficient'
    reason: str                              # required, Human-readable explanation of missing data

class ErrorMetric:
    """Metric computation failed with error"""
    status: str                              # required, Must be 'error'
    error: str                               # required, Error message

HealthMetricResult = ComputedMetric | InsufficientDataMetric | ErrorMetric

class MetricSnapshot:
    """Single timestamped metric value for time-series data"""
    timestamp: int                           # required, Unix timestamp in milliseconds
    value: float                             # required, Metric value at this timestamp

class MetricHistory:
    """Time-series history of a metric"""
    metric_name: str                         # required, Name of the metric being tracked
    snapshots: list                          # required, Ordered list of metric snapshots

class RechartDataPoint:
    """Recharts-compatible data point format"""
    name: str                                # required, X-axis label (e.g., timestamp formatted as string)
    metric1: float = None                    # optional, First metric value (null if unavailable)
    metric2: float = None                    # optional, Second metric value (null if unavailable)
    metric3: float = None                    # optional, Third metric value (null if unavailable)

class ParseError:
    """Error encountered during file parsing"""
    file_path: str                           # required, Path to file that failed to parse
    error_type: str                          # required, Category of error (e.g., 'malformed_json', 'missing_field')
    message: str                             # required, Detailed error message
    line_number: int = None                  # optional, Line number where error occurred if applicable

class OkResult:
    """Success result wrapper"""
    ok: bool                                 # required, Must be true
    value: any                               # required, Parsed data value

class ErrResult:
    """Error result wrapper"""
    ok: bool                                 # required, Must be false
    error: ParseError                        # required, Parse error details

Result = OkResult | ErrResult

class RawPactData:
    """Raw unvalidated data read from PACT directory files"""
    phase_files: dict                        # required, Map of phase name to file content (JSON string)
    component_files: list                    # required, List of component contract file paths
    session_log: str = None                  # optional, Raw session log content
    metadata: dict                           # required, Additional metadata (timestamps, version, etc.)

class ConfidentPhaseDetection:
    """Confident phase detection result"""
    result_type: str                         # required, Must be 'confident'
    phase: Phase                             # required, Detected phase
    confidence: str                          # required, Confidence level: 'high' or 'medium'

class AmbiguousPhaseDetection:
    """Ambiguous phase detection result (multiple candidates)"""
    result_type: str                         # required, Must be 'ambiguous'
    candidates: list                         # required, List of candidate phases
    reason: str                              # required, Explanation of ambiguity

PhaseDetectionResult = ConfidentPhaseDetection | AmbiguousPhaseDetection

class PactPhaseChangeEvent:
    """SSE event for phase transitions"""
    type: str                                # required, Must be 'pact:phase-change'
    version: int                             # required, Event schema version (1)
    project_id: str                          # required, Project identifier
    old_phase: Phase = None                  # optional, Previous phase (null if first phase)
    new_phase: Phase                         # required, Current phase
    timestamp: int                           # required, Unix timestamp in milliseconds

class PactHealthUpdateEvent:
    """SSE event for health metric updates"""
    type: str                                # required, Must be 'pact:health-update'
    version: int                             # required, Event schema version (1)
    project_id: str                          # required, Project identifier
    metric_name: str                         # required, Name of updated metric
    delta: dict                              # required, Delta payload with changed values only
    timestamp: int                           # required, Unix timestamp in milliseconds

class ExpansionState:
    """UI expansion state for component tree"""
    expanded_ids: list                       # required, Set of expanded component IDs

class HealthMetrics:
    """Collection of all computed health metrics"""
    output_planning_ratio: HealthMetricResult # required, Ratio of output tokens to planning tokens
    rejection_rate: HealthMetricResult       # required, Percentage of rejected artifacts
    budget_velocity: HealthMetricResult      # required, Token spend per unit time
    phase_balance: HealthMetricResult        # required, Distribution balance across phases
    cascade_detection: HealthMetricResult    # required, Detected cascading failures score

class PipelineState:
    """Complete state of PACT pipeline for visualization"""
    steps: list                              # required, Ordered list of all 8 phase steps
    current_phase: Phase = None              # optional, Currently active phase (null if not started)
    component_tree: TreeNode = None          # optional, Component hierarchy tree (null if no components)

def parse_pact_directory(
    directory_path: str,
) -> Result:
    """
    Parse all PACT files from a project directory into raw unvalidated data. Never throws on malformed files; returns Result with parse errors.

    Preconditions:
      - directory_path is a valid filesystem path

    Postconditions:
      - Returns Ok(RawPactData) if directory readable
      - Returns Err(ParseError) if directory missing or unreadable
      - Never throws exceptions

    Errors:
      - DirectoryNotFound (ParseError): directory_path does not exist
      - PermissionDenied (ParseError): insufficient permissions to read directory

    Side effects: none
    Idempotent: no
    """
    ...

def validate_raw_pact_data(
    raw_data: RawPactData,
) -> Result:
    """
    Validate raw PACT data using Zod schemas. Transforms unvalidated data into typed domain objects.

    Preconditions:
      - raw_data contains at least phase_files and metadata keys

    Postconditions:
      - Returns Ok with validated data structure
      - Returns Err with validation errors if schema mismatch

    Errors:
      - SchemaValidationFailure (ParseError): data does not match expected Zod schema
      - MissingRequiredField (ParseError): required field is missing from raw data

    Side effects: none
    Idempotent: no
    """
    ...

def detect_current_phase(
    validated_data: dict,
) -> PhaseDetectionResult:
    """
    Detect the current PACT phase from validated directory state using documented heuristics. Returns confident result with high/medium confidence, or ambiguous result with candidate phases.

    Preconditions:
      - validated_data passed Zod schema validation

    Postconditions:
      - Returns ConfidentPhaseDetection if clear phase indicators present
      - Returns AmbiguousPhaseDetection if multiple phases equally likely
      - Confidence level documented in heuristic comments

    Side effects: none
    Idempotent: no
    """
    ...

def build_pipeline_state(
    validated_data: dict,
    phase_detection: PhaseDetectionResult,
) -> PipelineState:
    """
    Build complete pipeline visualization state from validated data and phase detection result. Generates all 8 PhaseStep objects with correct status.

    Preconditions:
      - validated_data is valid
      - phase_detection is valid PhaseDetectionResult

    Postconditions:
      - Returns PipelineState with exactly 8 PhaseStep objects
      - Steps ordered Interview→Polish
      - Current phase marked as 'active' status
      - Completed phases marked 'completed'
      - Future phases marked 'pending'

    Side effects: none
    Idempotent: no
    """
    ...

def parse_component_tree(
    validated_data: dict,
) -> Result:
    """
    Parse component hierarchy from validated data into recursive TreeNode structure. Enforces max depth of 3 levels at parse time with runtime guards.

    Preconditions:
      - validated_data contains component_files

    Postconditions:
      - Returns Ok(TreeNode) if parsing succeeds
      - All nodes have depth <= 2 (0-indexed, max 3 levels)
      - Returns Err if max depth exceeded
      - Returns Err if malformed component data

    Errors:
      - MaxDepthExceeded (ParseError): component tree exceeds 3 levels
      - InvalidComponentData (ParseError): component data does not match expected schema

    Side effects: none
    Idempotent: no
    """
    ...

def validate_tree_depth(
    tree: TreeNode,
    max_depth: int,
) -> bool:
    """
    Runtime guard to validate that a TreeNode structure does not exceed max depth of 3 levels.

    Preconditions:
      - max_depth >= 0

    Postconditions:
      - Returns true if all nodes have depth <= max_depth
      - Returns false if any node exceeds max_depth

    Side effects: none
    Idempotent: no
    """
    ...

def compute_output_planning_ratio(
    session_data: dict,
) -> HealthMetricResult:
    """
    Compute output/planning token ratio from session data. Returns HealthMetricResult (computed/insufficient/error). Documented computation: output_tokens / planning_tokens.

    Preconditions:
      - session_data is validated

    Postconditions:
      - Returns ComputedMetric with Ratio if both token counts available and planning_tokens > 0
      - Returns InsufficientDataMetric if token counts missing
      - Returns ErrorMetric if planning_tokens = 0 (division by zero)

    Side effects: none
    Idempotent: no
    """
    ...

def compute_rejection_rate(
    artifact_data: dict,
) -> HealthMetricResult:
    """
    Compute artifact rejection rate as percentage. Returns HealthMetricResult. Documented computation: (rejected_count / total_artifacts) * 100.

    Preconditions:
      - artifact_data is validated

    Postconditions:
      - Returns ComputedMetric with Percentage if artifact counts available
      - Returns InsufficientDataMetric if no artifacts tracked
      - Percentage value in range [0, 100]

    Side effects: none
    Idempotent: no
    """
    ...

def compute_budget_velocity(
    session_data: dict,
) -> HealthMetricResult:
    """
    Compute token spend velocity (tokens per hour). Returns HealthMetricResult. Documented computation: total_tokens / elapsed_hours.

    Preconditions:
      - session_data contains timestamps and token counts

    Postconditions:
      - Returns ComputedMetric if session has elapsed time > 0
      - Returns InsufficientDataMetric if session too short or no tokens
      - Returns ErrorMetric if elapsed_time <= 0

    Side effects: none
    Idempotent: no
    """
    ...

def compute_phase_balance(
    phase_history: list,
) -> HealthMetricResult:
    """
    Compute phase distribution balance score. Returns HealthMetricResult. Documented computation: Shannon entropy or coefficient of variation across phase durations.

    Preconditions:
      - phase_history is list of numeric durations

    Postconditions:
      - Returns ComputedMetric if at least 2 phases completed
      - Returns InsufficientDataMetric if < 2 phases completed
      - Score normalized to [0, 1] where 1 = perfectly balanced

    Side effects: none
    Idempotent: no
    """
    ...

def detect_cascades(
    phase_transition_log: list,
) -> HealthMetricResult:
    """
    Detect cascading failures in phase transitions. Returns HealthMetricResult with cascade score. Documented computation: count of phase reversions or re-entry patterns.

    Preconditions:
      - phase_transition_log is ordered by timestamp

    Postconditions:
      - Returns ComputedMetric with cascade count if transitions available
      - Returns InsufficientDataMetric if < 3 transitions
      - Score >= 0 where 0 = no cascades

    Side effects: none
    Idempotent: no
    """
    ...

def compute_all_health_metrics(
    validated_data: dict,
) -> HealthMetrics:
    """
    Compute all health metrics in one pass. Returns HealthMetrics struct with all metric results.

    Preconditions:
      - validated_data passed schema validation

    Postconditions:
      - Returns HealthMetrics with all 5 metric results
      - Each metric is either ComputedMetric, InsufficientDataMetric, or ErrorMetric

    Side effects: none
    Idempotent: no
    """
    ...

def transform_to_recharts(
    metric_history: MetricHistory,
    format_timestamp: bool = None,
) -> list:
    """
    Transform domain metric history to recharts-compatible data point array. Pure transformer function.

    Preconditions:
      - metric_history.snapshots is ordered by timestamp

    Postconditions:
      - Returns list of RechartDataPoint objects
      - name field contains formatted timestamp or raw value
      - metric1 field contains snapshot value
      - Array length equals snapshots length

    Side effects: none
    Idempotent: no
    """
    ...

def transform_multi_metric_to_recharts(
    metric_histories: list,
) -> list:
    """
    Transform multiple metric histories into single recharts dataset with aligned timestamps. Handles missing data points as null.

    Preconditions:
      - All metric_histories have non-empty snapshots

    Postconditions:
      - Returns list of RechartDataPoint with up to 3 metrics per point
      - Timestamps aligned across all metrics
      - Missing values set to null
      - Array sorted by timestamp ascending

    Errors:
      - TooManyMetrics (ValueError): more than 3 metric histories provided
          max_metrics: 3

    Side effects: none
    Idempotent: no
    """
    ...

def validate_metric_range(
    metric_type: str,
    value: float,
) -> bool:
    """
    Validate that a metric value is within expected range based on metric type (Ratio unbounded, Percentage 0-100).

    Preconditions:
      - metric_type is 'ratio' or 'percentage'

    Postconditions:
      - Returns true if value is valid for metric_type
      - Returns false otherwise

    Side effects: none
    Idempotent: no
    """
    ...

def create_expansion_state(
    tree: TreeNode,
    expand_all: bool = None,
) -> ExpansionState:
    """
    Create initial expansion state for component tree UI. Returns ExpansionState with default settings.

    Preconditions:
      - tree is valid TreeNode

    Postconditions:
      - Returns ExpansionState with expanded_ids populated
      - If expand_all=true, all component IDs in expanded_ids
      - If expand_all=false, only root expanded

    Side effects: none
    Idempotent: no
    """
    ...

def toggle_node_expansion(
    current_state: ExpansionState,
    node_id: str,
) -> ExpansionState:
    """
    Toggle expansion state for a specific tree node. Pure function returning new ExpansionState.

    Preconditions:
      - current_state is valid

    Postconditions:
      - Returns new ExpansionState
      - If node_id was expanded, it is removed from expanded_ids
      - If node_id was collapsed, it is added to expanded_ids
      - Original current_state unchanged

    Side effects: none
    Idempotent: no
    """
    ...

def emit_phase_change_event(
    project_id: str,
    old_phase: Phase = None,
    new_phase: Phase,
) -> None:
    """
    Emit SSE event when PACT phase changes. Constructs PactPhaseChangeEvent and publishes to SSE bus.

    Preconditions:
      - project_id is non-empty
      - new_phase is valid Phase

    Postconditions:
      - PactPhaseChangeEvent published to SSE bus
      - Event includes timestamp

    Errors:
      - SSEBusUnavailable (RuntimeError): SSE event bus is not initialized

    Side effects: none
    Idempotent: no
    """
    ...

def emit_health_update_event(
    project_id: str,
    metric_name: str,
    delta: dict,
) -> None:
    """
    Emit SSE event when health metric updates. Constructs PactHealthUpdateEvent with delta payload.

    Preconditions:
      - project_id is non-empty
      - metric_name is one of: output_planning_ratio, rejection_rate, budget_velocity, phase_balance, cascade_detection

    Postconditions:
      - PactHealthUpdateEvent published to SSE bus
      - Event includes timestamp and delta

    Errors:
      - SSEBusUnavailable (RuntimeError): SSE event bus is not initialized

    Side effects: none
    Idempotent: no
    """
    ...

def watch_pact_directory(
    directory_path: str,
    on_change_callback: str,
) -> str:
    """
    Set up filesystem watcher on PACT directory. Triggers re-parsing and event emission on file changes. Uses chokidar.

    Preconditions:
      - directory_path exists and is readable

    Postconditions:
      - Returns watcher_id for cleanup
      - Filesystem watcher active on directory
      - on_change_callback invoked when files change

    Errors:
      - DirectoryNotFound (FileNotFoundError): directory_path does not exist
      - WatcherInitializationFailed (RuntimeError): chokidar cannot initialize watcher

    Side effects: none
    Idempotent: no
    """
    ...

def cleanup_watcher(
    watcher_id: str,
) -> None:
    """
    Stop and cleanup filesystem watcher by watcher_id.

    Preconditions:
      - watcher_id corresponds to active watcher

    Postconditions:
      - Watcher stopped and resources released
      - No further callbacks triggered

    Errors:
      - WatcherNotFound (ValueError): watcher_id does not exist

    Side effects: none
    Idempotent: no
    """
    ...

# ── REQUIRED EXPORTS ──────────────────────────────────
# Your implementation module MUST export ALL of these names
# with EXACTLY these spellings. Tests import them by name.
# __all__ = ['Phase', 'PhaseStatus', 'PhaseMetadata', 'PhaseStep', 'ContractStatus', 'ComponentContractData', 'TreeNode', 'Ratio', 'Percentage', 'ComputedMetric', 'InsufficientDataMetric', 'ErrorMetric', 'HealthMetricResult', 'MetricSnapshot', 'MetricHistory', 'RechartDataPoint', 'ParseError', 'OkResult', 'ErrResult', 'Result', 'RawPactData', 'ConfidentPhaseDetection', 'AmbiguousPhaseDetection', 'PhaseDetectionResult', 'PactPhaseChangeEvent', 'PactHealthUpdateEvent', 'ExpansionState', 'HealthMetrics', 'PipelineState', 'parse_pact_directory', 'validate_raw_pact_data', 'detect_current_phase', 'build_pipeline_state', 'parse_component_tree', 'validate_tree_depth', 'compute_output_planning_ratio', 'compute_rejection_rate', 'compute_budget_velocity', 'compute_phase_balance', 'detect_cascades', 'compute_all_health_metrics', 'transform_to_recharts', 'transform_multi_metric_to_recharts', 'validate_metric_range', 'create_expansion_state', 'toggle_node_expansion', 'emit_phase_change_event', 'emit_health_update_event', 'watch_pact_directory', 'cleanup_watcher']
