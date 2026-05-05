from __future__ import annotations

from typing import Any, Dict, Optional

from tradingagents.agents.utils.json_parser import extract_json_from_text
from tradingagents.agents.utils.prompt_loader import render_pre_open_template

VALID_REGIMES = {"strong_uptrend", "range_bound", "downtrend", "high_vol_uncertain"}
VALID_SKILLS = {f"{regime}_skill" for regime in VALID_REGIMES}

SKILL_BY_REGIME = {regime: f"{regime}_skill" for regime in VALID_REGIMES}
REGIME_BY_SKILL = {skill: regime for regime, skill in SKILL_BY_REGIME.items()}
TEMPLATE_BY_SKILL = {
    "strong_uptrend_skill": "strategy_skills/strong_uptrend_skill.j2",
    "range_bound_skill": "strategy_skills/range_bound_skill.j2",
    "downtrend_skill": "strategy_skills/downtrend_skill.j2",
    "high_vol_uncertain_skill": "strategy_skills/high_vol_uncertain_skill.j2",
}


def normalize_regime(value: Any) -> Optional[str]:
    regime = str(value or "").strip().lower()
    return regime if regime in VALID_REGIMES else None


def normalize_skill(value: Any, regime: Optional[str] = None) -> Optional[str]:
    skill = str(value or "").strip().lower()
    if skill in VALID_SKILLS:
        return skill
    if regime in VALID_REGIMES:
        return SKILL_BY_REGIME[regime]
    return None


def normalize_confidence(value: Any) -> Optional[float]:
    try:
        confidence = float(value)
    except Exception:
        return None
    return max(0.0, min(1.0, confidence))


def normalize_evidence(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()][:5]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def parse_reflection_response(content: str) -> Dict[str, Any]:
    try:
        payload = extract_json_from_text(content)
    except Exception:
        payload = {}
    payload = payload if isinstance(payload, dict) else {}

    regime = normalize_regime(payload.get("market_regime"))
    skill = normalize_skill(payload.get("selected_skill"), regime)
    if regime is None and skill:
        regime = REGIME_BY_SKILL.get(skill)
    if skill is None and regime:
        skill = SKILL_BY_REGIME.get(regime)

    valid = regime is not None and skill is not None
    return {
        "valid": valid,
        "market_regime": regime,
        "selected_skill": skill,
        "regime_confidence": normalize_confidence(payload.get("regime_confidence")),
        "regime_evidence": normalize_evidence(payload.get("regime_evidence")),
        "raw_response": content,
    }


def render_strategy_skill_rules(
    *,
    mode: str,
    fallback_mode: str,
    selected_skill: Optional[str] = None,
) -> Dict[str, Any]:
    mode = str(mode or "reflect").strip().lower()
    fallback_mode = str(fallback_mode or "off").strip().lower()
    selected_skill = normalize_skill(selected_skill)

    effective_mode = mode
    included_templates: list[str] = []
    rules_text = ""

    if mode == "off":
        return {
            "effective_mode": "off",
            "strategy_skill_rules_text": "",
            "included_skill_template": None,
            "included_skill_templates": [],
        }

    if mode == "all":
        included_templates = list(TEMPLATE_BY_SKILL.values())
    elif mode == "reflect" and selected_skill:
        included_templates = [TEMPLATE_BY_SKILL[selected_skill]]
    else:
        effective_mode = fallback_mode if fallback_mode in {"all", "off"} else "off"
        if effective_mode == "all":
            included_templates = list(TEMPLATE_BY_SKILL.values())

    if included_templates:
        rules_text = "\n\n".join(render_pre_open_template(path) for path in included_templates)

    return {
        "effective_mode": effective_mode,
        "strategy_skill_rules_text": rules_text,
        "included_skill_template": included_templates[0] if len(included_templates) == 1 else None,
        "included_skill_templates": included_templates,
    }
