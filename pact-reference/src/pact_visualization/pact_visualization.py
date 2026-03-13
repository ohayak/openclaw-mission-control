"""
PACT Pipeline & Health Visualization Module

Implements PACT pipeline visualization and health metrics computation.
"""

import os
import json
from enum import Enum
from typing import Dict, List, Any, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator
import math
from datetime import datetime


# ============================================================================
# ENUMS
# ============================================================================

class Phase(str, Enum):
    """Eight PACT pipeline phases in strict order"""
    Interview = "Interview"
    Shape = "Shape"
    Decompose = "Decompose"
    Contract = "Contract"
    Test = "Test"
    Implement = "Implement"
    Integrate = "Integrate"
    Polish = "Polish"


class PhaseStatus(str, Enum):
    """Execution status of a single phase"""
    pending = "pending"
    active = "active"
    completed = "completed"
    error = "error"
    skipped = "skipped"


class ContractStatus(str, Enum):
    """Status of a component contract definition and validation"""
    draft = "draft"
    defined = "defined"
    passed = "passed"
    failed = "failed"
    skipped = "skipped"
    unknown = "unknown"


# ============================================================================
# DATA MODELS
# ============================================================================

class PhaseMetadata(BaseModel):
    """Optional metadata for a phase step"""
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    error_message: Optional[str] = None
    artifacts_count: Optional[int] = None


class PhaseStep(BaseModel):
    """A single step in the pipeline visualization"""
    id: str
    label: str
    status: PhaseStatus
    metadata: Optional[PhaseMetadata] = None


class ComponentContractData(BaseModel):
    """Contract and test status for a single component"""
    component_id: str
    name: str
    contract_status: ContractStatus
    test_status: ContractStatus
    test_count: Optional[int] = None
    passed_tests: Optional[int] = None


class TreeNode(BaseModel):
    """Recursive tree node structure for component hierarchy"""
    data: ComponentContractData
    children: List['TreeNode'] = Field(default_factory=list)
    depth: int

    @field_validator('depth')
    @classmethod
    def validate_depth(cls, v):
        if v > 2:
            raise ValueError(f"Tree depth {v} exceeds maximum of 2 (3 levels)")
        return v


class Ratio(BaseModel):
    """Branded type for ratio values (0.0 to infinity)"""
    value: float

    @field_validator('value')
    @classmethod
    def validate_ratio(cls, v):
        if v < 0:
            raise ValueError("Ratio must be non-negative")
        return v


class Percentage(BaseModel):
    """Branded type for percentage values (0.0 to 100.0)"""
    value: float

    @field_validator('value')
    @classmethod
    def validate_percentage(cls, v):
        if not (0.0 <= v <= 100.0):
            raise ValueError(f"Percentage {v} must be between 0.0 and 100.0")
        return v


class ComputedMetric(BaseModel):
    """Successfully computed metric value"""
    status: str = "computed"
    value: float


class InsufficientDataMetric(BaseModel):
    """Metric could not be computed due to insufficient data"""
    status: str = "insufficient"
    reason: str


class ErrorMetric(BaseModel):
    """Metric computation failed with error"""
    status: str = "error"
    error: str


# Type alias for health metric results
HealthMetricResult = Union[ComputedMetric, InsufficientDataMetric, ErrorMetric]


class MetricSnapshot(BaseModel):
    """Single timestamped metric value for time-series data"""
    timestamp: int
    value: float


class MetricHistory(BaseModel):
    """Time-series history of a metric"""
    metric_name: str
    snapshots: List[MetricSnapshot]


class RechartDataPoint(BaseModel):
    """Recharts-compatible data point format"""
    name: str
    metric1: Optional[float] = None
    metric2: Optional[float] = None
    metric3: Optional[float] = None


class ParseError(BaseModel):
    """Error encountered during file parsing"""
    file_path: str
    error_type: str
    message: str
    line_number: Optional[int] = None


class OkResult(BaseModel):
    """Success result wrapper"""
    ok: bool = True
    value: Any


