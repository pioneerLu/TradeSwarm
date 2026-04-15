# -*- coding: utf-8 -*-
"""Append-only LLM prompt/response capture for audit runs (LangChain callbacks)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, List
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage


def _msg_line(m: BaseMessage) -> str:
    role = getattr(m, "type", None) or m.__class__.__name__
    content = getattr(m, "content", "")
    if not isinstance(content, str):
        content = str(content)
    return f"### {role}\n{content}\n"


class PromptScratchpadHandler(BaseCallbackHandler):
    """Writes each chat model call (input messages + raw response text) to a UTF-8 file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._n = 0
        self.path.write_text(
            "# LLM scratchpad (chronological)\n\n"
            "Each block: prompts/messages as sent to the model, then model response.\n"
            "String-style `llm.invoke(prompt)` is logged under `(llm_start)`; chat messages under chat_model.\n"
            "When using `run_signal_export --prompt-log`, see also `analyst_context_trace.jsonl` in the same folder "
            "for every `get_prompt_context_from_summaries` call (full `enabled_analysts_text` + `active_analyst_blocks`).\n\n",
            encoding="utf-8",
        )

    def _append(self, text: str) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(text)

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> Any:
        if not prompts:
            return
        self._n += 1
        name = (serialized or {}).get("name") or (serialized or {}).get("id") or "llm"
        lines = [f"\n{'=' * 80}\n## Call {self._n} — (llm_start) {name} — run_id={run_id}\n\n"]
        for i, p in enumerate(prompts):
            lines.append(f"### prompt[{i}]\n{p}\n")
        self._append("".join(lines))

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: List[List[BaseMessage]],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> Any:
        self._n += 1
        name = (serialized or {}).get("name") or (serialized or {}).get("id") or "chat_model"
        lines = [f"\n{'=' * 80}\n## Call {self._n} — (chat_model) {name} — run_id={run_id}\n\n"]
        for batch in messages:
            for m in batch:
                if isinstance(m, BaseMessage):
                    lines.append(_msg_line(m))
                else:
                    lines.append(f"### (non-message)\n{m!r}\n")
        self._append("".join(lines))

    def on_llm_end(self, response: Any, **kwargs: Any) -> Any:
        self._append("\n## Response\n")
        try:
            gens = getattr(response, "generations", None)
            if gens:
                for gen_list in gens:
                    for g in gen_list:
                        text = getattr(g, "text", None)
                        if text is not None:
                            self._append(text + "\n")
                        else:
                            self._append(repr(g) + "\n")
            else:
                self._append(repr(response) + "\n")
        except Exception as exc:  # noqa: BLE001
            self._append(f"(could not format response: {exc})\n{response!r}\n")
        self._append("\n")
