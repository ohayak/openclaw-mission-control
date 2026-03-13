"""
PACT Pipeline & Health Visualization Package

Exports all public types and functions.
"""

import os
import json

from pact_visualization.pact_visualization import (
    # Enums
    Phase,
    PhaseStatus,
    ContractStatus,

    # Data Models
    PhaseMetadata,
    PhaseStep,
    ComponentContractData,
    TreeNode,
    Ratio,
    Percentage,
    ComputedMetric,
    InsufficientDataMetric,
    ErrorMetric,
    HealthMetricResult,
    MetricSnapshot,
    MetricHistory,
    RechartDataPoint,
    ParseError,
    OkResult,
    ErrResult,
    Result,
    RawPactData,
    ConfidentPhaseDetection,
    AmbiguousPhaseDetection,
    PhaseDetectionResult,
    PactPhaseChangeEvent,
    PactHealthUpdateEvent,
    ExpansionState,
    HealthMetrics,
    PipelineState,

    # Functions
    parse_pact_directory,
    validate_raw_pact_data,
    detect_current_phase,
    build_pipeline_state,
    parse_component_tree,
    validate_tree_depth,
    compute_output_planning_ratio,
    compute_rejection_rate,
    compute_budget_velocity,
    compute_phase_balance,
    detect_cascades,
    compute_all_health_metrics,
    transform_to_recharts,
    transform_multi_metric_to_recharts,
    validate_metric_range,
    create_expansion_state,
    toggle_node_expansion,
    emit_phase_change_event,
    emit_health_update_event,
    watch_pact_directory,
    cleanup_watcher,
)
