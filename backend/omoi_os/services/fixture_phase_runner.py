"""Spec pipeline fixture mode — run phases using pre-recorded reference outputs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class PhaseResult:
    """Result of running a single phase against fixtures."""

    phase: str
    output: dict[str, Any]
    passed: bool
    score: float
    issues: list[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class PipelineResult:
    """Result of running the full fixture pipeline."""

    phases_run: list[str]
    phases_passed: list[str]
    all_passed: bool
    results: list[PhaseResult]


# Expected top-level keys for each phase fixture (basic structural validation)
PHASE_EXPECTED_KEYS = {
    "explore": ["project_type", "structure", "conventions"],
    "requirements": ["requirements"],
    "design": ["components", "architecture"],
    "tasks": ["tasks"],
}


class FixturePhaseRunner:
    """Runs spec phases using pre-recorded reference outputs instead of Claude.

    Enables testing the pipeline logic:
    1. Load fixture output for a phase
    2. Validate structure (expected keys present)
    3. Optionally run evaluator if spec_sandbox is importable
    4. Report pass/fail with score
    """

    PHASE_ORDER = ["explore", "requirements", "design", "tasks"]

    def __init__(self, fixture_dir: str):
        self._fixture_dir = Path(fixture_dir)
        self._evaluators = self._try_load_evaluators()

    def _try_load_evaluators(self) -> dict:
        """Try to import evaluators from spec_sandbox. Returns empty dict if unavailable."""
        try:
            from spec_sandbox.evaluators.phases import (
                ExploreEvaluator,
                RequirementsEvaluator,
                DesignEvaluator,
                TasksEvaluator,
            )

            return {
                "explore": ExploreEvaluator(),
                "requirements": RequirementsEvaluator(),
                "design": DesignEvaluator(),
                "tasks": TasksEvaluator(),
            }
        except ImportError:
            return {}

    def _load_fixture(self, phase: str) -> dict:
        """Load reference output for a phase."""
        fixture_path = self._fixture_dir / f"{phase}_output.json"
        if not fixture_path.exists():
            raise FileNotFoundError(
                f"No fixture found for phase '{phase}' at {fixture_path}. "
                f"Available fixtures: {[p.name for p in self._fixture_dir.glob('*_output.json')]}. "
                f"Ensure the fixture file exists and has the correct name."
            )
        return json.loads(fixture_path.read_text())

    def list_available_fixtures(self) -> list[str]:
        """List phases that have fixture files."""
        fixtures = []
        for phase in self.PHASE_ORDER:
            fixture_path = self._fixture_dir / f"{phase}_output.json"
            if fixture_path.exists():
                fixtures.append(phase)
        return fixtures

    def _validate_structure(self, phase: str, output: dict) -> tuple[float, list[str]]:
        """Basic structural validation — check expected keys exist."""
        expected = PHASE_EXPECTED_KEYS.get(phase, [])
        if not expected:
            return 1.0, []

        issues = []
        found = 0
        for key in expected:
            if key in output:
                found += 1
            else:
                issues.append(f"Missing expected key: {key}")

        score = found / len(expected) if expected else 1.0
        return score, issues

    async def run_phase(self, phase: str) -> PhaseResult:
        """Run a single phase using fixtures."""
        try:
            fixture_output = self._load_fixture(phase)
        except FileNotFoundError as e:
            return PhaseResult(
                phase=phase,
                output={},
                passed=False,
                score=0.0,
                error=str(e),
            )

        # Try evaluator first (if available)
        evaluator = self._evaluators.get(phase)
        if evaluator:
            try:
                eval_result = await evaluator.evaluate(fixture_output, context={})
                return PhaseResult(
                    phase=phase,
                    output=fixture_output,
                    passed=eval_result.passed,
                    score=eval_result.score,
                    issues=eval_result.issues if hasattr(eval_result, "issues") else [],
                )
            except Exception:
                # Fall back to structural validation
                pass

        # Structural validation fallback
        score, issues = self._validate_structure(phase, fixture_output)
        return PhaseResult(
            phase=phase,
            output=fixture_output,
            passed=score >= 0.5,
            score=score,
            issues=issues,
        )

    async def run_full_pipeline(self) -> PipelineResult:
        """Run all available phases sequentially."""
        results = []
        for phase in self.PHASE_ORDER:
            fixture_path = self._fixture_dir / f"{phase}_output.json"
            if not fixture_path.exists():
                continue
            result = await self.run_phase(phase)
            results.append(result)
            if not result.passed:
                break  # Stop at first failure

        return PipelineResult(
            phases_run=[r.phase for r in results],
            phases_passed=[r.phase for r in results if r.passed],
            all_passed=all(r.passed for r in results) if results else False,
            results=results,
        )
