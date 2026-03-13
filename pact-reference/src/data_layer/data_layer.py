"""
Data Access Layer (Filesystem + SQLite)
========================================
Single gateway for all data access in OpenClaw Mission Control.
Three-tier architecture:
- Tier 1 (types): domain types, schemas, Result<T>
- Tier 2 (parsers): internal parsers separating I/O from validation
- Tier 3 (facade): public API with caching
"""

import os
import json
import sqlite3
import time
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone
import uuid
import yaml


# ============================================================
# TIER 1: Core Types and Enums
# ============================================================

class ErrorKind(Enum):
    """Finite union of error categories for all data access operations."""
    not_found = "not_found"
    malformed = "malformed"
    permission_denied = "permission_denied"
    io_error = "io_error"
    empty = "empty"


class AgentRole(Enum):
    """Roles an agent can have in the OpenClaw system."""
    architect = "architect"
    developer = "developer"
    reviewer = "reviewer"
    tester = "tester"
    orchestrator = "orchestrator"
    custom = "custom"


class AgentStatus(Enum):
    """Current operational status of an agent."""
    idle = "idle"
    working = "working"
    error = "error"
    offline = "offline"
    unknown = "unknown"


class PipelinePhase(Enum):
    """Current phase of a PACT project pipeline."""
    not_started = "not_started"
    decomposition = "decomposition"
    contracting = "contracting"
    implementation = "implementation"
    testing = "testing"
    complete = "complete"
    unknown = "unknown"


class ContractStatus(Enum):
    """Status of a single PACT contract file."""
    draft = "draft"
    approved = "approved"
    implemented = "implemented"
    tested = "tested"
    missing = "missing"


class TestResult(Enum):
    """Outcome of a test execution."""
    pass_ = "pass"
    fail = "fail"
    skip = "skip"
    error = "error"
    not_run = "not_run"


class TaskStatus(Enum):
    """Status of a user task."""
    todo = "todo"
    in_progress = "in_progress"
    blocked = "blocked"
    done = "done"
    cancelled = "cancelled"


class TaskPriority(Enum):
    """Priority level for a user task."""
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ActivityEventType(Enum):
    """Types of activity events."""
    agent_started = "agent_started"
    agent_completed = "agent_completed"
    agent_error = "agent_error"
    contract_created = "contract_created"
    contract_updated = "contract_updated"
    test_run = "test_run"
    file_changed = "file_changed"
    task_created = "task_created"
    task_updated = "task_updated"
    session_started = "session_started"
    session_ended = "session_ended"


# ============================================================
# Result Type Helpers
# ============================================================

def make_ok(value: Any) -> Dict[str, Any]:
    """Create a successful Result."""
    return {"ok": True, "value": value}


def make_err(kind: Union[ErrorKind, str], message: str = "", file_path: str = "", original_error: str = "") -> Dict[str, Any]:
    """Create an error Result."""
    if isinstance(kind, ErrorKind):
        kind = kind.value
    return {
        "ok": False,
        "error": {
            "kind": kind,
            "message": message,
            "filePath": file_path,
            "originalError": original_error,
        },
    }


# ============================================================
# In-Memory Cache
# ============================================================

_cache: Dict[str, Dict[str, Any]] = {}
_cache_stats = {"hits": 0, "misses": 0, "evictions": 0}


def _get_cache_key(namespace: str, key: str) -> str:
    """Generate cache key."""
    return f"{namespace}:{key}"


def _get_from_cache(namespace: str, key: str, ttl_ms: int = 5000) -> Optional[Any]:
    """Get value from cache if not expired."""
    cache_key = _get_cache_key(namespace, key)
    if cache_key in _cache:
        entry = _cache[cache_key]
        if time.time() * 1000 < entry["expiresAt"]:
            _cache_stats["hits"] += 1
            return entry["value"]
        else:
            # Expired
            del _cache[cache_key]
            _cache_stats["evictions"] += 1
    _cache_stats["misses"] += 1
    return None


def _set_in_cache(namespace: str, key: str, value: Any, ttl_ms: int = 5000):
    """Set value in cache with TTL."""
    cache_key = _get_cache_key(namespace, key)
    now_ms = time.time() * 1000
    _cache[cache_key] = {
        "key": cache_key,
        "value": value,
        "expiresAt": now_ms + ttl_ms,
        "createdAt": now_ms,
    }


# ============================================================
# SQLite Database
# ============================================================

_db_connection: Optional[sqlite3.Connection] = None
_db_path: Optional[str] = None


def _get_db() -> sqlite3.Connection:
    """Get the database connection."""
    if _db_connection is None:
        raise RuntimeError("Database not initialized")
    return _db_connection


# ============================================================
# TIER 2: Path Validation
# ============================================================

