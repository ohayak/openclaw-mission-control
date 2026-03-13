"""
PACT reader service — reads PACT project directories.
Reads files directly; never imports pact as a library.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from app.models import PactComponent, PactHealth, PactStatus


def get_pact_status(project_dir: str) -> PactStatus:
    """Return the PACT pipeline status for a project directory."""
    p = Path(project_dir)
    if not p.exists():
        return PactStatus(
            project_id=project_dir,
            phase="unknown",
            status="not_found",
        )

    # Read authoritative state from .pact/state.json if daemon is running
    state_path = p / ".pact" / "state.json"
    phase = "unknown"
    status = "idle"

    if state_path.exists():
        try:
            state = json.loads(state_path.read_text())
            phase = state.get("phase", "unknown")
            status = state.get("status", "idle")
        except Exception:
            pass
    else:
        # Infer phase from filesystem state
        phase = _infer_phase(p)
        status = "idle"

    # Gather component stats
    decomp_file = p / "decomposition" / "decomposition.json"
    has_decomposition = decomp_file.exists()
    components = _read_components_raw(p)
    component_count = len(components)

    contracts_dir = p / "contracts"
    has_contracts = contracts_dir.exists() and any(contracts_dir.iterdir()) if contracts_dir.exists() else False

    components_contracted = sum(1 for c in components if _component_has_contract(p, c.get("id", "")))
    components_tested = sum(1 for c in components if _component_has_tests(p, c.get("id", "")))
    components_implemented = sum(1 for c in components if _component_has_implementation(p, c.get("id", "")))

    return PactStatus(
        project_id=project_dir,
        phase=phase,
        status=status,
        has_decomposition=has_decomposition,
        has_contracts=has_contracts,
        component_count=component_count,
        components_contracted=components_contracted,
        components_tested=components_tested,
        components_implemented=components_implemented,
    )


def get_pact_components(project_dir: str) -> list[PactComponent]:
    """Return component list with contract/test/implementation status."""
    p = Path(project_dir)
    components_raw = _read_components_raw(p)
    result = []

    for raw in components_raw:
        cid = raw.get("id", "")
        has_contract = _component_has_contract(p, cid)
        has_tests = _component_has_tests(p, cid)
        has_impl = _component_has_implementation(p, cid)

        # Read test results if available
        test_passed = None
        test_failed = None
        test_total = None
        results_file = p / "tests" / cid / "results.json"
        if results_file.exists():
            try:
                results = json.loads(results_file.read_text())
                test_passed = results.get("passed")
                test_failed = results.get("failed")
                test_total = results.get("total")
            except Exception:
                pass

        result.append(PactComponent(
            id=cid,
            name=raw.get("name", cid),
            description=raw.get("description"),
            layer=raw.get("layer"),
            dependencies=raw.get("dependencies", []),
            has_contract=has_contract,
            has_tests=has_tests,
            has_implementation=has_impl,
            test_passed=test_passed,
            test_failed=test_failed,
            test_total=test_total,
        ))

    return result


def get_pact_health(project_dir: str) -> PactHealth:
    """Run `pact health .` and capture raw output."""
    try:
        result = subprocess.run(
            ["pact", "health", "."],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=15,
        )
        raw = result.stdout or result.stderr or "No health data available"
    except FileNotFoundError:
        raw = "pact CLI not found"
    except subprocess.TimeoutExpired:
        raw = "pact health timed out"
    except Exception as e:
        raw = f"Error running pact health: {e}"

    return PactHealth(project_id=project_dir, raw_output=raw)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_components_raw(project_path: Path) -> list[dict]:
    decomp_file = project_path / "decomposition" / "decomposition.json"
    if not decomp_file.exists():
        return []
    try:
        data = json.loads(decomp_file.read_text())
        # Format: {"components": [...]}
        return data.get("components", [])
    except Exception:
        return []


def _infer_phase(p: Path) -> str:
    """Infer PACT phase from filesystem state when daemon isn't running."""
    decomp_file = p / "decomposition" / "decomposition.json"
    if not decomp_file.exists():
        # Check if interview questions exist
        interview_file = p / "decomposition" / "interview.json"
        return "interview" if interview_file.exists() else "shape"

    components = _read_components_raw(p)
    if not components:
        return "decompose"

    cids = [c.get("id", "") for c in components]
    all_contracted = all(_component_has_contract(p, cid) for cid in cids if cid)
    if not all_contracted:
        return "contract"

    all_tested = all(_component_has_tests(p, cid) for cid in cids if cid)
    if not all_tested:
        return "test"

    all_implemented = all(_component_has_implementation(p, cid) for cid in cids if cid)
    if not all_implemented:
        return "implement"

    return "complete"


def _component_has_contract(p: Path, cid: str) -> bool:
    return (p / "contracts" / cid / "contract.json").exists() or \
           (p / "contracts" / cid / "contract.md").exists()


def _component_has_tests(p: Path, cid: str) -> bool:
    test_dir = p / "tests" / cid
    return test_dir.exists() and any(test_dir.iterdir())


def _component_has_implementation(p: Path, cid: str) -> bool:
    src_dir = p / "src" / cid
    return src_dir.exists() and any(src_dir.iterdir())
