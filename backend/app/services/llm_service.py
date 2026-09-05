
import logging
import asyncio
from typing import Any
from openai import OpenAI
from app.core.config import settings
from app.utils.json_extract import JSONExtractionError, extract_json_from_text

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self):
        if not settings.GROQ_API_KEY:
            logger.warning(
                "GROQ_API_KEY is not set. LLM features will fail. "
                "Set GROQ_API_KEY in your .env file."
            )
        self.client = OpenAI(
            api_key=settings.GROQ_API_KEY or "NOT_SET",
            base_url=settings.GROQ_BASE_URL,
        )

    async def call_llm(
        self,
        prompt: str,
        system_prompt: str = "You are an AI learning intelligence assistant. Respond in strict JSON.",
        expect_json: bool = True
    ) -> Any:
        if not settings.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not configured for the LLM service.")

        input_value = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
        logger.info("Calling Groq Responses API with model %s", settings.GROQ_MODEL)
        try:
            response = await asyncio.to_thread(
                self.client.responses.create,
                model=settings.GROQ_MODEL,
                input=input_value,
            )
        except Exception as error:
            logger.error("Groq API request failure model=%s error_type=%s", settings.GROQ_MODEL, type(error).__name__)
            raise

        try:
            content = (response.output_text or "").strip()
        except Exception as error:
            logger.error("LLM response extraction failure model=%s error_type=%s", settings.GROQ_MODEL, type(error).__name__)
            raise ValueError("Groq Responses API returned an unreadable response.") from error

        if not content:
            logger.error("LLM response extraction failure model=%s reason=empty_output", settings.GROQ_MODEL)
            raise ValueError("Groq Responses API returned empty output.")
        if not expect_json:
            return content

        try:
            return extract_json_from_text(content, expected_type=dict)
        except JSONExtractionError as error:
            logger.error(
                "JSON parsing failure model=%s error_type=%s line=%s column=%s position=%s excerpt=%r",
                settings.GROQ_MODEL,
                type(error.original_error).__name__ if error.original_error else type(error).__name__,
                error.line,
                error.column,
                error.position,
                error.excerpt,
            )
            raise


llm_service = LLMService()