def validatePath(baseDir: str, relativePath: str) -> Dict[str, Any]:
    """
    Validates and resolves a file path against a base directory.
    Prevents directory traversal attacks.
    """
    try:
        # Check baseDir is absolute
        if not os.path.isabs(baseDir):
            return make_err(
                ErrorKind.permission_denied,
                "Base directory must be absolute",
                baseDir,
                "base_not_absolute"
            )

        # Resolve paths
        base_path = Path(baseDir).resolve()
        target_path = (base_path / relativePath).resolve()

        # Check if target is under base (prevents traversal)
        try:
            target_path.relative_to(base_path)
        except ValueError:
            return make_err(
                ErrorKind.not_found,
                "Path escapes base directory",
                str(target_path),
                "traversal_detected"
            )

        # Calculate relative path
        try:
            rel_path = target_path.relative_to(base_path)
        except ValueError:
            rel_path = Path(relativePath)

        return make_ok({
            "absolute": str(target_path),
            "relative": str(rel_path),
            "baseDir": str(base_path),
        })

    except Exception as e:
        return make_err(
            ErrorKind.io_error,
            str(e),
            baseDir,
            str(e)
        )


# ============================================================
# TIER 2: Filesystem I/O
# ============================================================

def readFileRaw(filePath: str) -> Dict[str, Any]:
    """
    Reads a file's contents as a UTF-8 string using try-read-catch-ENOENT.
    """
    try:
        with open(filePath, 'r', encoding='utf-8') as f:
            content = f.read()
        return make_ok(content)
    except FileNotFoundError:
        return make_err(
            ErrorKind.not_found,
            f"File not found: {filePath}",
            filePath,
            "ENOENT"
        )
    except PermissionError:
        return make_err(
            ErrorKind.permission_denied,
            f"Permission denied: {filePath}",
            filePath,
            "EACCES"
        )
    except Exception as e:
        return make_err(
            ErrorKind.io_error,
            f"Error reading file: {str(e)}",
            filePath,
            str(e)
        )


def readDirectoryEntries(dirPath: str, filterExtension: Optional[str] = None) -> Dict[str, Any]:
    """
    Lists entries in a directory.
    Returns Result<list of str> with entry names (not full paths).
    """
    try:
        if not os.path.exists(dirPath):
            return make_err(
                ErrorKind.not_found,
                f"Directory not found: {dirPath}",
                dirPath,
                "ENOENT"
            )

        if not os.path.isdir(dirPath):
            return make_err(
                ErrorKind.malformed,
                f"Path is not a directory: {dirPath}",
                dirPath,
                "not_a_directory"
            )

        entries = os.listdir(dirPath)

        if filterExtension:
            entries = [e for e in entries if e.endswith(filterExtension)]

        return make_ok(entries)

    except PermissionError:
        return make_err(
            ErrorKind.permission_denied,
            f"Permission denied: {dirPath}",
            dirPath,
            "EACCES"
        )
    except Exception as e:
        return make_err(
            ErrorKind.io_error,
            f"Error reading directory: {str(e)}",
            dirPath,
            str(e)
        )


# ============================================================
# TIER 2: Parsers (Pure Functions)
# ============================================================

def parseOpenClawConfig(data: Any, sourceFilePath: str, baseDir: str) -> Dict[str, Any]:
    """
    Parses unknown data as OpenClaw config.
    Pure function - no I/O.
    """
    try:
        if data is None or (isinstance(data, dict) and len(data) == 0):
            return make_err(
                ErrorKind.empty,
                "Config data is empty",
                sourceFilePath,
                "empty_data"
            )

        if not isinstance(data, dict):
            return make_err(
                ErrorKind.malformed,
                "Config must be a dictionary",
                sourceFilePath,
                "malformed_data"
            )

        # Validate required fields
        required_fields = ["version", "projectName", "agents"]
        for field in required_fields:
            if field not in data:
                return make_err(
                    ErrorKind.malformed,
                    f"Missing required field: {field}",
                    sourceFilePath,
                    "malformed_data"
                )

        # Parse agents
        agents = data.get("agents", [])
        if not isinstance(agents, list):
            return make_err(
                ErrorKind.malformed,
                "agents must be a list",
                sourceFilePath,
                "malformed_data"
            )

        # Resolve agent workspace directories to absolute paths
        parsed_agents = []
        for agent in agents:
            agent_copy = agent.copy()
            if "workspaceDir" in agent_copy:
                workspace_dir = agent_copy["workspaceDir"]
                if not os.path.isabs(workspace_dir):
                    agent_copy["workspaceDir"] = os.path.join(baseDir, workspace_dir)
            parsed_agents.append(agent_copy)

        config = {
            "version": data["version"],
            "projectName": data["projectName"],
            "agents": parsed_agents,
            "baseDir": baseDir,
        }

        return make_ok(config)

    except Exception as e:
        return make_err(
            ErrorKind.malformed,
            f"Error parsing OpenClaw config: {str(e)}",
            sourceFilePath,
            str(e)
        )


def parsePactYaml(yamlContent: str, sourceFilePath: str, baseDir: str) -> Dict[str, Any]:
    """
    Parses raw YAML string as pact.yaml config.
    Pure function - no I/O.
    """
    try:
        if not yamlContent or yamlContent.strip() == "":
            return make_err(
                ErrorKind.empty,
                "YAML content is empty",
                sourceFilePath,
                "empty_content"
            )

        # Parse YAML
        try:
            data = yaml.safe_load(yamlContent)
        except yaml.YAMLError as e:
            return make_err(
                ErrorKind.malformed,
                f"Invalid YAML syntax: {str(e)}",
                sourceFilePath,
                str(e)
            )

        if not isinstance(data, dict):
            return make_err(
                ErrorKind.malformed,
                "YAML must parse to a dictionary",
                sourceFilePath,
                "schema_mismatch"
            )

        # Validate required fields
        required_fields = ["projectId", "name", "description", "createdAt"]
        for field in required_fields:
            if field not in data:
                return make_err(
                    ErrorKind.malformed,
                    f"Missing required field: {field}",
                    sourceFilePath,
                    "schema_mismatch"
                )

        config = {
            "projectId": data["projectId"],
            "name": data["name"],
            "description": data["description"],
            "createdAt": data["createdAt"],
            "rootDir": baseDir,
        }

        return make_ok(config)

    except Exception as e:
        return make_err(
            ErrorKind.malformed,
            f"Error parsing PACT YAML: {str(e)}",
            sourceFilePath,
            str(e)
        )


