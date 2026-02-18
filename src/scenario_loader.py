"""
Scenario loader and selector.

Loads test scenarios from YAML. Supports:
- scenarios.yaml (legacy): list of scenarios with patient_context
- scenarios/<name>.yaml (new): individual files with description, goal, context
"""

import os
from pathlib import Path
from typing import Any

import yaml

from src.utils import get_project_root, log


def _build_behavior_from_stages(patient_context: dict[str, Any]) -> str:
    """
    Convert rich response_stages, anti_repetition, question_priority into
    a single behavior string for the LLM system prompt.
    """
    parts: list[str] = []

    if anti := patient_context.get("anti_repetition"):
        parts.append("ANTI-REPETITION RULES:\n" + "\n".join(f"- {r}" for r in anti))

    if qp := patient_context.get("question_priority"):
        parts.append("\nQUESTION-PRIORITY BEHAVIOR:\n" + "\n".join(f"- {r}" for r in qp))

    if stages := patient_context.get("response_stages"):
        parts.append("\nRESPONSE STAGES (match agent's last message and respond accordingly):")
        for key, stage in stages.items():
            if isinstance(stage, dict):
                trigger = stage.get("trigger", "")
                examples = stage.get("examples", [])
                parts.append(f"\n{key}:")
                parts.append(f"  Trigger: {trigger}")
                if examples:
                    parts.append("  Examples: " + " | ".join(f'"{e}"' for e in examples))

    if tone := patient_context.get("tone"):
        parts.append("\nTONE:\n" + "\n".join(f"- {t}" for t in tone))

    return "\n".join(parts) if parts else ""


def _normalize_scenario_from_file(data: dict[str, Any], name: str) -> dict[str, Any]:
    """
    Convert simple format (description, goal, context) or rich format
    (patient_context with response_stages) to full scenario format
    expected by ConversationManager.
    """
    if "patient_context" in data:
        pc = data["patient_context"].copy()
        # Build behavior from rich structure if present
        if "response_stages" in pc or "anti_repetition" in pc:
            behavior_from_stages = _build_behavior_from_stages(pc)
            existing_behavior = pc.get("behavior", "")
            pc["behavior"] = (existing_behavior + "\n\n" + behavior_from_stages).strip()
        # Merge top-level system_prompt_addendum into behavior (Bar-Raiser format)
        if addendum := data.get("system_prompt_addendum"):
            existing = pc.get("behavior", "")
            pc["behavior"] = (existing + "\n\n" + addendum.strip()).strip()
        # Use scenario goal if patient_context lacks it
        if "goal" not in pc and "goal" in data:
            pc["goal"] = data["goal"]
        data = {**data, "patient_context": pc}
        return {**data, "name": data.get("name", name)}
    goal = data.get("goal", "Help the caller.")
    context = data.get("context", "")
    test_type = "edge_case" if name.startswith("edge_") else "standard"
    patient_context = {
        "name": "Lucas",
        "dob": "02/17/2026",
        "phone": "",
        "goal": goal,
        "background": context,
    }
    if test_type == "edge_case":
        patient_context["behavior"] = context
    return {
        "name": name,
        "description": data.get("description", ""),
        "test_type": test_type,
        "patient_context": patient_context,
    }


def load_scenario(scenario_name: str) -> dict[str, Any]:
    """
    Load a single scenario from file.

    Tries scenarios/<scenario_name>.yaml first, then falls back to scenarios.yaml.

    Args:
        scenario_name: Scenario name (without .yaml extension).

    Returns:
        Scenario dict in format expected by ConversationManager.

    Raises:
        FileNotFoundError: If scenario not found.
    """
    root = get_project_root()
    scenario_path = Path(root) / "scenarios" / f"{scenario_name}.yaml"
    if scenario_path.exists():
        with open(scenario_path, "r") as f:
            data = yaml.safe_load(f) or {}
        return _normalize_scenario_from_file(data, scenario_name)
    try:
        scenarios = load_scenarios()
    except FileNotFoundError:
        raise FileNotFoundError(f"Scenario not found: {scenario_name}")
    for s in scenarios:
        if s.get("name") == scenario_name:
            return s
    raise FileNotFoundError(f"Scenario not found: {scenario_name}")


def load_scenarios(yaml_file: str | None = None) -> list[dict[str, Any]]:
    """
    Load all scenarios from YAML file.

    Args:
        yaml_file: Path to YAML file. Defaults to scenarios.yaml in project root.

    Returns:
        List of scenario dicts.

    Raises:
        FileNotFoundError: If YAML file does not exist.
    """
    if yaml_file is None:
        yaml_file = os.path.join(get_project_root(), "scenarios.yaml")

    if not os.path.exists(yaml_file):
        raise FileNotFoundError(f"Scenarios file not found: {yaml_file}")

    with open(yaml_file, "r") as f:
        data = yaml.safe_load(f)

    scenarios = data.get("scenarios", [])
    return scenarios


def get_scenario_by_name(name: str, yaml_file: str | None = None) -> dict[str, Any]:
    """
    Get specific scenario by name.

    Tries scenarios/<name>.yaml first, then scenarios.yaml.

    Args:
        name: Scenario name key.
        yaml_file: Optional path to YAML. Ignored when loading from scenarios/.

    Returns:
        Scenario dict.

    Raises:
        ValueError: If scenario name not found.
    """
    try:
        return load_scenario(name)
    except FileNotFoundError:
        raise ValueError(f"Scenario not found: {name}")


def list_scenarios(yaml_file: str | None = None) -> list[dict[str, Any]]:
    """
    Print all available scenarios and return list.

    Merges scenarios from scenarios.yaml and scenarios/*.yaml files.

    Args:
        yaml_file: Optional path to YAML. Defaults to project scenarios.yaml.

    Returns:
        List of scenario dicts.
    """
    root = get_project_root()
    scenarios_dir = Path(root) / "scenarios"
    seen_names: set[str] = set()
    scenarios: list[dict[str, Any]] = []

    # Load from scenarios.yaml
    try:
        legacy = load_scenarios(yaml_file)
        for s in legacy:
            name = s.get("name")
            if name and name not in seen_names:
                seen_names.add(name)
                scenarios.append(s)
    except FileNotFoundError:
        pass

    # Load from scenarios/*.yaml
    if scenarios_dir.is_dir():
        for path in sorted(scenarios_dir.glob("*.yaml")):
            name = path.stem
            if name not in seen_names:
                seen_names.add(name)
                try:
                    with open(path, "r") as f:
                        data = yaml.safe_load(f) or {}
                    scenarios.append(_normalize_scenario_from_file(data, name))
                except Exception as e:
                    log("WARNING", f"Could not load {path.name}", str(e))

    log("INFO", f"Loaded {len(scenarios)} scenarios. Available:")
    for scenario in scenarios:
        test_type = scenario.get("test_type", "standard")
        desc = scenario.get("description", "No description")
        print(f"         - {scenario['name']} ({test_type}): {desc}")
    return scenarios