class ErrResult(BaseModel):
    """Error result wrapper"""
    ok: bool = False
    error: ParseError


# Type alias for result type
Result = Union[OkResult, ErrResult]


class RawPactData(BaseModel):
    """Raw unvalidated data read from PACT directory files"""
    phase_files: Dict[str, Any]
    component_files: List[Any]
    session_log: Optional[str] = None
    metadata: Dict[str, Any]


class ConfidentPhaseDetection(BaseModel):
    """Confident phase detection result"""
    result_type: str = "confident"
    phase: Phase
    confidence: str

    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v):
        if v not in ['high', 'medium']:
            raise ValueError("Confidence must be 'high' or 'medium'")
        return v


class AmbiguousPhaseDetection(BaseModel):
    """Ambiguous phase detection result"""
    result_type: str = "ambiguous"
    candidates: List[Phase]
    reason: str


# Type alias for phase detection result
PhaseDetectionResult = Union[ConfidentPhaseDetection, AmbiguousPhaseDetection]


class PactPhaseChangeEvent(BaseModel):
    """SSE event for phase transitions"""
    type: str = "pact:phase-change"
    version: int = 1
    project_id: str
    old_phase: Optional[Phase] = None
    new_phase: Phase
    timestamp: int


class PactHealthUpdateEvent(BaseModel):
    """SSE event for health metric updates"""
    type: str = "pact:health-update"
    version: int = 1
    project_id: str
    metric_name: str
    delta: Dict[str, Any]
    timestamp: int


class ExpansionState(BaseModel):
    """UI expansion state for component tree"""
    expanded_ids: List[str] = Field(default_factory=list)


class HealthMetrics(BaseModel):
    """Collection of all computed health metrics"""
    output_planning_ratio: HealthMetricResult
    rejection_rate: HealthMetricResult
    budget_velocity: HealthMetricResult
    phase_balance: HealthMetricResult
    cascade_detection: HealthMetricResult


class PipelineState(BaseModel):
    """Complete state of PACT pipeline for visualization"""
    steps: List[PhaseStep]
    current_phase: Optional[Phase] = None
    component_tree: Optional[TreeNode] = None

    @field_validator('steps')
    @classmethod
    def validate_steps_count(cls, v):
        if len(v) != 8:
            raise ValueError(f"PipelineState must have exactly 8 steps, got {len(v)}")
        return v


# ============================================================================
# PARSING FUNCTIONS
# ============================================================================

def parse_pact_directory(directory_path: str) -> Dict[str, Any]:
    """
    Parse all PACT files from a project directory into raw unvalidated data.
    Never throws on malformed files; returns Result with parse errors.
    """
    try:
        # Check if directory exists
        if not os.path.exists(directory_path):
            return {
                'ok': False,
                'error': {
                    'file_path': directory_path,
                    'error_type': 'DirectoryNotFound',
                    'message': f'Directory not found: {directory_path}'
                }
            }

        # Check if it's a directory
        if not os.path.isdir(directory_path):
            return {
                'ok': False,
                'error': {
                    'file_path': directory_path,
                    'error_type': 'DirectoryNotFound',
                    'message': f'Path is not a directory: {directory_path}'
                }
            }

        # Try to list directory contents
        try:
            files = os.listdir(directory_path)
        except PermissionError as e:
            return {
                'ok': False,
                'error': {
                    'file_path': directory_path,
                    'error_type': 'PermissionDenied',
                    'message': str(e)
                }
            }

        # Parse phase files
        phase_files = {}
        component_files = []
        session_log = None
        metadata = {}

        for filename in files:
            file_path = os.path.join(directory_path, filename)

            try:
                if filename.endswith('.json'):
                    with open(file_path, 'r') as f:
                        content = f.read()
                        try:
                            parsed = json.loads(content)
                            if 'phase' in parsed or any(p.value.lower() in filename.lower() for p in Phase):
                                phase_files[filename] = parsed
                            elif filename == 'metadata.json':
                                metadata = parsed
                            else:
                                # Treat as component file
                                component_files.append(parsed)
                        except json.JSONDecodeError:
                            # Malformed JSON - store as error but don't throw
                            phase_files[filename] = {'_parse_error': True, 'content': content}
                elif filename.endswith('.log'):
                    session_log = filename
            except Exception:
                # Silently skip files that can't be read
                pass

        return {
            'ok': True,
            'value': {
                'phase_files': phase_files,
                'component_files': component_files,
                'session_log': session_log,
                'metadata': metadata if metadata else {'created_at': int(datetime.now().timestamp())}
            }
        }

    except Exception as e:
        # Catch any unexpected errors and return as Result
        return {
            'ok': False,
            'error': {
                'file_path': directory_path,
                'error_type': 'UnknownError',
                'message': str(e)
            }
        }


