# adaptive_depth.py
"""
Adaptive Depth Engine (adaptive_depth.py)
Internal technicality calibration system for Knowledge Agent.
Calibrates depth (1-10) without leaking point values into user-facing output.
"""

from __future__ import annotations
import re
from typing import List, Optional, Dict, Any


class DepthLevel:
    MIN_SCORE = 1
    MAX_SCORE = 10
    DEFAULT_BASE = 5


class AdaptiveDepthEngine:
    """Calculates internal technicality level based on vocabulary and conversational flow."""

    SIMPLIFICATION_PATTERNS = [
        r"\b(?:explain\s+(?:me\s+)?(?:this\s+)?more\s+clearly|simpler|simple\s+terms|in\s+plain\s+english)\b",
        r"\b(?:eli5|for\s+beginners?|beginner-friendly|spoon\s*feed|too\s+complex|confused|break\s+it\s+down)\b",
        r"\b(?:what\s+does\s+this\s+mean|i\s+don'?t\s+understand|basic\s+explanation)\b",
    ]

    MODERATE_TECHNICAL_PATTERNS = [
        r"\b(?:more\s+technical(?:\s+terms)?|in-depth|detailed\s+architecture|under\s+the\s+hood|internals?)\b",
        r"\b(?:data\s+flow|lifecycle|contract|interface|subsystem|middleware|pipeline)\b",
    ]

    DEEP_TECHNICAL_PATTERNS = [
        r"\b(?:http\s+endpoint|api\s+route|database\s+connection|orm|schema|sql|migration)\b",
        r"\b(?:asyncio|thread\s*pool|concurrency|mutex|deadlock|race\s+condition|ast|bytecode)\b",
        r"\b(?:fastapi|express|django|postgres|sqlite|redis|grpc|protobuf|webhook\s+payload)\b",
    ]

    def calculate_depth(self, query: Optional[str], history: Optional[List[str]] = None) -> int:
        if not query:
            return DepthLevel.DEFAULT_BASE

        score = DepthLevel.DEFAULT_BASE
        q_lower = query.lower()

        # Check simplification cues (-1 to -2)
        for pat in self.SIMPLIFICATION_PATTERNS:
            if re.search(pat, q_lower):
                score -= 1
                if "spoon feed" in q_lower or "eli5" in q_lower or "more clearly" in q_lower:
                    score -= 1
                break

        # Check moderate technical cues (+1)
        for pat in self.MODERATE_TECHNICAL_PATTERNS:
            if re.search(pat, q_lower):
                score += 1
                break

        # Check deep technical cues (+1 to +3)
        deep_matches = 0
        for pat in self.DEEP_TECHNICAL_PATTERNS:
            if re.search(pat, q_lower):
                deep_matches += 1

        if deep_matches >= 2:
            score += 3
        elif deep_matches == 1:
            score += 2

        # Check history cues if available
        if history:
            for past in history[-3:]:
                p_lower = past.lower()
                if "more technical" in p_lower:
                    score += 1
                elif "more clearly" in p_lower or "simpler" in p_lower:
                    score -= 1

        # Clamp between MIN_SCORE and MAX_SCORE
        return max(DepthLevel.MIN_SCORE, min(DepthLevel.MAX_SCORE, score))

    def get_prompt_guidance(self, depth: int) -> str:
        """Translates numerical depth to internal LLM instructions without disclosing numbers."""
        if depth <= 3:
            return (
                "ADAPTIVE EXPLANATION DEPTH: HIGH ACCESSIBILITY\n"
                "- Keep explanations conceptual, intuitive, and focused on the big picture.\n"
                "- Avoid dense jargon or raw bytecode/protocol traces.\n"
                "- Use clear analogies and walk through steps incrementally before showing code."
            )
        elif depth >= 7:
            return (
                "ADAPTIVE EXPLANATION DEPTH: DEEP TECHNICAL IMPLEMENTATION\n"
                "- Provide direct, concrete, low-level technical specifics.\n"
                "- Trace exact function signatures, HTTP routes/methods, schema fields, and execution flow.\n"
                "- Detail underlying data structures, state transitions, and error edge cases without high-level filler."
            )
        else:
            return (
                "ADAPTIVE EXPLANATION DEPTH: BALANCED ENGINEERING KT\n"
                "- Provide direct, senior-engineer level context with clear evidence links.\n"
                "- Balance architectural rationale with specific file and component references."
            )