def parsePactContract(data: Any, sourceFilePath: str) -> Dict[str, Any]:
    """
    Parses raw JSON/YAML data as a PACT contract.
    Pure function - no I/O.
    """
    try:
        if data is None or (isinstance(data, dict) and len(data) == 0):
            return make_err(
                ErrorKind.empty,
                "Contract data is empty",
                sourceFilePath,
                "empty_data"
            )

        if not isinstance(data, dict):
            return make_err(
                ErrorKind.malformed,
                "Contract must be a dictionary",
                sourceFilePath,
                "malformed_contract"
            )

        # Validate required fields
        required_fields = ["componentId", "name", "filePath", "status", "version"]
        for field in required_fields:
            if field not in data:
                return make_err(
                    ErrorKind.malformed,
                    f"Missing required field: {field}",
                    sourceFilePath,
                    "malformed_contract"
                )

        contract = {
            "componentId": data["componentId"],
            "name": data["name"],
            "filePath": data["filePath"],
            "status": data["status"],
            "version": data["version"],
        }

        return make_ok(contract)

    except Exception as e:
        return make_err(
            ErrorKind.malformed,
            f"Error parsing contract: {str(e)}",
            sourceFilePath,
            str(e)
        )


def parseSessionCostData(data: Any, sourceFilePath: str) -> Dict[str, Any]:
    """
    Parses raw JSON data from an agent session file to extract token/cost data.
    Pure function - no I/O.
    """
    try:
        if data is None or (isinstance(data, dict) and len(data) == 0):
            return make_err(
                ErrorKind.empty,
                "Session data is empty",
                sourceFilePath,
                "empty_data"
            )

        if not isinstance(data, dict):
            return make_err(
                ErrorKind.malformed,
                "Session data must be a dictionary",
                sourceFilePath,
                "malformed_session"
            )

        # Check for required cost fields
        required_fields = ["agentId", "sessionId", "model", "inputTokens", "outputTokens",
                          "cacheReadTokens", "cacheWriteTokens", "totalTokens", "costUsd",
                          "startedAt", "endedAt"]

        for field in required_fields:
            if field not in data:
                return make_err(
                    ErrorKind.malformed,
                    f"Missing cost field: {field}",
                    sourceFilePath,
                    "missing_cost_fields"
                )

        cost_record = {
            "agentId": data["agentId"],
            "sessionId": data["sessionId"],
            "model": data["model"],
            "tokens": {
                "inputTokens": data["inputTokens"],
                "outputTokens": data["outputTokens"],
                "cacheReadTokens": data["cacheReadTokens"],
                "cacheWriteTokens": data["cacheWriteTokens"],
                "totalTokens": data["totalTokens"],
            },
            "costUsd": data["costUsd"],
            "startedAt": data["startedAt"],
            "endedAt": data["endedAt"],
            "projectId": data.get("projectId", ""),
        }

        return make_ok(cost_record)

    except Exception as e:
        return make_err(
            ErrorKind.malformed,
            f"Error parsing session cost data: {str(e)}",
            sourceFilePath,
            str(e)
        )


def parseDecompositionTree(
    fileEntries: Dict[str, Any],
    contractStatuses: Dict[str, str],
    implementedComponents: List[str],
    testedComponents: List[str]
) -> Dict[str, Any]:
    """
    Parses decomposition directory structure data into a component tree.
    Pure function - no I/O.
    """
    try:
        if not fileEntries:
            return make_err(
                ErrorKind.empty,
                "No decomposition files provided",
                "",
                "empty_decomposition"
            )

        # Build component tree
        components = []

        for file_path, content in fileEntries.items():
            try:
                if isinstance(content, str):
                    data = json.loads(content)
                else:
                    data = content

                component_id = data.get("id", "")
                status = contractStatuses.get(component_id, "missing")

                component = {
                    "id": component_id,
                    "name": data.get("name", ""),
                    "parentId": data.get("parentId", ""),
                    "children": data.get("children", []),
                    "contractStatus": status,
                    "hasImplementation": component_id in implementedComponents,
                    "hasTests": component_id in testedComponents,
                }

                components.append(component)
            except json.JSONDecodeError as e:
                return make_err(
                    ErrorKind.malformed,
                    f"Invalid JSON in decomposition file: {str(e)}",
                    file_path,
                    "malformed_decomposition"
                )

        return make_ok(components)

    except Exception as e:
        return make_err(
            ErrorKind.malformed,
            f"Error parsing decomposition tree: {str(e)}",
            "",
            str(e)
        )


# ============================================================
# TIER 2: Pure Utilities
# ============================================================

