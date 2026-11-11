"""Tools for documenting and comparing observed business-process scenarios."""

from .comparison import (
    ScenarioValidationError,
    compare_scenarios,
    validate_scenario,
)

__all__ = [
    "ScenarioValidationError",
    "compare_scenarios",
    "validate_scenario",
]
