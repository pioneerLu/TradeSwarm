#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Prompt 模板加载工具

统一管理所有 agent 的 prompt 模板，使用 Jinja2 进行渲染。
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Optional
from jinja2 import Template, Environment, FileSystemLoader


# 模板目录路径
TEMPLATE_BASE_DIR = Path(__file__).parent.parent / "pre_open"
TEMPLATE_DIRS = {
    "researchers": TEMPLATE_BASE_DIR / "researchers",
    "risk_mgmt": TEMPLATE_BASE_DIR / "risk_mgmt",
    "trader": TEMPLATE_BASE_DIR / "trader",
    "managers": TEMPLATE_BASE_DIR / "managers",
}


def _render_template_file(template_path: Path, context: Dict[str, Any]) -> str:
    """Render a pre_open template and allow includes from the same template tree."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_BASE_DIR)),
        autoescape=False,
        trim_blocks=False,
        lstrip_blocks=False,
    )
    template_name = template_path.relative_to(TEMPLATE_BASE_DIR).as_posix()
    template = env.get_template(template_name)
    return template.render(**context)


def render_pre_open_template(relative_template_path: str, context: Optional[Dict[str, Any]] = None) -> str:
    """Render a template by path relative to the pre_open template root."""
    context = context or {}
    template_path = TEMPLATE_BASE_DIR / relative_template_path
    return _render_template_file(template_path, context)


def _get_template_path(agent_type: str, agent_name: str) -> Path:
    template_dir = TEMPLATE_DIRS.get(agent_type)
    if template_dir is None:
        raise ValueError(
            f"未知的 agent_type: {agent_type}。"
            f"可选值: {list(TEMPLATE_DIRS.keys())}"
        )

    if agent_type == "managers":
        return template_dir / agent_name / "prompt.j2"
    if agent_type == "trader":
        return template_dir / "prompt.j2"
    return template_dir / agent_name / "prompt.j2"


def load_prompt_template(
    agent_type: str,
    agent_name: str,
    context: Optional[Dict[str, Any]] = None,
    fallback_prompt: Optional[str] = None,
) -> str:
    """
    加载并渲染 prompt 模板。
    
    Args:
        agent_type: Agent 类型，可选值: "researchers", "risk_mgmt", "trader", "managers"
        agent_name: Agent 名称，例如 "bull_researcher", "aggresive_debator" 等
        context: 模板渲染上下文变量（字典）
        fallback_prompt: 如果模板文件不存在，使用的默认 prompt
        
    Returns:
        渲染后的 prompt 字符串
        
    Examples:
        >>> context = {
        ...     "enabled_analysts_text": "market, news",
        ...     "active_analyst_blocks": "[market]\\n...",
        ... }
        >>> prompt = load_prompt_template(
        ...     "researchers",
        ...     "bull_researcher",
        ...     context=context
        ... )
    """
    if context is None:
        context = {}
    
    template_path = _get_template_path(agent_type, agent_name)
    
    # 尝试加载模板文件
    if template_path.exists():
        try:
            return _render_template_file(template_path, context)
        except Exception as e:
            print(f"[WARN] 加载模板文件失败: {template_path}, 错误: {e}")
            print(f"[WARN] 使用 fallback prompt")
            if fallback_prompt:
                # 如果 fallback 也是模板字符串，尝试渲染
                try:
                    fallback_template = Template(fallback_prompt)
                    return fallback_template.render(**context)
                except Exception:
                    return fallback_prompt.format(**context) if context else fallback_prompt
            return fallback_prompt or ""
    else:
        # 模板文件不存在，使用 fallback
        if fallback_prompt:
            try:
                fallback_template = Template(fallback_prompt)
                return fallback_template.render(**context)
            except Exception:
                return fallback_prompt.format(**context) if context else fallback_prompt
        else:
            raise FileNotFoundError(
                f"模板文件不存在: {template_path}，且未提供 fallback_prompt"
            )


def get_template_path(agent_type: str, agent_name: str) -> Path:
    """
    获取模板文件路径（不加载）。
    
    Args:
        agent_type: Agent 类型
        agent_name: Agent 名称
        
    Returns:
        模板文件的 Path 对象
    """
    return _get_template_path(agent_type, agent_name)