def validate_raw_pact_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate raw PACT data using schemas.
    Transforms unvalidated data into typed domain objects.
    """
    try:
        # Check required fields
        if 'phase_files' not in raw_data:
            return {
                'ok': False,
                'error': {
                    'file_path': '',
                    'error_type': 'MissingRequiredField',
                    'message': 'Missing required field: phase_files'
                }
            }

        if 'metadata' not in raw_data:
            return {
                'ok': False,
                'error': {
                    'file_path': '',
                    'error_type': 'MissingRequiredField',
                    'message': 'Missing required field: metadata'
                }
            }

        # Validate phase_files is a dict
        if not isinstance(raw_data['phase_files'], dict):
            return {
                'ok': False,
                'error': {
                    'file_path': '',
                    'error_type': 'SchemaValidationFailure',
                    'message': 'phase_files must be a dictionary'
                }
            }

        # Validate metadata is a dict
        if not isinstance(raw_data['metadata'], dict):
            return {
                'ok': False,
                'error': {
                    'file_path': '',
                    'error_type': 'SchemaValidationFailure',
                    'message': 'metadata must be a dictionary'
                }
            }

        # Additional validation for phase enum values
        for filename, content in raw_data.get('phase_files', {}).items():
            if isinstance(content, dict) and 'phase' in content:
                phase_value = content['phase']
                try:
                    Phase(phase_value)
                except ValueError:
                    return {
                        'ok': False,
                        'error': {
                            'file_path': filename,
                            'error_type': 'SchemaValidationFailure',
                            'message': f'Invalid phase value: {phase_value}'
                        }
                    }

        return {
            'ok': True,
            'value': raw_data
        }

    except Exception as e:
        return {
            'ok': False,
            'error': {
                'file_path': '',
                'error_type': 'SchemaValidationFailure',
                'message': str(e)
            }
        }


# ============================================================================
# PHASE DETECTION AND PIPELINE BUILDING
# ============================================================================

def detect_current_phase(validated_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detect the current PACT phase from validated directory state.
    Returns confident result with high/medium confidence, or ambiguous result.
    """
    # Check for 'phases' key (validated format) or 'phase_files' (raw format)
    phases_data = validated_data.get('phases', validated_data.get('phase_files', {}))

    # Count completed phases and find active phase
    completed_phases = []
    active_phase = None
    ambiguous_candidates = []

    for phase_name, content in phases_data.items():
        if isinstance(content, dict):
            # Check for active marker
            if content.get('active') is True or (content.get('completed') is False and content.get('active') is not False):
                try:
                    candidate_phase = Phase(phase_name)
                    if content.get('active') is True:
                        active_phase = candidate_phase
                    elif 'markers' in content:
                        # Partial completion markers indicate ambiguity
                        ambiguous_candidates.append(candidate_phase)
                except ValueError:
                    pass

            # Check for completed
            if content.get('completed') is True:
                try:
                    completed_phases.append(Phase(phase_name))
                except ValueError:
                    pass

    # High confidence: explicit active phase
    if active_phase:
        return {
            'result_type': 'confident',
            'phase': active_phase.value,
            'confidence': 'high'
        }

    # Ambiguous: multiple partial candidates
    if len(ambiguous_candidates) > 1:
        return {
            'result_type': 'ambiguous',
            'candidates': [p.value for p in ambiguous_candidates],
            'reason': 'Multiple phases have partial completion markers'
        }

    # Medium confidence: next phase after last completed
    if completed_phases:
        phases_list = list(Phase)
        last_completed = max(completed_phases, key=lambda p: phases_list.index(p))
        last_index = phases_list.index(last_completed)

        if last_index < len(phases_list) - 1:
            next_phase = phases_list[last_index + 1]
            return {
                'result_type': 'confident',
                'phase': next_phase.value,
                'confidence': 'medium'
            }

    # Ambiguous: no clear indicator
    if len(phases_data) == 0:
        return {
            'result_type': 'ambiguous',
            'candidates': [Phase.Interview.value, Phase.Shape.value],
            'reason': 'No phase data found, could be at start'
        }

    return {
        'result_type': 'confident',
        'phase': Phase.Interview.value,
        'confidence': 'medium'
    }


