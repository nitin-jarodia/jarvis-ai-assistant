"""Tool calling helpers for Jarvis AI Assistant."""

from __future__ import annotations

import ast
import logging
import operator
import re
from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend import models

logger = logging.getLogger(__name__)


@dataclass
class ToolContext:
    db: Session | None = None
    user_id: int | None = None


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., str]
    needs_context: bool = False


_SAFE_OPERATORS: dict[type[ast.AST], Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_SAFE_UNARY_OPERATORS: dict[type[ast.AST], Callable[[Any], Any]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _safe_eval(node: ast.AST) -> float | int:
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Num):  # pragma: no cover - py<3.8 compatibility shim
        return node.n
    if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPERATORS:
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        return _SAFE_OPERATORS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_UNARY_OPERATORS:
        return _SAFE_UNARY_OPERATORS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("Unsupported expression")


def calculate(expression: str) -> str:
    """Safely evaluate a basic arithmetic expression."""
    try:
        normalized = expression.strip()
        if not normalized:
            return "Invalid calculation"
        tree = ast.parse(normalized, mode="eval")
        value = _safe_eval(tree)
        return str(value)
    except Exception:
        return "Invalid calculation"


def summarize_text(text: str) -> str:
    """Generate a deterministic short summary without another LLM call."""
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return "Nothing to summarize."
    if len(normalized) <= 220:
        return normalized

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", normalized) if s.strip()]
    summary_parts: list[str] = []
    current_length = 0
    for sentence in sentences[:6]:
        addition = ("" if not summary_parts else " ") + sentence
        if current_length + len(addition) > 220:
            break
        summary_parts.append(sentence)
        current_length += len(addition)

    if not summary_parts:
        clipped = normalized[:217].rstrip(" ,;:")
        return f"{clipped}..."
    summary = " ".join(summary_parts)
    if len(summary) < len(normalized):
        return f"{summary.rstrip(' ,;:')}..."
    return summary


def search_notes(query: str, *, db: Session | None = None, user_id: int | None = None) -> str:
    """Search stored notes and return a compact result summary."""
    normalized = re.sub(r"\s+", " ", query).strip()
    if not normalized:
        return "Please provide a note search query."
    if db is None:
        return f"Results for '{normalized}': note search is unavailable right now."

    like_query = f"%{normalized}%"
    matches = (
        db.query(models.Note)
        .filter(
            or_(
                models.Note.title.ilike(like_query),
                models.Note.content.ilike(like_query),
            )
        )
        .order_by(models.Note.created_at.desc())
        .limit(5)
        .all()
    )

    if not matches:
        return f"No notes found for '{normalized}'."

    lines = [f"Results for '{normalized}':"]
    for note in matches:
        snippet = re.sub(r"\s+", " ", note.content).strip()
        if len(snippet) > 90:
            snippet = f"{snippet[:87].rstrip()}..."
        lines.append(f"- {note.title}: {snippet}")
    return "\n".join(lines)


TOOLS: dict[str, ToolSpec] = {
    "calculate": ToolSpec(
        name="calculate",
        description="Perform mathematical calculations from an arithmetic expression.",
        parameters={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Arithmetic expression to evaluate, e.g. '(234 * 567) / 3'.",
                }
            },
            "required": ["expression"],
        },
        handler=calculate,
    ),
    "summarize_text": ToolSpec(
        name="summarize_text",
        description="Create a concise summary of a longer block of text.",
        parameters={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The text content that should be summarized.",
                }
            },
            "required": ["text"],
        },
        handler=summarize_text,
    ),
    "search_notes": ToolSpec(
        name="search_notes",
        description="Search saved notes for relevant content and return matching snippets.",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search phrase to look up in saved notes.",
                }
            },
            "required": ["query"],
        },
        handler=search_notes,
        needs_context=True,
    ),
}


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": spec.name,
            "description": spec.description,
            "parameters": spec.parameters,
        },
    }
    for spec in TOOLS.values()
]


def execute_tool(name: str, arguments: dict[str, Any], context: ToolContext) -> str:
    """Safely execute a registered tool and normalize failures."""
    spec = TOOLS.get(name)
    if spec is None:
        return f"Tool '{name}' is not available."

    try:
        logger.info("Executing tool | name=%s | arguments=%s", name, arguments)
        if spec.needs_context:
            return spec.handler(**arguments, db=context.db, user_id=context.user_id)
        return spec.handler(**arguments)
    except TypeError:
        return f"Tool '{name}' received invalid arguments."
    except Exception:
        return f"Tool '{name}' failed while running."
