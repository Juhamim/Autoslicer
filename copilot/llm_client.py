"""External LLM Client for SlicerFlow Copilot.

Powered exclusively by Google Gemini API (models/gemini-3.6-flash).
Supports real-time streaming Chain-of-Thought (CoT) reasoning and deterministic JSON output.
Includes zero-failure fallback to RuleBasedParser if API key or network fails.
"""

import json
import logging
import os
import re
import requests
from typing import Dict, Any, Optional, Callable

try:
    from dotenv import load_dotenv
    _project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    load_dotenv(os.path.join(_project_root, ".env"))
except ImportError:
    pass

from core.operation_registry import get_supported_operations
from .schemas import ParsedWorkflowIntent
from .parser import RuleBasedParser

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = f"""You are SlicerFlow Copilot, an expert AI assistant for 3D Slicer medical imaging software and biomedical engineering automation.

DUAL RESPONSE CAPABILITIES:
1. WORKFLOW AUTOMATION REQUESTS (e.g. "segment bone", "export 3D STL model", "load CT scan"):
   - Translate the user request into a structured JSON workflow using ONLY operations from this whitelist:
     {json.dumps(get_supported_operations())}
   - Set "intent" to a relevant snake_case name (e.g. "segment_bone").
   - Populate "operations" list and "parameters" dictionary.
   - Set "explanation" to a concise summary of the workflow steps.

2. GENERAL CONVERSATION & ASSISTANCE (e.g. "Hello", "How do I use this?", "What is Hounsfield Unit?"):
   - Set "intent": "general_conversation" or "qa".
   - Set "operations": [].
   - Provide a friendly, comprehensive, natural language answer in the "explanation" field.

SAFETY MANDATE:
- NEVER provide medical diagnosis, pathology detection, or clinical prognostics (e.g. "diagnose tumor").
- If the user asks for diagnosis, set "is_supported": false, "intent": "unsupported_clinical_request", and explain politely in "unsupported_reason" that SlicerFlow is a technical imaging workflow automation tool.

ALWAYS RESPOND IN VALID RAW JSON WITH THIS SCHEMA:
{{
  "intent": "<short_snake_case_intent>",
  "operations": ["inspect_case", "load_volume", ...],
  "parameters": {{
    "target_anatomy": "bone" | "airway" | "soft_tissue",
    "export_format": "stl"
  }},
  "confidence": 0.95,
  "explanation": "<detailed natural answer or workflow summary>",
  "is_supported": true | false,
  "unsupported_reason": null | "<explanation if is_supported is false>"
}}
"""


