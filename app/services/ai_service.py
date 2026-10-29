import asyncio
import json
import logging
import re
from datetime import date as dt_date
from typing import Any, Dict, Optional
import httpx

from app.core.config import settings
from app.schemas.api import WrittenEvaluationResponse
from app.schemas.exercise import ChoiceOption, GeneratedLesson, MultipleChoiceExercise, WrittenExercise

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _get_client(self) -> httpx.AsyncClient:
        current_loop = None
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        if (
            self.client is None
            or self.client.is_closed
            or self._loop is None
            or self._loop.is_closed()
            or self._loop != current_loop
        ):
            self.client = httpx.AsyncClient(timeout=settings.openrouter_timeout_seconds)
            self._loop = current_loop
        return self.client

    def _extract_json(self, raw_content: str) -> Dict[str, Any]:
        """Strip markdown fences or conversational preambles to parse JSON safely."""
        cleaned = raw_content.strip()
        # Remove ```json ... ``` or ``` ... ```
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if fence_match:
            cleaned = fence_match.group(1).strip()
        return json.loads(cleaned)

    async def generate_lesson(
        self, course_name: str, date: dt_date, raw_text: str
    ) -> GeneratedLesson:
        """
        Calls OpenRouter with Gemini Flash to generate theory summary and exercises.
        Retries up to openrouter_max_retries upon malformed JSON.
        """
        api_key = settings.OPENROUTER_API_KEY
        # If running in local mock/test environment without OpenRouter key
        if not api_key or api_key.startswith("your-") or api_key.startswith("placeholder"):
            logger.info("Generating realistic mock German lesson (OpenRouter API key not configured).")
            return self._generate_mock_lesson(raw_text)

        # Retrieve prompts
        lesson_prompts = settings.prompts.get("lesson_generation", {})
        system_prompt = lesson_prompts.get("system", "You are a German teacher. Output valid JSON.")
        user_template = lesson_prompts.get(
            "user_template",
            "Course: {course_name}\nDate: {date}\nRaw text:\n{raw_text}\nOutput JSON."
        )
        user_prompt = user_template.format(
            course_name=course_name,
            date=date.isoformat(),
            raw_text=raw_text,
        )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": settings.openrouter_site_url,
            "X-Title": settings.openrouter_site_name,
            "Content-Type": "application/json",
        }

        payload = {
            "model": settings.openrouter_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": settings.ai_generation_temperature,
            "max_tokens": settings.ai_generation_max_tokens,
            "response_format": {"type": "json_object"},
        }

        last_error = None
        for attempt in range(1, settings.openrouter_max_retries + 1):
            try:
                logger.info(f"Calling OpenRouter (attempt {attempt}/{settings.openrouter_max_retries}) model {settings.openrouter_model}...")
                response = await self._get_client().post(
                    f"{settings.openrouter_base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                raw_text_out = data["choices"][0]["message"]["content"]
                parsed_json = self._extract_json(raw_text_out)
                validated = GeneratedLesson.model_validate(parsed_json)
                logger.info("Successfully generated and validated lesson from OpenRouter.")
                return validated
            except Exception as e:
                logger.warning(f"Lesson generation attempt {attempt} failed: {e}")
                last_error = e

        logger.error(f"Failed to generate lesson after {settings.openrouter_max_retries} attempts: {last_error}")
        raise RuntimeError(f"OpenRouter lesson generation failed: {last_error}")

    async def evaluate_written_answer(
        self, question_prompt: str, theory_summary: Optional[str], user_answer: str
    ) -> WrittenEvaluationResponse:
        """
        Dynamically evaluates a student's written response using OpenRouter Gemini Flash.
        """
        api_key = settings.OPENROUTER_API_KEY
        if not api_key or api_key.startswith("your-") or api_key.startswith("placeholder"):
            logger.info("Generating realistic mock written evaluation (OpenRouter key not configured).")
            return self._mock_evaluate_written(user_answer)

        eval_prompts = settings.prompts.get("written_evaluation", {})
        system_prompt = eval_prompts.get(
            "system",
            "You are a German teacher evaluating a student's answer. Provide all feedback and explanations in English. Output valid JSON.",
        )
        user_template = eval_prompts.get(
            "user_template",
            "Theory: {theory_summary}\nPrompt: {question_prompt}\nAnswer: {user_answer}\nEvaluate. Output JSON with is_correct and an explanation in English.",
        )
        user_prompt = user_template.format(
            theory_summary=theory_summary or "German general grammar context.",
            question_prompt=question_prompt,
            user_answer=user_answer,
        )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": settings.openrouter_site_url,
            "X-Title": settings.openrouter_site_name,
            "Content-Type": "application/json",
        }

        payload = {
            "model": settings.openrouter_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": settings.ai_evaluation_temperature,
            "max_tokens": settings.ai_evaluation_max_tokens,
            "response_format": {"type": "json_object"},
        }

        try:
            response = await self._get_client().post(
                f"{settings.openrouter_base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            raw_text_out = data["choices"][0]["message"]["content"]
            parsed_json = self._extract_json(raw_text_out)
            return WrittenEvaluationResponse.model_validate(parsed_json)
        except Exception as e:
            logger.error(f"Error calling OpenRouter for written evaluation: {e}")
            # Fallback to local heuristic evaluation if network/API fails
            return self._mock_evaluate_written(user_answer)

    def _generate_mock_lesson(self, raw_text: str) -> GeneratedLesson:
        """Generates realistic German exercises for demonstration and testing."""
        return GeneratedLesson(
            theory_summary="In today's lesson, we examine two-way prepositions (Wechselpräpositionen): an, auf, hinter, in, neben, entlang, über, unter, vor, zwischen. Remember: Akkusativ is used for movement towards a target (Wohin? - Direction/Change of state), while Dativ is used for static location or position without directional change (Wo? - Location).",
            exercises=[
                MultipleChoiceExercise(
                    exercise_type="multiple_choice",
                    question="Wählen Sie die richtige Form: 'Ich stelle das Buch auf _____ Tisch.' (der Tisch)",
                    options=[
                        ChoiceOption(
                            text="den",
                            is_correct=True,
                            explanation="Richtig! 'Stellen' indicates an action with direction (Wohin? Akkusativ maskulin: der -> den)."
                        ),
                        ChoiceOption(
                            text="dem",
                            is_correct=False,
                            explanation="Falsch. 'Dem' ist Dativ. Dativ wird mit 'liegen' oder 'stehen' (Wo?) verwendet, aber 'stellen' verlangt Akkusativ (Wohin?)."
                        ),
                        ChoiceOption(
                            text="das",
                            is_correct=False,
                            explanation="Falsch. 'Tisch' ist maskulin (der Tisch), nicht neutral (das)."
                        ),
                        ChoiceOption(
                            text="des",
                            is_correct=False,
                            explanation="Falsch. 'Des' ist Genitiv, der hier von der Präposition 'auf' nicht verlangt wird."
                        )
                    ]
                ),
                MultipleChoiceExercise(
                    exercise_type="multiple_choice",
                    question="Wählen Sie die richtige Präposition und Form: 'Das Bild hängt _____ Wand.' (die Wand)",
                    options=[
                        ChoiceOption(
                            text="an der",
                            is_correct=True,
                            explanation="Richtig! 'Hängen' als Zustand verlangt den Dativ (Wo?). Die Wand ist feminin -> Dativ: der Wand."
                        ),
                        ChoiceOption(
                            text="an die",
                            is_correct=False,
                            explanation="Falsch. 'An die' ist Akkusativ (Wohin?). Das Bild hängt aber bereits dort (statischer Zustand -> Dativ)."
                        ),
                        ChoiceOption(
                            text="in dem",
                            is_correct=False,
                            explanation="Falsch. Ein Bild hängt an einer vertikalen Fläche (an), nicht im Inneren der Wand (in)."
                        )
                    ]
                ),
                WrittenExercise(
                    exercise_type="written",
                    question="Übersetzen Sie ins Deutsche (Akkusativ Bewegung): 'The boy runs into the garden.' (der Junge / der Garten / laufen)"
                ),
                WrittenExercise(
                    exercise_type="written",
                    question="Bilden Sie einen Satz im Perfekt: 'Er legt die Zeitung auf das Sofa.'"
                )
            ]
        )

    def _mock_evaluate_written(self, user_answer: str) -> WrittenEvaluationResponse:
        """Heuristic mock evaluator when no live AI keys are configured."""
        clean = user_answer.strip().lower()
        if "in den garten" in clean or "auf das sofa gelegt" in clean or "läuft" in clean or "rennt" in clean:
            return WrittenEvaluationResponse(
                is_correct=True,
                explanation="Great job! Your grammar and word order are completely correct. The accusative case and verb form were applied flawlessly."
            )
        elif len(clean) > 3:
            return WrittenEvaluationResponse(
                is_correct=False,
                explanation="Good attempt! However, the grammatical case or verb conjugation is not quite right. Example of a correct sentence: 'Der Junge läuft in den Garten' or 'Er hat die Zeitung auf das Sofa gelegt'."
            )
        else:
            return WrittenEvaluationResponse(
                is_correct=False,
                explanation="The answer is too short or incomplete. Please formulate a complete German sentence."
            )

ai_service = AIService()