def derivePipelinePhase(
    hasDecomposition: bool,
    totalComponents: int,
    contractedCount: int,
    implementedCount: int,
    testedCount: int
) -> str:
    """
    Derives the current pipeline phase from directory existence and content counts.
    Pure function.
    """
    # Not started: no decomposition and all counts are 0
    if not hasDecomposition and totalComponents == 0:
        return PipelinePhase.not_started.value

    # Complete: all components tested (and totalComponents > 0)
    if totalComponents > 0 and testedCount == totalComponents:
        return PipelinePhase.complete.value

    # Testing: some tested but not all
    if testedCount > 0:
        return PipelinePhase.testing.value

    # Implementation: some implemented
    if implementedCount > 0:
        return PipelinePhase.implementation.value

    # Contracting: some contracts exist
    if contractedCount > 0:
        return PipelinePhase.contracting.value

    # Decomposition: has decomposition but no contracts
    if hasDecomposition:
        return PipelinePhase.decomposition.value

    return PipelinePhase.unknown.value


# ============================================================
# TIER 3: Facade Functions - OpenClaw Config
# ============================================================

def getOpenClawConfig(baseDir: str) -> Dict[str, Any]:
    """
    Reads and parses the OpenClaw configuration from openclaw.json.
    Cached with TTL.
    """
    # Check cache
    cached = _get_from_cache("openclaw_config", baseDir)
    if cached is not None:
        return make_ok(cached)

    # Read file
    config_path = os.path.join(baseDir, "openclaw.json")
    result = readFileRaw(config_path)

    if not result["ok"]:
        return result

    # Parse JSON
    try:
        data = json.loads(result["value"])
    except json.JSONDecodeError as e:
        return make_err(
            ErrorKind.malformed,
            f"Invalid JSON in openclaw.json: {str(e)}",
            config_path,
            str(e)
        )

    # Parse config
    parse_result = parseOpenClawConfig(data, config_path, baseDir)
    if not parse_result["ok"]:
        return parse_result

    # Cache and return
    config = parse_result["value"]
    _set_in_cache("openclaw_config", baseDir, config)
    return make_ok(config)


def getAgent(baseDir: str, agentId: str) -> Dict[str, Any]:
    """
    Gets a single agent definition by ID from the OpenClaw config.
    """
    if not agentId:
        return make_err(
            ErrorKind.malformed,
            "Agent ID cannot be empty",
            "",
            "empty_agent_id"
        )

    config_result = getOpenClawConfig(baseDir)
    if not config_result["ok"]:
        return config_result

    config = config_result["value"]
    agents = config.get("agents", [])

    for agent in agents:
        if agent.get("id") == agentId:
            return make_ok(agent)

    return make_err(
        ErrorKind.not_found,
        f"Agent not found: {agentId}",
        "",
        "agent_not_found"
    )


def listAgents(baseDir: str) -> Dict[str, Any]:
    """
    Lists all agent definitions from the OpenClaw config.
    """
    config_result = getOpenClawConfig(baseDir)
    if not config_result["ok"]:
        return config_result

    config = config_result["value"]
    agents = config.get("agents", [])
    return make_ok(agents)


# ============================================================
# TIER 3: Facade Functions - PACT Projects
# ============================================================

def getProject(projectDir: str) -> Dict[str, Any]:
    """
    Reads and assembles a full PACT project summary from a project directory.
    """
    # Read pact.yaml
    pact_yaml_path = os.path.join(projectDir, "pact.yaml")
    yaml_result = readFileRaw(pact_yaml_path)

    if not yaml_result["ok"]:
        return yaml_result

    # Parse pact.yaml
    config_result = parsePactYaml(yaml_result["value"], pact_yaml_path, projectDir)
    if not config_result["ok"]:
        return config_result

    config = config_result["value"]

    # Check for decomposition
    decomp_dir = os.path.join(projectDir, "decomposition")
    has_decomposition = os.path.isdir(decomp_dir)

    # Get component tree (placeholder)
    component_tree = []
    total_components = 0

    # Get contracts
    contracts_result = getProjectContracts(projectDir)
    contracts = contracts_result["value"] if contracts_result["ok"] else []
    contracted_count = len(contracts)

    # Get test results
    tests_result = getProjectTestResults(projectDir)
    test_suites = tests_result["value"] if tests_result["ok"] else []

    # Count implemented and tested components
    implemented_count = 0
    tested_count = 0

    # Derive phase
    phase = derivePipelinePhase(
        has_decomposition,
        total_components,
        contracted_count,
        implemented_count,
        tested_count
    )

    summary = {
        "config": config,
        "phase": phase,
        "componentTree": component_tree,
        "contracts": contracts,
        "testSuites": test_suites,
        "totalComponents": total_components,
        "contractedCount": contracted_count,
        "implementedCount": implemented_count,
        "testedCount": tested_count,
    }

    return make_ok(summary)


def listProjects(baseDir: str) -> Dict[str, Any]:
    """
    Discovers and summarizes all PACT projects under a base directory.
    """
    entries_result = readDirectoryEntries(baseDir)
    if not entries_result["ok"]:
        return entries_result

    entries = entries_result["value"]
    projects = []

    for entry in entries:
        entry_path = os.path.join(baseDir, entry)
        if os.path.isdir(entry_path):
            pact_yaml = os.path.join(entry_path, "pact.yaml")
            if os.path.exists(pact_yaml):
                project_result = getProject(entry_path)
                if project_result["ok"]:
                    projects.append(project_result["value"])

    return make_ok(projects)