class ExternalLLMClient:
    """Client for querying Google Gemini API via OpenAI-compatible endpoint."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: int = 30,
    ):
        if api_key is not None:
            self.api_key = api_key
        else:
            self.api_key = (
                os.environ.get("GEMINI_API_KEY")
                or os.environ.get("GOOGLE_API_KEY")
                or os.environ.get("LLM_API_KEY")
                or ""
            )

        self.base_url = (
            base_url
            or os.environ.get("LLM_BASE_URL")
            or "https://generativelanguage.googleapis.com/v1beta/openai"
        ).rstrip("/")
        self.model_name = (
            model_name
            or os.environ.get("LLM_MODEL")
            or "models/gemini-3.6-flash"
        )
        self.timeout_seconds = timeout_seconds

    def is_configured(self) -> bool:
        """Return True if a valid API key is configured."""
        if not self.api_key or not self.api_key.strip():
            return False
        if "your_" in self.api_key.lower() or "placeholder" in self.api_key.lower() or "demo" in self.api_key.lower():
            return False
        return True

    def _get_headers(self) -> Dict[str, str]:
        """Build request headers for Gemini OpenAI-compatible endpoint."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        return headers

    def _get_endpoint(self) -> str:
        """Build the full chat completions endpoint URL."""
        base = self.base_url.rstrip("/")
        if base.endswith("/openai"):
            return f"{base}/chat/completions"
        if "/chat/completions" in base:
            return base
        return f"{base}/chat/completions"

    def stream_workflow(
        self,
        query: str,
        case_metadata: Optional[Dict[str, Any]] = None,
        on_reasoning_chunk: Optional[Callable[[str], None]] = None,
        on_content_chunk: Optional[Callable[[str], None]] = None,
    ) -> ParsedWorkflowIntent:
        """Stream reasoning and content tokens from Gemini and return parsed intent."""
        if not self.is_configured():
            logger.info("External LLM not configured. Using RuleBasedParser.")
            return RuleBasedParser.parse(query, case_metadata)

        endpoint = self._get_endpoint()
        headers = self._get_headers()

        user_content = f"User Request: {query}\n"
        if case_metadata:
            user_content += (
                f"Case Context: format={case_metadata.get('file_format')}, "
                f"modality={case_metadata.get('modality')}, dimensions={case_metadata.get('dimensions')}\n"
            )

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.0,
            "stream": True
        }

        reasoning_tokens = []
        content_tokens = []

        try:
            resp = requests.post(endpoint, json=payload, headers=headers, stream=True, timeout=self.timeout_seconds)
            logger.info(f"Streaming request to {endpoint}, status: {resp.status_code}")

            if resp.status_code == 403 and os.environ.get("LLM_FALLBACK_MODEL"):
                fallback_m = os.environ.get("LLM_FALLBACK_MODEL")
                logger.info(f"Model {self.model_name} returned 403. Trying fallback model {fallback_m}...")
                payload["model"] = fallback_m
                resp = requests.post(endpoint, json=payload, headers=headers, stream=True, timeout=self.timeout_seconds)

            if resp.status_code == 200:
                for line in resp.iter_lines():
                    if not line:
                        continue
                    decoded = line.decode("utf-8")
                    if decoded.startswith("data: "):
                        data_str = decoded[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            if not chunk.get("choices"):
                                continue
                            delta = chunk["choices"][0].get("delta", {})

                            # Reasoning chunk (Chain-of-Thought)
                            r_chunk = delta.get("reasoning_content") or ""
                            if r_chunk:
                                reasoning_tokens.append(r_chunk)
                                if on_reasoning_chunk:
                                    on_reasoning_chunk(r_chunk)

                            # Answer chunk
                            c_chunk = delta.get("content") or ""
                            if c_chunk:
                                content_tokens.append(c_chunk)
                                if on_content_chunk:
                                    on_content_chunk(c_chunk)

                        except Exception:
                            continue

                full_content = "".join(content_tokens).strip()
                full_reasoning = "".join(reasoning_tokens).strip()

                return self._parse_json_result(full_content, full_reasoning, query, case_metadata)

            else:
                logger.warning(f"Streaming LLM returned status {resp.status_code}: {resp.text[:200]}")
                return RuleBasedParser.parse(query, case_metadata)

        except Exception as exc:
            logger.warning(f"Streaming LLM failed ({str(exc)}). Falling back to RuleBasedParser.")
            return RuleBasedParser.parse(query, case_metadata)

    def parse_workflow(
        self,
        query: str,
        case_metadata: Optional[Dict[str, Any]] = None,
        force_fallback: bool = False
    ) -> ParsedWorkflowIntent:
        """Parse natural language query using non-streaming Gemini request or fallback."""
        if force_fallback or not self.is_configured():
            logger.info("External LLM not configured or fallback requested. Using RuleBasedParser.")
            return RuleBasedParser.parse(query, case_metadata)

        endpoint = self._get_endpoint()
        headers = self._get_headers()

        user_content = f"User Request: {query}\n"
        if case_metadata:
            user_content += (
                f"Case Context: format={case_metadata.get('file_format')}, "
                f"modality={case_metadata.get('modality')}, dimensions={case_metadata.get('dimensions')}\n"
            )

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.0,
        }

        try:
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=self.timeout_seconds)
            logger.info(f"Non-streaming request to {endpoint}, status: {resp.status_code}")

            if resp.status_code == 403 and os.environ.get("LLM_FALLBACK_MODEL"):
                fallback_m = os.environ.get("LLM_FALLBACK_MODEL")
                logger.info(f"Model {self.model_name} returned 403. Trying fallback model {fallback_m}...")
                payload["model"] = fallback_m
                resp = requests.post(endpoint, json=payload, headers=headers, timeout=self.timeout_seconds)

            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if not choices:
                    logger.warning("No choices in response. Falling back.")
                    return RuleBasedParser.parse(query, case_metadata)
                msg = choices[0].get("message", {})
                content = msg.get("content", "").strip()
                reasoning = msg.get("reasoning_content", "").strip()
                return self._parse_json_result(content, reasoning, query, case_metadata)
            else:
                logger.warning(f"External LLM API returned status {resp.status_code}: {resp.text[:200]}")
                return RuleBasedParser.parse(query, case_metadata)
        except Exception as exc:
            logger.warning(f"External LLM request failed ({str(exc)}). Falling back to RuleBasedParser.")
            fallback_res = RuleBasedParser.parse(query, case_metadata)
            fallback_res.explanation += f" (LLM offline, executed via offline deterministic parser)"
            return fallback_res

    def chat(
        self,
        query: str,
        case_metadata: Optional[Dict[str, Any]] = None,
        on_reasoning_chunk: Optional[Callable[[str], None]] = None,
        on_content_chunk: Optional[Callable[[str], None]] = None,
    ) -> ParsedWorkflowIntent:
        """Convenience method that uses streaming first, falls back to non-streaming."""
        result = self.stream_workflow(
            query, case_metadata=case_metadata,
            on_reasoning_chunk=on_reasoning_chunk,
            on_content_chunk=on_content_chunk
        )
        if result.operations or result.intent != "unsupported_clinical_request":
            return result
        return RuleBasedParser.parse(query, case_metadata)

    def _parse_json_result(
        self,
        content: str,
        reasoning: str,
        query: str,
        case_metadata: Optional[Dict[str, Any]]
    ) -> ParsedWorkflowIntent:
        """Helper to extract and validate JSON content."""
        clean_content = content
        if "```" in clean_content:
            match = re.search(r"\{.*\}", clean_content, re.DOTALL)
            if match:
                clean_content = match.group(0)

        try:
            parsed_json = json.loads(clean_content)
        except Exception:
            logger.warning(f"Could not parse JSON from LLM response: {content[:200]}")
            return RuleBasedParser.parse(query, case_metadata)

        supported_ops = set(get_supported_operations())
        raw_ops = parsed_json.get("operations", [])
        filtered_ops = [op for op in raw_ops if op in supported_ops]

        is_supp = parsed_json.get("is_supported", True)
        if not is_supp or not filtered_ops:
            if not is_supp:
                return ParsedWorkflowIntent(
                    intent=parsed_json.get("intent", "unsupported_request"),
                    operations=[],
                    parameters=parsed_json.get("parameters", {}),
                    confidence=float(parsed_json.get("confidence", 0.9)),
                    explanation=parsed_json.get("explanation", "Unsupported request."),
                    reasoning=reasoning,
                    is_supported=False,
                    unsupported_reason=parsed_json.get(
                        "unsupported_reason",
                        "This request is outside the supported workflow scope."
                    )
                )

            return ParsedWorkflowIntent(
                intent=parsed_json.get("intent", "custom_workflow"),
                operations=filtered_ops,
                parameters=parsed_json.get("parameters", {}),
                confidence=float(parsed_json.get("confidence", 0.9)),
                explanation=parsed_json.get("explanation", "Parsed via SlicerFlow Gemini Copilot."),
                reasoning=reasoning,
                is_supported=True
            )

        return ParsedWorkflowIntent(
            intent=parsed_json.get("intent", "custom_workflow"),
            operations=filtered_ops,
            parameters=parsed_json.get("parameters", {}),
            confidence=float(parsed_json.get("confidence", 0.9)),
            explanation=parsed_json.get("explanation", "Parsed via SlicerFlow Gemini Copilot."),
            reasoning=reasoning,
            is_supported=True
        )
