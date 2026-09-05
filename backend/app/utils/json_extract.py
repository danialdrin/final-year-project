import json
import re
from typing import Any, Type


class JSONExtractionError(ValueError):
    def __init__(self, message: str, *, original_error: Exception | None = None, excerpt: str = ""):
        super().__init__(message)
        self.original_error = original_error
        self.excerpt = excerpt
        self.line = getattr(original_error, "lineno", None)
        self.column = getattr(original_error, "colno", None)
        self.position = getattr(original_error, "pos", None)


def _safe_excerpt(text: str, position: int | None, limit: int = 240) -> str:
    if position is None:
        return text[:limit]
    start = max(0, position - limit // 2)
    excerpt = text[start:start + limit]
    excerpt = re.sub(r'(?i)"[^"\n]*(?:api[_ -]?key|authorization|bearer|secret)[^"\n]*"\s*:', '"[REDACTED_FIELD]":', excerpt)
    return re.sub(r"(?i)(api[_ -]?key|authorization|bearer|secret)\s*[:=]\s*[^,\s]+", r"\1=[REDACTED]", excerpt)


def _remove_fence(text: str) -> str:
    match = re.fullmatch(r"\s*```(?:json)?\s*([\s\S]*?)\s*```\s*", text, re.IGNORECASE)
    return match.group(1).strip() if match else text.strip()


def _find_json_bounds(text: str) -> tuple[int, int]:
    starts = [index for index in (text.find("{"), text.find("[")) if index >= 0]
    if not starts:
        raise JSONExtractionError("LLM response did not contain a JSON object or array", excerpt=_safe_excerpt(text, None))

    start = min(starts)
    opener = text[start]
    closer = "}" if opener == "{" else "]"
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        character = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character == opener:
            depth += 1
        elif character == closer:
            depth -= 1
            if depth == 0:
                return start, index + 1
    raise JSONExtractionError("LLM response contained an unclosed JSON object or array", excerpt=_safe_excerpt(text, len(text)))


def extract_json_from_text(text: str, expected_type: Type[Any] | None = None) -> Any:
    cleaned = _remove_fence(text or "")
    start, end = _find_json_bounds(cleaned)
    candidate = cleaned[start:end]
    try:
        result = json.loads(candidate)
    except json.JSONDecodeError as error:
        excerpt = _safe_excerpt(candidate, error.pos)
        raise JSONExtractionError(
            f"Malformed JSON: {error.msg} (line {error.lineno}, column {error.colno}, character {error.pos})",
            original_error=error,
            excerpt=excerpt,
        ) from error

    if expected_type is not None and not isinstance(result, expected_type):
        expected_name = "object" if expected_type is dict else "array" if expected_type is list else expected_type.__name__
        raise JSONExtractionError(
            f"Expected JSON {expected_name}, received {type(result).__name__}",
            excerpt=_safe_excerpt(candidate, None),
        )
    return result