def getProjectPipelineStatus(projectDir: str) -> Dict[str, Any]:
    """
    Returns just the pipeline phase and high-level counts for a project.
    """
    # Read pact.yaml to verify it's a valid project
    pact_yaml_path = os.path.join(projectDir, "pact.yaml")
    if not os.path.exists(pact_yaml_path):
        return make_err(
            ErrorKind.not_found,
            "pact.yaml not found",
            pact_yaml_path,
            "project_not_found"
        )

    # Check for decomposition
    decomp_dir = os.path.join(projectDir, "decomposition")
    has_decomposition = os.path.isdir(decomp_dir)

    # Get counts (simplified)
    total_components = 0
    contracted_count = 0
    implemented_count = 0
    tested_count = 0

    # Derive phase
    phase = derivePipelinePhase(
        has_decomposition,
        total_components,
        contracted_count,
        implemented_count,
        tested_count
    )

    status = {
        "phase": phase,
        "totalComponents": total_components,
        "contractedCount": contracted_count,
        "implementedCount": implemented_count,
        "testedCount": tested_count,
    }

    return make_ok(status)


def getProjectContracts(projectDir: str) -> Dict[str, Any]:
    """
    Lists all PACT contracts in a project's contracts/ directory.
    """
    contracts_dir = os.path.join(projectDir, "contracts")

    if not os.path.isdir(contracts_dir):
        return make_err(
            ErrorKind.not_found,
            "contracts directory not found",
            contracts_dir,
            "contracts_dir_not_found"
        )

    entries_result = readDirectoryEntries(contracts_dir, ".json")
    if not entries_result["ok"]:
        return entries_result

    contracts = []
    # For now, return empty list - full implementation would parse each contract file
    return make_ok(contracts)


def getProjectTestResults(projectDir: str) -> Dict[str, Any]:
    """
    Aggregates test results for all components in a project.
    """
    tests_dir = os.path.join(projectDir, "tests")

    if not os.path.isdir(tests_dir):
        return make_err(
            ErrorKind.not_found,
            "tests directory not found",
            tests_dir,
            "tests_dir_not_found"
        )

    test_suites = []
    # For now, return empty list - full implementation would parse test results
    return make_ok(test_suites)


def getProjectComponentTree(projectDir: str) -> Dict[str, Any]:
    """
    Returns the component decomposition tree for a project.
    """
    decomp_dir = os.path.join(projectDir, "decomposition")

    if not os.path.isdir(decomp_dir):
        return make_err(
            ErrorKind.not_found,
            "decomposition directory not found",
            decomp_dir,
            "decomposition_not_found"
        )

    # For now, return empty list
    component_tree = []
    return make_ok(component_tree)


# ============================================================
# TIER 3: Facade Functions - Cost & Activity
# ============================================================

def getCostRecords(
    baseDir: str,
    timeRange: Optional[Dict[str, str]] = None,
    agentId: Optional[str] = None,
    projectId: Optional[str] = None
) -> Dict[str, Any]:
    """
    Reads token/cost data from agent session files for a given time range.
    """
    # Get config to find agent workspaces
    config_result = getOpenClawConfig(baseDir)
    if not config_result["ok"]:
        return config_result

    cost_records = []
    # For now, return empty list

    if not cost_records:
        return make_err(
            ErrorKind.empty,
            "No session files found matching criteria",
            "",
            "no_sessions"
        )

    return make_ok(cost_records)


def getCostSummary(baseDir: str, timeRange: Dict[str, str]) -> Dict[str, Any]:
    """
    Aggregates cost records into a summary over a time range.
    """
    records_result = getCostRecords(baseDir, timeRange)
    if not records_result["ok"]:
        return records_result

    records = records_result["value"]

    if not records:
        return make_err(
            ErrorKind.empty,
            "No cost records found in time range",
            "",
            "no_data"
        )

    # Aggregate
    summary = {
        "totalCostUsd": 0.0,
        "totalInputTokens": 0,
        "totalOutputTokens": 0,
        "totalTokens": 0,
        "recordCount": len(records),
        "byAgent": {},
        "byModel": {},
        "periodStart": timeRange["start"],
        "periodEnd": timeRange["end"],
    }

    return make_ok(summary)


