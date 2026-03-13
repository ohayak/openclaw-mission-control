"""Tests for the pact_reader service."""
import json
from pathlib import Path

import pytest

from app.models import PactComponent, PactStatus
from app.services.pact_reader import (
    _component_has_contract,
    _component_has_implementation,
    _component_has_tests,
    _infer_phase,
    _read_components_raw,
    get_pact_components,
    get_pact_status,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_tree_json(project_dir: Path, nodes: dict, root_id: str = "root") -> Path:
    """Write a tree.json with the given nodes."""
    decomp_dir = project_dir / "decomposition"
    decomp_dir.mkdir(parents=True, exist_ok=True)
    tree_file = decomp_dir / "tree.json"
    tree_file.write_text(json.dumps({"root_id": root_id, "nodes": nodes}))
    return tree_file


def _make_node(cid: str, name: str = None, depth: int = 1) -> dict:
    return {
        "component_id": cid,
        "name": name or cid.replace("_", " ").title(),
        "description": f"Description for {cid}",
        "depth": depth,
        "parent_id": "root",
        "children": [],
        "contract": None,
        "implementation_status": "pending",
        "test_results": None,
    }


# ---------------------------------------------------------------------------
# Tests for _read_components_raw
# ---------------------------------------------------------------------------

class TestReadComponentsRaw:
    def test_reads_tree_json_format(self, tmp_path):
        nodes = {
            "root": _make_node("root", depth=0),
            "foundation": _make_node("foundation"),
            "data_layer": _make_node("data_layer"),
        }
        _write_tree_json(tmp_path, nodes)

        components = _read_components_raw(tmp_path)
        # root node should be excluded
        cids = [c["component_id"] for c in components]
        assert "foundation" in cids
        assert "data_layer" in cids
        assert "root" not in cids

    def test_reads_fixture_tree_json(self, tmp_path):
        """Test with the real tree.json fixture."""
        import shutil
        decomp_dir = tmp_path / "decomposition"
        decomp_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(FIXTURES / "tree.json", decomp_dir / "tree.json")

        components = _read_components_raw(tmp_path)
        assert len(components) > 0
        # Each component should have the expected keys
        for c in components:
            assert "component_id" in c
            assert "name" in c

    def test_excludes_root_node(self, tmp_path):
        nodes = {
            "root": _make_node("root", depth=0),
            "alpha": _make_node("alpha"),
        }
        _write_tree_json(tmp_path, nodes, root_id="root")
        components = _read_components_raw(tmp_path)
        cids = [c["component_id"] for c in components]
        assert "root" not in cids
        assert "alpha" in cids

    def test_falls_back_to_decomposition_json(self, tmp_path):
        """When tree.json doesn't exist, fall back to decomposition.json."""
        decomp_dir = tmp_path / "decomposition"
        decomp_dir.mkdir()
        legacy_data = {
            "components": [
                {"id": "comp1", "name": "Component 1"},
                {"id": "comp2", "name": "Component 2"},
            ]
        }
        (decomp_dir / "decomposition.json").write_text(json.dumps(legacy_data))

        components = _read_components_raw(tmp_path)
        assert len(components) == 2
        assert components[0]["id"] == "comp1"

    def test_missing_both_files_returns_empty(self, tmp_path):
        components = _read_components_raw(tmp_path)
        assert components == []

    def test_malformed_tree_json_returns_empty(self, tmp_path):
        decomp_dir = tmp_path / "decomposition"
        decomp_dir.mkdir()
        (decomp_dir / "tree.json").write_text("not valid json {{{")
        components = _read_components_raw(tmp_path)
        assert components == []


# ---------------------------------------------------------------------------
# Tests for get_pact_status
# ---------------------------------------------------------------------------

class TestGetPactStatus:
    def test_missing_directory_returns_not_found(self):
        status = get_pact_status("/nonexistent/path/xyz123")
        assert status.status == "not_found"
        assert status.phase == "unknown"

    def test_returns_pact_status_object(self, tmp_path):
        status = get_pact_status(str(tmp_path))
        assert isinstance(status, PactStatus)
        assert status.project_id == str(tmp_path)

    def test_detects_components_from_tree_json(self, tmp_path):
        nodes = {
            "root": _make_node("root", depth=0),
            "comp_a": _make_node("comp_a"),
            "comp_b": _make_node("comp_b"),
        }
        _write_tree_json(tmp_path, nodes)

        status = get_pact_status(str(tmp_path))
        assert status.component_count == 2
        assert status.has_decomposition is True

    def test_counts_contracted_components(self, tmp_path):
        nodes = {
            "root": _make_node("root", depth=0),
            "comp_a": _make_node("comp_a"),
            "comp_b": _make_node("comp_b"),
        }
        _write_tree_json(tmp_path, nodes)

        # Add interface.json for comp_a only
        contract_dir = tmp_path / "contracts" / "comp_a"
        contract_dir.mkdir(parents=True)
        (contract_dir / "interface.json").write_text('{"version": 1}')

        status = get_pact_status(str(tmp_path))
        assert status.components_contracted == 1

    def test_counts_implemented_components(self, tmp_path):
        nodes = {
            "root": _make_node("root", depth=0),
            "comp_a": _make_node("comp_a"),
        }
        _write_tree_json(tmp_path, nodes)

        src_dir = tmp_path / "src" / "comp_a"
        src_dir.mkdir(parents=True)
        (src_dir / "main.py").write_text("# implementation")

        status = get_pact_status(str(tmp_path))
        assert status.components_implemented == 1

    def test_uses_state_json_when_present(self, tmp_path):
        pact_dir = tmp_path / ".pact"
        pact_dir.mkdir()
        state_data = {"phase": "contract", "status": "running"}
        (pact_dir / "state.json").write_text(json.dumps(state_data))

        status = get_pact_status(str(tmp_path))
        assert status.phase == "contract"
        assert status.status == "running"


# ---------------------------------------------------------------------------
# Tests for get_pact_components
# ---------------------------------------------------------------------------

class TestGetPactComponents:
    def test_returns_component_list(self, tmp_path):
        nodes = {
            "root": _make_node("root", depth=0),
            "foundation": _make_node("foundation"),
            "data_layer": _make_node("data_layer"),
        }
        _write_tree_json(tmp_path, nodes)

        components = get_pact_components(str(tmp_path))
        assert len(components) == 2
        assert all(isinstance(c, PactComponent) for c in components)

    def test_component_fields_from_tree_json(self, tmp_path):
        nodes = {
            "root": _make_node("root", depth=0),
            "foundation": {
                "component_id": "foundation",
                "name": "Foundation & Infrastructure",
                "description": "Core scaffolding",
                "depth": 1,
                "parent_id": "root",
                "children": [],
                "contract": None,
                "implementation_status": "pending",
                "test_results": None,
            },
        }
        _write_tree_json(tmp_path, nodes)

        components = get_pact_components(str(tmp_path))
        assert len(components) == 1
        c = components[0]
        assert c.id == "foundation"
        assert c.name == "Foundation & Infrastructure"
        assert c.description == "Core scaffolding"

    def test_has_contract_false_when_missing(self, tmp_path):
        nodes = {"root": _make_node("root", depth=0), "comp_x": _make_node("comp_x")}
        _write_tree_json(tmp_path, nodes)

        components = get_pact_components(str(tmp_path))
        assert components[0].has_contract is False

    def test_has_contract_true_with_interface_json(self, tmp_path):
        nodes = {"root": _make_node("root", depth=0), "comp_x": _make_node("comp_x")}
        _write_tree_json(tmp_path, nodes)

        contract_dir = tmp_path / "contracts" / "comp_x"
        contract_dir.mkdir(parents=True)
        (contract_dir / "interface.json").write_text('{"version": 1}')

        components = get_pact_components(str(tmp_path))
        assert components[0].has_contract is True

    def test_has_contract_true_with_interface_py(self, tmp_path):
        nodes = {"root": _make_node("root", depth=0), "comp_x": _make_node("comp_x")}
        _write_tree_json(tmp_path, nodes)

        contract_dir = tmp_path / "contracts" / "comp_x"
        contract_dir.mkdir(parents=True)
        (contract_dir / "interface.py").write_text("# contract")

        components = get_pact_components(str(tmp_path))
        assert components[0].has_contract is True

    def test_empty_project_returns_empty_list(self, tmp_path):
        components = get_pact_components(str(tmp_path))
        assert components == []

    def test_uses_real_fixture_tree_json(self, tmp_path):
        """Integration test with the real fixture tree.json."""
        import shutil
        decomp_dir = tmp_path / "decomposition"
        decomp_dir.mkdir()
        shutil.copy(FIXTURES / "tree.json", decomp_dir / "tree.json")

        components = get_pact_components(str(tmp_path))
        assert len(components) > 0
        # All have ids and names
        for c in components:
            assert c.id
            assert c.name


# ---------------------------------------------------------------------------
# Tests for _infer_phase
# ---------------------------------------------------------------------------

class TestInferPhase:
    def test_no_decomposition_no_interview_returns_shape(self, tmp_path):
        phase = _infer_phase(tmp_path)
        assert phase == "shape"

    def test_interview_json_present_returns_interview(self, tmp_path):
        decomp_dir = tmp_path / "decomposition"
        decomp_dir.mkdir()
        (decomp_dir / "interview.json").write_text("[]")
        phase = _infer_phase(tmp_path)
        assert phase == "interview"

    def test_tree_json_no_contracts_returns_contract(self, tmp_path):
        nodes = {"root": _make_node("root", depth=0), "comp_a": _make_node("comp_a")}
        _write_tree_json(tmp_path, nodes)
        phase = _infer_phase(tmp_path)
        assert phase == "contract"

    def test_all_contracted_no_tests_returns_test(self, tmp_path):
        nodes = {"root": _make_node("root", depth=0), "comp_a": _make_node("comp_a")}
        _write_tree_json(tmp_path, nodes)

        contract_dir = tmp_path / "contracts" / "comp_a"
        contract_dir.mkdir(parents=True)
        (contract_dir / "interface.json").write_text("{}")

        phase = _infer_phase(tmp_path)
        assert phase == "test"

    def test_all_contracted_all_tested_no_impl_returns_implement(self, tmp_path):
        nodes = {"root": _make_node("root", depth=0), "comp_a": _make_node("comp_a")}
        _write_tree_json(tmp_path, nodes)

        contract_dir = tmp_path / "contracts" / "comp_a"
        contract_dir.mkdir(parents=True)
        (contract_dir / "interface.json").write_text("{}")

        test_dir = tmp_path / "tests" / "comp_a"
        test_dir.mkdir(parents=True)
        (test_dir / "test_comp_a.py").write_text("# tests")

        phase = _infer_phase(tmp_path)
        assert phase == "implement"

    def test_fully_implemented_returns_complete(self, tmp_path):
        nodes = {"root": _make_node("root", depth=0), "comp_a": _make_node("comp_a")}
        _write_tree_json(tmp_path, nodes)

        (tmp_path / "contracts" / "comp_a").mkdir(parents=True)
        (tmp_path / "contracts" / "comp_a" / "interface.json").write_text("{}")

        (tmp_path / "tests" / "comp_a").mkdir(parents=True)
        (tmp_path / "tests" / "comp_a" / "test_comp_a.py").write_text("# tests")

        (tmp_path / "src" / "comp_a").mkdir(parents=True)
        (tmp_path / "src" / "comp_a" / "main.py").write_text("# impl")

        phase = _infer_phase(tmp_path)
        assert phase == "complete"


# ---------------------------------------------------------------------------
# Tests for _component_has_contract
# ---------------------------------------------------------------------------

class TestComponentHasContract:
    def test_no_contract_dir_returns_false(self, tmp_path):
        assert _component_has_contract(tmp_path, "comp_a") is False

    def test_empty_contract_dir_returns_false(self, tmp_path):
        (tmp_path / "contracts" / "comp_a").mkdir(parents=True)
        assert _component_has_contract(tmp_path, "comp_a") is False

    def test_interface_json_returns_true(self, tmp_path):
        contract_dir = tmp_path / "contracts" / "comp_a"
        contract_dir.mkdir(parents=True)
        (contract_dir / "interface.json").write_text("{}")
        assert _component_has_contract(tmp_path, "comp_a") is True

    def test_interface_py_returns_true(self, tmp_path):
        contract_dir = tmp_path / "contracts" / "comp_a"
        contract_dir.mkdir(parents=True)
        (contract_dir / "interface.py").write_text("# contract")
        assert _component_has_contract(tmp_path, "comp_a") is True

    def test_old_contract_json_returns_false(self, tmp_path):
        """contract.json is the old format — should NOT be recognized."""
        contract_dir = tmp_path / "contracts" / "comp_a"
        contract_dir.mkdir(parents=True)
        (contract_dir / "contract.json").write_text("{}")
        assert _component_has_contract(tmp_path, "comp_a") is False

    def test_old_contract_md_returns_false(self, tmp_path):
        """contract.md is the old format — should NOT be recognized."""
        contract_dir = tmp_path / "contracts" / "comp_a"
        contract_dir.mkdir(parents=True)
        (contract_dir / "contract.md").write_text("# contract")
        assert _component_has_contract(tmp_path, "comp_a") is False


# ---------------------------------------------------------------------------
# Graceful handling tests
# ---------------------------------------------------------------------------

class TestGracefulHandling:
    def test_get_pact_status_with_missing_dir(self):
        status = get_pact_status("/tmp/this_dir_does_not_exist_12345")
        assert status.status == "not_found"

    def test_get_pact_components_with_missing_dir(self):
        # Should not raise
        components = get_pact_components("/tmp/this_dir_does_not_exist_12345")
        assert components == []

    def test_read_components_raw_with_empty_tree(self, tmp_path):
        decomp_dir = tmp_path / "decomposition"
        decomp_dir.mkdir()
        # tree.json with empty nodes
        (decomp_dir / "tree.json").write_text(json.dumps({"root_id": "root", "nodes": {}}))
        components = _read_components_raw(tmp_path)
        assert components == []
