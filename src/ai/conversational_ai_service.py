"""High-level conversational AI service for parsing and response rewriting."""

import json
import re
from typing import Any, Dict, Iterable, Optional

from ai.llm_provider import BaseLLMProvider


class ConversationalAIService:
    """LLM-backed helpers for intent parsing and conversational responses."""

    ALLOWED_ACTIONS = {
        "help",
        "status",
        "ex",
        "w",
        "s",
        "note",
        "undo",
        "done",
        "finish",
        "cancel",
        "restart",
    }
    ALLOWED_FOCUSES = {
        "upper-strength",
        "lower-strength",
        "push-hypertrophy",
        "pull-hypertrophy",
        "legs-hypertrophy",
        "mobility",
    }

    def __init__(self, provider: BaseLLMProvider):
        self.provider = provider
        self._rewrite_cache: Dict[str, str] = {}

    def is_enabled(self) -> bool:
        return bool(getattr(self.provider, "enabled", False))

    def status_message(self) -> str:
        return getattr(self.provider, "status", "LLM status unavailable.")

    def parse_workout_action(
        self,
        raw: str,
        *,
        draft_active: bool,
    ) -> Optional[Dict[str, Any]]:
        """Use LLM to parse workout-loop user text into command action JSON."""
        if not self.is_enabled():
            return None

        system_prompt = (
            "You are a strict intent parser for a workout logging CLI.\n"
            "Return ONLY valid JSON (no markdown) with keys: "
            "action, payload, preview, confidence.\n"
            "Allowed actions: help,status,ex,w,s,note,undo,done,finish,cancel,restart.\n"
            "Rules:\n"
            "- Never infer finish/cancel/restart unless explicit intent words are present.\n"
            "- For exercise text, action=ex and payload.exercise_name string.\n"
            "- For set input, action=w or action=s and payload.set_data with numeric weight,reps and optional rpe.\n"
            "- Use action=note when user is clearly adding notes.\n"
            "- Keep preview concise.\n"
            "- confidence must be 0..1.\n"
        )
        user_prompt = (
            f"draft_active={draft_active}\n"
            f"user_input={raw!r}\n"
            "Now return JSON."
        )
        response_text = self.provider.complete(system_prompt, user_prompt, max_tokens=260, temperature=0.1)
        if not response_text:
            return None

        parsed = self._parse_json_response(response_text)
        if not parsed:
            return None
        return self._validate_workout_parse(parsed)

    def parse_metadata_update(
        self,
        raw: str,
        current_metadata: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Use LLM to parse metadata update text into canonical update JSON."""
        if not self.is_enabled():
            return None

        focuses = ", ".join(sorted(self.ALLOWED_FOCUSES))
        system_prompt = (
            "You parse workout session metadata updates.\n"
            "Return ONLY JSON with keys: updates, preview, confidence.\n"
            "updates may include: phase, week, focus, is_deload.\n"
            f"focus must be one of: {focuses}.\n"
            "phase format must be 'phase N' (N >= 1).\n"
            "week must be integer >= 1.\n"
            "is_deload must be boolean.\n"
            "If nothing can be parsed, return {\"updates\":{}}."
        )
        user_prompt = (
            f"current_metadata={json.dumps(current_metadata)}\n"
            f"user_input={raw!r}"
        )
        response_text = self.provider.complete(system_prompt, user_prompt, max_tokens=260, temperature=0.1)
        if not response_text:
            return None

        parsed = self._parse_json_response(response_text)
        if not parsed:
            return None
        return self._validate_metadata_parse(parsed)

    def rewrite_message(self, message: str, *, kind: str = "info") -> str:
        """Rewrite a system message into concise conversational phrasing."""
        if not self.is_enabled():
            return message

        key = f"{kind}|{message}"
        if key in self._rewrite_cache:
            return self._rewrite_cache[key]

        system_prompt = (
            "Rewrite system text for a workout assistant chat.\n"
            "Constraints:\n"
            "- Keep facts exactly the same.\n"
            "- Preserve numbers, units, command words, and file/env names.\n"
            "- Keep it concise and clear.\n"
            "- Return plain text only."
        )
        user_prompt = f"kind={kind}\ntext={message!r}"
        rewritten = self.provider.complete(system_prompt, user_prompt, max_tokens=120, temperature=0.3)
        final = rewritten.strip() if isinstance(rewritten, str) and rewritten.strip() else message
        self._rewrite_cache[key] = final
        return final

    def rewrite_question(self, question: str) -> str:
        """Rewrite a confirmation question while keeping intent unchanged."""
        if not self.is_enabled():
            return question
        return self.rewrite_message(question, kind="question")

    def summarize_lines(self, lines: Iterable[str], *, context: str) -> Optional[str]:
        """Summarize multiple context lines into one concise conversational line."""
        if not self.is_enabled():
            return None

        joined = "\n".join(line for line in lines if line)
        if not joined.strip():
            return None

        system_prompt = (
            "Summarize context for a workout logging assistant.\n"
            "Keep numeric details and units.\n"
            "Return one concise sentence."
        )
        user_prompt = f"context={context}\nlines:\n{joined}"
        text = self.provider.complete(system_prompt, user_prompt, max_tokens=120, temperature=0.2)
        if not text:
            return None
        return text.strip()

    def _parse_json_response(self, text: str) -> Optional[Dict[str, Any]]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        if not cleaned.startswith("{"):
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1 and end > start:
                cleaned = cleaned[start : end + 1]

        try:
            data = json.loads(cleaned)
        except (json.JSONDecodeError, TypeError):
            return None
        if not isinstance(data, dict):
            return None
        return data

    def _validate_workout_parse(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        action = str(data.get("action", "")).strip().lower()
        if action not in self.ALLOWED_ACTIONS:
            return None

        payload = data.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {}

        if action == "ex":
            exercise_name = str(payload.get("exercise_name", "")).strip()
            if not exercise_name:
                return None
            payload = {"exercise_name": exercise_name}

        elif action in {"w", "s"}:
            set_data = payload.get("set_data")
            if not isinstance(set_data, dict):
                return None
            try:
                weight = float(set_data.get("weight"))
                reps = int(set_data.get("reps"))
            except (TypeError, ValueError):
                return None
            normalized_set = {"weight": weight, "reps": reps}
            if set_data.get("rpe") is not None:
                try:
                    normalized_set["rpe"] = float(set_data.get("rpe"))
                except (TypeError, ValueError):
                    pass
            payload = {"set_data": normalized_set}

        elif action == "note":
            note = str(payload.get("note", "")).strip()
            if not note:
                return None
            payload = {"note": note}

        else:
            payload = {}

        preview = self._normalize_preview(
            data.get("preview"),
            fallback=f"Apply action: {action}",
        )

        confidence_raw = data.get("confidence", 0.75)
        try:
            confidence = float(confidence_raw)
        except (TypeError, ValueError):
            confidence = 0.75
        confidence = max(0.0, min(1.0, confidence))

        return {
            "action": action,
            "payload": payload,
            "preview": preview,
            "confidence": confidence,
            "source": "llm",
        }

    def _validate_metadata_parse(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        updates = data.get("updates")
        if not isinstance(updates, dict) or not updates:
            return None

        normalized: Dict[str, Any] = {}
        if "phase" in updates:
            phase_raw = str(updates.get("phase", "")).strip().lower()
            match = re.search(r"([1-9][0-9]*)", phase_raw)
            if match:
                normalized["phase"] = f"phase {int(match.group(1))}"

        if "week" in updates:
            try:
                week = int(updates.get("week"))
                if week >= 1:
                    normalized["week"] = week
            except (TypeError, ValueError):
                pass

        if "focus" in updates:
            focus_raw = str(updates.get("focus", "")).strip().lower().replace(" ", "-")
            mapped = self._normalize_focus_label(focus_raw)
            if mapped:
                normalized["focus"] = mapped

        if "is_deload" in updates:
            value = updates.get("is_deload")
            if isinstance(value, bool):
                normalized["is_deload"] = value
            elif isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in {"true", "yes", "y", "1"}:
                    normalized["is_deload"] = True
                elif lowered in {"false", "no", "n", "0"}:
                    normalized["is_deload"] = False

        if not normalized:
            return None

        preview = self._normalize_preview(
            data.get("preview"),
            fallback="Update session metadata.",
        )
        confidence_raw = data.get("confidence", 0.75)
        try:
            confidence = float(confidence_raw)
        except (TypeError, ValueError):
            confidence = 0.75
        confidence = max(0.0, min(1.0, confidence))

        return {
            "action": "meta_update",
            "payload": {"updates": normalized},
            "preview": preview,
            "confidence": confidence,
            "source": "llm",
        }

    @staticmethod
    def _normalize_preview(value: Any, fallback: str) -> str:
        """Normalize LLM preview text and guard against null/None placeholder strings."""
        if value is None:
            return fallback
        if not isinstance(value, str):
            return fallback
        text = value.strip()
        if not text:
            return fallback
        if text.lower() in {"none", "null", "n/a"}:
            return fallback
        return text

    def _normalize_focus_label(self, raw_focus: str) -> Optional[str]:
        """
        Normalize focus labels from model output.

        Accept canonical values, map common synonyms, and keep non-empty custom
        labels as kebab-case so metadata updates do not fail on new user intents.
        """
        text = (raw_focus or "").strip().lower().replace("_", "-")
        if not text:
            return None

        synonyms = {
            "yoga": "mobility",
            "stretching": "mobility",
            "recovery": "mobility",
            "rehab": "mobility",
        }
        if text in synonyms:
            return synonyms[text]

        if text in self.ALLOWED_FOCUSES:
            return text

        compact = re.sub(r"[^a-z0-9-]+", "-", text).strip("-")
        return compact or None