def getActivityFeed(
    baseDir: str,
    pagination: Optional[Dict[str, int]] = None,
    agentId: Optional[str] = None,
    projectId: Optional[str] = None,
    eventTypes: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Returns recent activity events from agent sessions and file changes.
    """
    events = []

    limit = pagination.get("limit", 50) if pagination else 50
    offset = pagination.get("offset", 0) if pagination else 0

    total = len(events)
    has_more = offset + limit < total

    result = {
        "items": events[offset:offset + limit],
        "total": total,
        "limit": limit,
        "offset": offset,
        "hasMore": has_more,
    }

    return make_ok(result)


# ============================================================
# TIER 3: SQLite Operations - Database Management
# ============================================================

def initDatabase(dbPath: str) -> Dict[str, Any]:
    """
    Initializes the SQLite database, runs migrations, and enables WAL mode.
    """
    global _db_connection, _db_path

    try:
        # Create connection
        conn = sqlite3.connect(dbPath)
        conn.row_factory = sqlite3.Row

        # Enable WAL mode (unless :memory:)
        if dbPath != ":memory:":
            conn.execute("PRAGMA journal_mode=WAL")

        # Create migrations table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS migrations (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                appliedAt TEXT NOT NULL
            )
        """)

        # Create tasks table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                projectId TEXT,
                assignedAgentId TEXT,
                status TEXT NOT NULL,
                priority TEXT NOT NULL,
                createdAt TEXT NOT NULL,
                updatedAt TEXT NOT NULL,
                completedAt TEXT
            )
        """)

        # Create user_preferences table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                userId TEXT PRIMARY KEY,
                theme TEXT NOT NULL,
                refreshIntervalMs INTEGER NOT NULL,
                openclawBaseDir TEXT NOT NULL,
                pactBaseDir TEXT NOT NULL
            )
        """)

        conn.commit()

        _db_connection = conn
        _db_path = dbPath

        return make_ok({"message": "Database initialized successfully"})

    except Exception as e:
        return make_err(
            ErrorKind.io_error,
            f"Failed to initialize database: {str(e)}",
            dbPath,
            str(e)
        )


def closeDatabase() -> Dict[str, Any]:
    """
    Closes the database connection gracefully.
    """
    global _db_connection, _db_path

    if _db_connection is None:
        return make_err(
            ErrorKind.io_error,
            "Database was never initialized",
            "",
            "not_initialized"
        )

    try:
        _db_connection.close()
        _db_connection = None
        _db_path = None
        return make_ok({"message": "Database closed successfully"})
    except Exception as e:
        return make_err(
            ErrorKind.io_error,
            f"Error closing database: {str(e)}",
            "",
            str(e)
        )


def getAppliedMigrations() -> Dict[str, Any]:
    """
    Returns list of applied database migrations.
    """
    try:
        db = _get_db()
        cursor = db.execute("SELECT * FROM migrations ORDER BY id ASC")
        rows = cursor.fetchall()

        migrations = [
            {
                "id": row["id"],
                "name": row["name"],
                "appliedAt": row["appliedAt"],
            }
            for row in rows
        ]

        return make_ok(migrations)
    except RuntimeError as e:
        return make_err(
            ErrorKind.io_error,
            str(e),
            "",
            "not_initialized"
        )
    except Exception as e:
        return make_err(
            ErrorKind.io_error,
            f"Error getting migrations: {str(e)}",
            "",
            str(e)
        )


# ============================================================
# TIER 3: SQLite Operations - Tasks CRUD
# ============================================================