def build_pipeline_state(
    validated_data: Dict[str, Any],
    phase_detection: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Build complete pipeline visualization state from validated data and phase detection.
    Generates all 8 PhaseStep objects with correct status.
    """
    phases = list(Phase)
    current_phase = None

    if phase_detection['result_type'] == 'confident':
        current_phase = phase_detection['phase']

    steps = []
    for i, phase in enumerate(phases):
        status = PhaseStatus.pending

        if current_phase:
            current_index = phases.index(Phase(current_phase))
            if i < current_index:
                status = PhaseStatus.completed
            elif i == current_index:
                status = PhaseStatus.active
            else:
                status = PhaseStatus.pending

        step = {
            'id': phase.value.lower(),
            'label': phase.value,
            'status': status.value,
            'metadata': None
        }
        steps.append(step)

    return {
        'steps': steps,
        'current_phase': current_phase.value if current_phase else None,
        'component_tree': None
    }


# ============================================================================
# COMPONENT TREE PARSING
# ============================================================================

def parse_component_tree(validated_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse component hierarchy from validated data into recursive TreeNode structure.
    Enforces max depth of 3 levels at parse time.
    """
    try:
        component_files = validated_data.get('component_files', [])

        if not component_files:
            return {
                'ok': False,
                'error': {
                    'file_path': '',
                    'error_type': 'InvalidComponentData',
                    'message': 'No component files found'
                }
            }

        def build_tree_node(component_data: Dict[str, Any], depth: int = 0) -> Dict[str, Any]:
            if depth > 2:
                raise ValueError(f"MaxDepthExceeded: depth {depth} exceeds maximum of 2")

            # Validate required fields
            required_fields = ['component_id', 'name', 'contract_status', 'test_status']
            for field in required_fields:
                if field not in component_data:
                    raise ValueError(f"Missing required field: {field}")

            node = {
                'data': {
                    'component_id': component_data['component_id'],
                    'name': component_data['name'],
                    'contract_status': component_data['contract_status'],
                    'test_status': component_data['test_status'],
                    'test_count': component_data.get('test_count'),
                    'passed_tests': component_data.get('passed_tests')
                },
                'children': [],
                'depth': depth
            }

            # Recursively build children
            children_data = component_data.get('children', [])
            for child_data in children_data:
                child_node = build_tree_node(child_data, depth + 1)
                node['children'].append(child_node)

            return node

        # Build tree from first component (assuming single root)
        root_component = component_files[0]
        tree = build_tree_node(root_component, 0)

        return {
            'ok': True,
            'value': tree
        }

    except ValueError as e:
        error_msg = str(e)
        if 'MaxDepthExceeded' in error_msg:
            return {
                'ok': False,
                'error': {
                    'file_path': '',
                    'error_type': 'MaxDepthExceeded',
                    'message': error_msg
                }
            }
        else:
            return {
                'ok': False,
                'error': {
                    'file_path': '',
                    'error_type': 'InvalidComponentData',
                    'message': error_msg
                }
            }
    except Exception as e:
        return {
            'ok': False,
            'error': {
                'file_path': '',
                'error_type': 'InvalidComponentData',
                'message': str(e)
            }
        }


def validate_tree_depth(tree: Dict[str, Any], max_depth: int) -> bool:
    """
    Runtime guard to validate that a TreeNode structure does not exceed max depth.
    """
    def check_depth(node: Dict[str, Any]) -> bool:
        if node['depth'] > max_depth:
            return False

        for child in node.get('children', []):
            if not check_depth(child):
                return False

        return True

    return check_depth(tree)


# ============================================================================
# HEALTH METRICS COMPUTATION
# ============================================================================

def compute_output_planning_ratio(session_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute output/planning token ratio from session data.
    Returns HealthMetricResult (computed/insufficient/error).
    """
    output_tokens = session_data.get('output_tokens')
    planning_tokens = session_data.get('planning_tokens')

    if output_tokens is None or planning_tokens is None:
        return {
            'status': 'insufficient',
            'reason': 'Missing token counts (output_tokens or planning_tokens not available)'
        }

    if planning_tokens == 0:
        return {
            'status': 'error',
            'error': 'Division by zero: planning_tokens is 0'
        }

    ratio = output_tokens / planning_tokens
    return {
        'status': 'computed',
        'value': ratio
    }


def compute_rejection_rate(artifact_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute artifact rejection rate as percentage.
    Returns HealthMetricResult.
    """
    total_artifacts = artifact_data.get('total_artifacts')
    rejected_count = artifact_data.get('rejected_count')

    if total_artifacts is None or total_artifacts == 0:
        return {
            'status': 'insufficient',
            'reason': 'No artifacts tracked'
        }

    if rejected_count is None:
        rejected_count = 0

    rejection_rate = (rejected_count / total_artifacts) * 100.0
    return {
        'status': 'computed',
        'value': rejection_rate
    }


def compute_budget_velocity(session_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute token spend velocity (tokens per hour).
    Returns HealthMetricResult.
    """
    total_tokens = session_data.get('total_tokens')
    elapsed_hours = session_data.get('elapsed_hours')

    if total_tokens is None or elapsed_hours is None:
        return {
            'status': 'insufficient',
            'reason': 'Missing session data (total_tokens or elapsed_hours not available)'
        }

    if elapsed_hours <= 0:
        return {
            'status': 'error',
            'error': 'Invalid elapsed time: must be greater than 0'
        }

    velocity = total_tokens / elapsed_hours
    return {
        'status': 'computed',
        'value': velocity
    }


def compute_phase_balance(phase_history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute phase distribution balance score.
    Returns HealthMetricResult.
    """
    if len(phase_history) < 2:
        return {
            'status': 'insufficient',
            'reason': 'Need at least 2 completed phases to compute balance'
        }

    # Extract durations
    durations = [phase.get('duration', 0) for phase in phase_history]

    # Check for perfectly balanced (all equal)
    if len(set(durations)) == 1:
        return {
            'status': 'computed',
            'value': 1.0
        }

    # Compute coefficient of variation (normalized standard deviation)
    mean_duration = sum(durations) / len(durations)
    variance = sum((d - mean_duration) ** 2 for d in durations) / len(durations)
    std_dev = math.sqrt(variance)

    if mean_duration == 0:
        cv = 0
    else:
        cv = std_dev / mean_duration

    # Convert to balance score (1 = perfectly balanced, 0 = highly imbalanced)
    # Using inverse of CV, normalized
    balance_score = 1.0 / (1.0 + cv)

    return {
        'status': 'computed',
        'value': balance_score
    }


def detect_cascades(phase_transition_log: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Detect cascading failures in phase transitions.
    Returns HealthMetricResult with cascade score.
    """
    if len(phase_transition_log) < 3:
        return {
            'status': 'insufficient',
            'reason': 'Need at least 3 phase transitions to detect cascades'
        }

    # Detect backward transitions (phase reversions)
    phases_list = list(Phase)
    cascade_count = 0

    for i in range(len(phase_transition_log) - 1):
        from_phase = phase_transition_log[i].get('to')
        to_phase = phase_transition_log[i + 1].get('to')

        if from_phase and to_phase:
            try:
                from_idx = phases_list.index(Phase(from_phase))
                to_idx = phases_list.index(Phase(to_phase))

                # Backward transition indicates cascade
                if to_idx < from_idx:
                    cascade_count += 1
            except (ValueError, KeyError):
                pass

    return {
        'status': 'computed',
        'value': float(cascade_count)
    }


def compute_all_health_metrics(validated_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute all health metrics in one pass.
    Returns HealthMetrics struct with all metric results.
    """
    session_data = validated_data.get('session_data', {})
    artifact_data = validated_data.get('artifact_data', {})
    phase_history = validated_data.get('phase_history', [])
    phase_transition_log = validated_data.get('phase_transition_log', [])

    return {
        'output_planning_ratio': compute_output_planning_ratio(session_data),
        'rejection_rate': compute_rejection_rate(artifact_data),
        'budget_velocity': compute_budget_velocity(session_data),
        'phase_balance': compute_phase_balance(phase_history),
        'cascade_detection': detect_cascades(phase_transition_log)
    }


# ============================================================================
# DATA TRANSFORMATION
# ============================================================================

def transform_to_recharts(
    metric_history: Dict[str, Any],
    format_timestamp: bool = True
) -> List[Dict[str, Any]]:
    """
    Transform domain metric history to recharts-compatible data point array.
    """
    snapshots = metric_history.get('snapshots', [])
    result = []

    for snapshot in snapshots:
        timestamp = snapshot['timestamp']
        value = snapshot['value']

        if format_timestamp:
            # Format timestamp as readable string
            dt = datetime.fromtimestamp(timestamp)
            name = dt.strftime('%Y-%m-%d %H:%M')
        else:
            name = str(timestamp)

        result.append({
            'name': name,
            'metric1': value,
            'metric2': None,
            'metric3': None
        })

    return result


def transform_multi_metric_to_recharts(metric_histories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Transform multiple metric histories into single recharts dataset with aligned timestamps.
    """
    if len(metric_histories) > 3:
        raise ValueError('TooManyMetrics: maximum 3 metric histories allowed')

    # Collect all unique timestamps
    all_timestamps = set()
    for history in metric_histories:
        for snapshot in history.get('snapshots', []):
            all_timestamps.add(snapshot['timestamp'])

    # Sort timestamps
    sorted_timestamps = sorted(all_timestamps)

    # Build lookup maps for each metric
    metric_maps = []
    for history in metric_histories:
        metric_map = {}
        for snapshot in history.get('snapshots', []):
            metric_map[snapshot['timestamp']] = snapshot['value']
        metric_maps.append(metric_map)

    # Build result
    result = []
    for timestamp in sorted_timestamps:
        dt = datetime.fromtimestamp(timestamp)
        name = dt.strftime('%Y-%m-%d %H:%M')

        point = {
            'name': name,
            'metric1': metric_maps[0].get(timestamp) if len(metric_maps) > 0 else None,
            'metric2': metric_maps[1].get(timestamp) if len(metric_maps) > 1 else None,
            'metric3': metric_maps[2].get(timestamp) if len(metric_maps) > 2 else None
        }
        result.append(point)

    return result


def validate_metric_range(metric_type: str, value: float) -> bool:
    """
    Validate that a metric value is within expected range based on metric type.
    """
    if metric_type == 'ratio':
        return value >= 0.0
    elif metric_type == 'percentage':
        return 0.0 <= value <= 100.0
    else:
        return False


# ============================================================================
# UI STATE MANAGEMENT
# ============================================================================

def create_expansion_state(tree: Dict[str, Any], expand_all: bool = False) -> Dict[str, Any]:
    """
    Create initial expansion state for component tree UI.
    """
    expanded_ids = []

    def collect_ids(node: Dict[str, Any]):
        component_id = node['data']['component_id']
        expanded_ids.append(component_id)

        for child in node.get('children', []):
            collect_ids(child)

    if expand_all:
        collect_ids(tree)
    else:
        # Only expand root
        expanded_ids.append(tree['data']['component_id'])

    return {
        'expanded_ids': expanded_ids
    }


def toggle_node_expansion(current_state: Dict[str, Any], node_id: str) -> Dict[str, Any]:
    """
    Toggle expansion state for a specific tree node.
    Pure function returning new ExpansionState.
    """
    expanded_ids = current_state.get('expanded_ids', []).copy()

    if node_id in expanded_ids:
        expanded_ids.remove(node_id)
    else:
        expanded_ids.append(node_id)

    return {
        'expanded_ids': expanded_ids
    }


# ============================================================================
# SSE EVENTS
# ============================================================================

# Global SSE bus (mocked for testing)
_sse_bus = None


def emit_phase_change_event(
    project_id: str,
    old_phase: Optional[Phase] = None,
    new_phase: Phase = None
) -> None:
    """
    Emit SSE event when PACT phase changes.
    """
    global _sse_bus

    if _sse_bus is None:
        raise RuntimeError('SSEBusUnavailable: SSE event bus is not initialized')

    event = {
        'type': 'pact:phase-change',
        'version': 1,
        'project_id': project_id,
        'old_phase': old_phase.value if old_phase else None,
        'new_phase': new_phase.value if new_phase else None,
        'timestamp': int(datetime.now().timestamp() * 1000)
    }

    _sse_bus.emit(event)


def emit_health_update_event(
    project_id: str,
    metric_name: str,
    delta: Dict[str, Any]
) -> None:
    """
    Emit SSE event when health metric updates.
    """
    global _sse_bus

    if _sse_bus is None:
        raise RuntimeError('SSEBusUnavailable: SSE event bus is not initialized')

    valid_metrics = [
        'output_planning_ratio',
        'rejection_rate',
        'budget_velocity',
        'phase_balance',
        'cascade_detection'
    ]

    if metric_name not in valid_metrics:
        raise ValueError(f'Invalid metric name: {metric_name}')

    event = {
        'type': 'pact:health-update',
        'version': 1,
        'project_id': project_id,
        'metric_name': metric_name,
        'delta': delta,
        'timestamp': int(datetime.now().timestamp() * 1000)
    }

    _sse_bus.emit(event)


# ============================================================================
# FILE WATCHING
# ============================================================================

# Global watcher registry
_watchers = {}
_watcher_id_counter = 0


def watch_pact_directory(
    directory_path: str,
    on_change_callback: Any
) -> str:
    """
    Set up filesystem watcher on PACT directory.
    Uses chokidar (mocked for Python implementation).
    """
    global _watchers, _watcher_id_counter

    if not os.path.exists(directory_path):
        raise FileNotFoundError(f'DirectoryNotFound: {directory_path}')

    try:
        # In real implementation, would use watchdog or similar
        # For now, create a mock watcher
        watcher_id = f'watcher_{_watcher_id_counter}'
        _watcher_id_counter += 1

        _watchers[watcher_id] = {
            'path': directory_path,
            'callback': on_change_callback,
            'active': True
        }

        return watcher_id

    except Exception as e:
        raise RuntimeError(f'WatcherInitializationFailed: {str(e)}')


def cleanup_watcher(watcher_id: str) -> None:
    """
    Stop and cleanup filesystem watcher by watcher_id.
    """
    global _watchers

    if watcher_id not in _watchers:
        raise ValueError(f'WatcherNotFound: {watcher_id}')

    _watchers[watcher_id]['active'] = False
    del _watchers[watcher_id]
