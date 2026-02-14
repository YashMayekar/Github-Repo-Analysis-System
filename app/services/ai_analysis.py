import httpx
from app.core.config import settings
from typing import Dict, Any, Optional
import json
import re
import logging

logger = logging.getLogger(__name__)


class AIAnalysisService:
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.AI_MODEL_NAME

    async def _generate_response(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                payload = {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                }
                response = await client.post(f"{self.base_url}/api/generate", json=payload)
                response.raise_for_status()
                return response.json().get("response", "").strip()
            except Exception as e:
                logger.error(f"AI Generation failed: {e}")
                return ""

    def _parse_ai_response(self, raw: str) -> Dict[str, Any]:
        """Bulletproof JSON parser with multiple fallback strategies."""
        default = {"score": 10, "is_ai": False, "summary": "Code Update", "explanation": "Auto-analyzed commit"}

        if not raw:
            return default

        # Strategy 1: Clean markdown and try direct JSON parse
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        
        # Strategy 2: Extract JSON object between { and }
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start != -1 and end > start:
            try:
                result = json.loads(cleaned[start:end])
                # Validate and clamp score
                result["score"] = max(0, min(20, int(result.get("score", 10))))
                result["is_ai"] = bool(result.get("is_ai", False))
                result["summary"] = str(result.get("summary", "Code Update"))[:50]
                result["explanation"] = str(result.get("explanation", "Auto-analyzed"))[:100]
                return result
            except (json.JSONDecodeError, ValueError):
                pass  # Fall through to Strategy 3

        # Strategy 3: Regex extraction of individual fields from raw text
        result = dict(default)
        
        score_match = re.search(r'"score"\s*:\s*(\d+)', cleaned)
        if score_match:
            result["score"] = max(0, min(20, int(score_match.group(1))))

        ai_match = re.search(r'"is_ai"\s*:\s*(true|false)', cleaned, re.IGNORECASE)
        if ai_match:
            result["is_ai"] = ai_match.group(1).lower() == "true"

        summary_match = re.search(r'"summary"\s*:\s*"([^"]*)"', cleaned)
        if summary_match:
            result["summary"] = summary_match.group(1)[:50]

        explanation_match = re.search(r'"explanation"\s*:\s*"([^"]*)"', cleaned)
        if explanation_match:
            result["explanation"] = explanation_match.group(1)[:100]

        # If we extracted at least a score, consider it a success
        if score_match:
            return result

        # Strategy 4: Look for any number that could be a score (last resort)
        numbers = re.findall(r'\b(\d{1,2})\b', cleaned)
        for n in numbers:
            val = int(n)
            if 0 <= val <= 20:
                result["score"] = val
                result["summary"] = "AI Scored"
                result["explanation"] = "Score extracted from response"
                return result

        logger.warning(f"Could not parse AI response: {raw[:200]}")
        return default

    async def analyze_commit(self, message: str, diffs: str) -> Dict[str, Any]:
        prompt = f"""
        [INST]
        You are a code analysis engine. 
        Your task is to analyze the following git commit and output raw JSON only.
        Do not include markdown formatting (```json), chat explanations, or any other text.
        I do not have access to previous history. Treat this as an isolated event.

        Commit Message: {message}
        
        Code Changes (truncated):
        {diffs[:4000]}
        
        Scoring Criteria (0-20):
        0-5: Buggy, broken logic, obvious placeholder, or nonsensical code "vibecoding".
        6-12: Standard boilerplate, config updates, minor tweaks, or simple CRUD.
        13-17: distinct logic improvement, good refactoring, clean implementation.
        18-20: Exceptional optimization, complex algorithm, highly efficient "10x" code.

        Output Fields:
        - score: (int) 0 to 20 based on criteria.
        - is_ai: (bool) true if code looks like a generic LLM dump (generic comments, repetitive).
        - summary: (string) max 10 words.
        - explanation: (string) max 20 words.
        
        Respond with ONLY this JSON, nothing else:
        {{"score": 0, "is_ai": false, "summary": "...", "explanation": "..."}}
        [/INST]
        """
        
        response = await self._generate_response(prompt)
        return self._parse_ai_response(response)

    async def generate_final_review(self, team_name: str, summaries: list[str], scores: list[int]) -> str:
        data_str = json.dumps([{"s": s, "score": sc} for s, sc in zip(summaries, scores)], indent=None)
        
        prompt = f"""
        [INST]
        Write a short performance review for Team '{team_name}'.
        Strictly no chat. Output only the review paragraph.
        
        History:
        {data_str}
        
        Criteria:
        - Avg Score < 10: "Needs Improvement"
        - Avg Score > 15: "High Performer"
        - Mention if they seem to be using AI heavily (generic summaries).
        
        Keep it under 50 words. Brutally honest.
        [/INST]
        """
        return await self._generate_response(prompt)