def createTask(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Creates a new user task in SQLite.
    """
    try:
        # Validate required field
        if "title" not in input_data or not input_data["title"]:
            return make_err(
                ErrorKind.malformed,
                "Title is required",
                "",
                "validation_failed"
            )

        if len(input_data["title"]) > 500:
            return make_err(
                ErrorKind.malformed,
                "Title must be 500 characters or less",
                "",
                "validation_failed"
            )

        db = _get_db()

        # Generate UUID
        task_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Extract fields with defaults
        title = input_data["title"]
        description = input_data.get("description", "")
        project_id = input_data.get("projectId", "")
        assigned_agent_id = input_data.get("assignedAgentId", "")
        priority = input_data.get("priority", "medium")
        status = "todo"

        # Insert task
        db.execute("""
            INSERT INTO tasks (id, title, description, projectId, assignedAgentId,
                             status, priority, createdAt, updatedAt, completedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (task_id, title, description, project_id, assigned_agent_id,
              status, priority, now, now, ""))

        db.commit()

        task = {
            "id": task_id,
            "title": title,
            "description": description,
            "projectId": project_id,
            "assignedAgentId": assigned_agent_id,
            "status": status,
            "priority": priority,
            "createdAt": now,
            "updatedAt": now,
            "completedAt": "",
        }

        return make_ok(task)

    except RuntimeError as e:
        return make_err(
            ErrorKind.io_error,
            str(e),
            "",
            "db_error"
        )
    except Exception as e:
        return make_err(
            ErrorKind.io_error,
            f"Error creating task: {str(e)}",
            "",
            str(e)
        )


def getTask(taskId: str) -> Dict[str, Any]:
    """
    Retrieves a single task by ID.
    """
    if not taskId:
        return make_err(
            ErrorKind.malformed,
            "Task ID cannot be empty",
            "",
            "empty_task_id"
        )

    try:
        db = _get_db()
        cursor = db.execute("SELECT * FROM tasks WHERE id = ?", (taskId,))
        row = cursor.fetchone()

        if not row:
            return make_err(
                ErrorKind.not_found,
                f"Task not found: {taskId}",
                "",
                "task_not_found"
            )

        task = {
            "id": row["id"],
            "title": row["title"],
            "description": row["description"] or "",
            "projectId": row["projectId"] or "",
            "assignedAgentId": row["assignedAgentId"] or "",
            "status": row["status"],
            "priority": row["priority"],
            "createdAt": row["createdAt"],
            "updatedAt": row["updatedAt"],
            "completedAt": row["completedAt"] or "",
        }

        return make_ok(task)

    except RuntimeError as e:
        return make_err(
            ErrorKind.io_error,
            str(e),
            "",
            "db_error"
        )
    except Exception as e:
        return make_err(
            ErrorKind.io_error,
            f"Error getting task: {str(e)}",
            "",
            str(e)
        )


def listTasks(
    pagination: Optional[Dict[str, int]] = None,
    projectId: Optional[str] = None,
    assignedAgentId: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None
) -> Dict[str, Any]:
    """
    Lists tasks with optional filters and pagination.
    """
    try:
        # Validate filters
        valid_statuses = ["todo", "in_progress", "blocked", "done", "cancelled"]
        valid_priorities = ["low", "medium", "high", "critical"]

        if status and status not in valid_statuses:
            return make_err(
                ErrorKind.malformed,
                f"Invalid status filter: {status}",
                "",
                "invalid_filter"
            )

        if priority and priority not in valid_priorities:
            return make_err(
                ErrorKind.malformed,
                f"Invalid priority filter: {priority}",
                "",
                "invalid_filter"
            )

        db = _get_db()

        # Build query
        query = "SELECT * FROM tasks WHERE 1=1"
        params = []

        if projectId:
            query += " AND projectId = ?"
            params.append(projectId)

        if assignedAgentId:
            query += " AND assignedAgentId = ?"
            params.append(assignedAgentId)

        if status:
            query += " AND status = ?"
            params.append(status)

        if priority:
            query += " AND priority = ?"
            params.append(priority)

        query += " ORDER BY createdAt DESC"

        # Get total count
        count_query = query.replace("SELECT *", "SELECT COUNT(*)")
        cursor = db.execute(count_query, params)
        total = cursor.fetchone()[0]

        # Apply pagination
        limit = pagination.get("limit", 50) if pagination else 50
        offset = pagination.get("offset", 0) if pagination else 0

        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = db.execute(query, params)
        rows = cursor.fetchall()

        tasks = [
            {
                "id": row["id"],
                "title": row["title"],
                "description": row["description"] or "",
                "projectId": row["projectId"] or "",
                "assignedAgentId": row["assignedAgentId"] or "",
                "status": row["status"],
                "priority": row["priority"],
                "createdAt": row["createdAt"],
                "updatedAt": row["updatedAt"],
                "completedAt": row["completedAt"] or "",
            }
            for row in rows
        ]

        result = {
            "items": tasks,
            "total": total,
            "limit": limit,
            "offset": offset,
            "hasMore": offset + limit < total,
        }

        return make_ok(result)

    except RuntimeError as e:
        return make_err(
            ErrorKind.io_error,
            str(e),
            "",
            "db_error"
        )
    except Exception as e:
        return make_err(
            ErrorKind.io_error,
            f"Error listing tasks: {str(e)}",
            "",
            str(e)
        )


def updateTask(taskId: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Updates an existing task.
    """
    if not taskId:
        return make_err(
            ErrorKind.malformed,
            "Task ID cannot be empty",
            "",
            "empty_task_id"
        )

    try:
        # Get existing task
        task_result = getTask(taskId)
        if not task_result["ok"]:
            return task_result

        task = task_result["value"]
        db = _get_db()

        # Update fields
        if "title" in input_data:
            if len(input_data["title"]) > 500:
                return make_err(
                    ErrorKind.malformed,
                    "Title must be 500 characters or less",
                    "",
                    "validation_failed"
                )
            task["title"] = input_data["title"]

        if "description" in input_data:
            task["description"] = input_data["description"]

        if "projectId" in input_data:
            task["projectId"] = input_data["projectId"]

        if "assignedAgentId" in input_data:
            task["assignedAgentId"] = input_data["assignedAgentId"]

        if "priority" in input_data:
            task["priority"] = input_data["priority"]

        # Handle status changes
        old_status = task["status"]
        if "status" in input_data:
            task["status"] = input_data["status"]

            # Set completedAt when status changes to done
            if task["status"] == "done" and old_status != "done":
                task["completedAt"] = datetime.now(timezone.utc).isoformat()

            # Clear completedAt when status changes from done to something else
            if old_status == "done" and task["status"] != "done":
                task["completedAt"] = ""

        task["updatedAt"] = datetime.now(timezone.utc).isoformat()

        # Update in database
        db.execute("""
            UPDATE tasks
            SET title = ?, description = ?, projectId = ?, assignedAgentId = ?,
                status = ?, priority = ?, updatedAt = ?, completedAt = ?
            WHERE id = ?
        """, (task["title"], task["description"], task["projectId"],
              task["assignedAgentId"], task["status"], task["priority"],
              task["updatedAt"], task["completedAt"], taskId))

        db.commit()

        return make_ok(task)

    except RuntimeError as e:
        return make_err(
            ErrorKind.io_error,
            str(e),
            "",
            "db_error"
        )
    except Exception as e:
        return make_err(
            ErrorKind.io_error,
            f"Error updating task: {str(e)}",
            "",
            str(e)
        )


def deleteTask(taskId: str) -> Dict[str, Any]:
    """
    Deletes a task by ID.
    """
    if not taskId:
        return make_err(
            ErrorKind.malformed,
            "Task ID cannot be empty",
            "",
            "empty_task_id"
        )

    try:
        # Get task before deleting
        task_result = getTask(taskId)
        if not task_result["ok"]:
            return task_result

        task = task_result["value"]

        db = _get_db()
        db.execute("DELETE FROM tasks WHERE id = ?", (taskId,))
        db.commit()

        return make_ok(task)

    except RuntimeError as e:
        return make_err(
            ErrorKind.io_error,
            str(e),
            "",
            "db_error"
        )
    except Exception as e:
        return make_err(
            ErrorKind.io_error,
            f"Error deleting task: {str(e)}",
            "",
            str(e)
        )


# ============================================================
# TIER 3: SQLite Operations - User Preferences
# ============================================================

def getUserPreferences(userId: str = "default") -> Dict[str, Any]:
    """
    Gets user preferences, creating default if not exists.
    """
    try:
        db = _get_db()
        cursor = db.execute("SELECT * FROM user_preferences WHERE userId = ?", (userId,))
        row = cursor.fetchone()

        if not row:
            # Create defaults
            defaults = {
                "userId": userId,
                "theme": "dark",
                "refreshIntervalMs": 5000,
                "openclawBaseDir": "/data/.openclaw",
                "pactBaseDir": "/data/.openclaw/projects",
            }

            db.execute("""
                INSERT INTO user_preferences (userId, theme, refreshIntervalMs,
                                             openclawBaseDir, pactBaseDir)
                VALUES (?, ?, ?, ?, ?)
            """, (userId, defaults["theme"], defaults["refreshIntervalMs"],
                  defaults["openclawBaseDir"], defaults["pactBaseDir"]))
            db.commit()

            return make_ok(defaults)

        prefs = {
            "userId": row["userId"],
            "theme": row["theme"],
            "refreshIntervalMs": row["refreshIntervalMs"],
            "openclawBaseDir": row["openclawBaseDir"],
            "pactBaseDir": row["pactBaseDir"],
        }

        return make_ok(prefs)

    except RuntimeError as e:
        return make_err(
            ErrorKind.io_error,
            str(e),
            "",
            "db_error"
        )
    except Exception as e:
        return make_err(
            ErrorKind.io_error,
            f"Error getting preferences: {str(e)}",
            "",
            str(e)
        )


def updateUserPreferences(userId: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Updates user preferences.
    """
    if not userId:
        return make_err(
            ErrorKind.malformed,
            "User ID cannot be empty",
            "",
            "empty_user_id"
        )

    try:
        # Get existing preferences
        prefs_result = getUserPreferences(userId)
        if not prefs_result["ok"]:
            return prefs_result

        prefs = prefs_result["value"]

        # Validate and merge updates
        if "theme" in updates:
            prefs["theme"] = updates["theme"]

        if "refreshIntervalMs" in updates:
            interval = updates["refreshIntervalMs"]
            if not isinstance(interval, int) or interval < 1000 or interval > 60000:
                return make_err(
                    ErrorKind.malformed,
                    "refreshIntervalMs must be between 1000 and 60000",
                    "",
                    "validation_failed"
                )
            prefs["refreshIntervalMs"] = interval

        if "openclawBaseDir" in updates:
            prefs["openclawBaseDir"] = updates["openclawBaseDir"]

        if "pactBaseDir" in updates:
            prefs["pactBaseDir"] = updates["pactBaseDir"]

        # Update in database
        db = _get_db()
        db.execute("""
            UPDATE user_preferences
            SET theme = ?, refreshIntervalMs = ?, openclawBaseDir = ?, pactBaseDir = ?
            WHERE userId = ?
        """, (prefs["theme"], prefs["refreshIntervalMs"], prefs["openclawBaseDir"],
              prefs["pactBaseDir"], userId))
        db.commit()

        return make_ok(prefs)

    except RuntimeError as e:
        return make_err(
            ErrorKind.io_error,
            str(e),
            "",
            "db_error"
        )
    except Exception as e:
        return make_err(
            ErrorKind.io_error,
            f"Error updating preferences: {str(e)}",
            "",
            str(e)
        )


# ============================================================
# TIER 3: Cache Operations
# ============================================================

def invalidateCache(key: Optional[str] = None, prefix: Optional[str] = None) -> int:
    """
    Invalidates cache entries.
    """
    global _cache

    if key:
        # Invalidate specific key
        if key in _cache:
            del _cache[key]
            _cache_stats["evictions"] += 1
            return 1
        return 0

    elif prefix:
        # Invalidate by prefix
        keys_to_remove = [k for k in _cache.keys() if k.startswith(prefix)]
        for k in keys_to_remove:
            del _cache[k]
        _cache_stats["evictions"] += len(keys_to_remove)
        return len(keys_to_remove)

    else:
        # Clear all
        count = len(_cache)
        _cache.clear()
        _cache_stats["evictions"] += count
        return count


def getCacheStats() -> Dict[str, Any]:
    """
    Returns current cache statistics.
    """
    return {
        "size": len(_cache),
        "hits": _cache_stats["hits"],
        "misses": _cache_stats["misses"],
        "evictions": _cache_stats["evictions"],
    }


# ── Auto-injected export aliases (Pact export gate) ──
Result = TestResult
PactContract = parsePactContract
CostRecord = getCostRecords
CostSummary = getCostSummary
CreateTaskInput = createTask
UpdateTaskInput = updateTask
CacheStats = _cache_stats
ActivityEvent = ActivityEventType
