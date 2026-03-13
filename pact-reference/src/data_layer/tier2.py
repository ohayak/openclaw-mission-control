"""
Tier 2: Internal parsers and I/O functions
Separates I/O from validation for testability.
"""

import os
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from .core import ErrorKind, make_ok, make_err


# ============================================================
# Path Validation
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
# Filesystem I/O
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
# Parsers (Pure Functions)
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
# Pure Utilities
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
    from .core import PipelinePhase

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
