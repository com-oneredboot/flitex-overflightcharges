"""Summary Review Service for multi-persona AI analysis via local Ollama model.

Sends aggregated wizard data to a local Ollama instance for multi-persona
AI analysis. Uses a light RAG approach: data is chunked per-FIR and per-invoice,
and only relevant chunks are included in each persona's prompt.

When Ollama is unavailable, returns a graceful fallback with risk_score=0
and a recommendation for manual review.

Validates Requirements: 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 6.3
"""

import json
import logging
from typing import Any

import httpx

from src.schemas.summary_review import AIReviewResult, Finding, MultiPersonaResult

logger = logging.getLogger(__name__)

# Ollama defaults — model name is intentionally configurable.
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"
CONNECT_TIMEOUT_S = 30
READ_TIMEOUT_S = 120


class SummaryReviewService:
    """Multi-persona AI analysis service via local Ollama model.

    Uses a light RAG approach: chunks data per-FIR and per-invoice,
    selects relevant chunks per persona, and builds focused prompts.

    Validates Requirements: 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 6.3
    """

    def __init__(
        self,
        ollama_url: str = DEFAULT_OLLAMA_URL,
        model: str = DEFAULT_MODEL,
    ) -> None:
        """Initialize the service with Ollama connection parameters.

        Args:
            ollama_url: Base URL for the Ollama API (e.g., http://localhost:11434)
            model: Name of the Ollama model to use (e.g., llama3.2)
        """
        self.ollama_url = ollama_url
        self.model = model

    def _chunk_data(
        self,
        summary: dict,
        comparison: list[dict],
    ) -> dict[str, list[dict]]:
        """Break summary and comparison data into focused chunks.

        Creates chunks organized by type:
        - flight_plan: Single chunk with flight plan metadata
        - route_costs: Per-FIR planned cost chunks
        - flown_data: Flown route data chunk
        - invoices: Per-invoice chunks
        - comparisons: Per-FIR comparison chunks (planned vs invoiced)
        - totals: Summary totals chunk

        Args:
            summary: The aggregated summary from wizard steps 1-4.
            comparison: The per-FIR charge comparison data.

        Returns:
            Dict mapping chunk type to list of chunk dicts.
        """
        chunks: dict[str, list[dict]] = {
            "flight_plan": [],
            "route_costs": [],
            "flown_data": [],
            "invoices": [],
            "comparisons": [],
            "totals": [],
        }

        # Flight plan chunk
        flight_plan = summary.get("flightPlan", {})
        if flight_plan:
            chunks["flight_plan"].append({
                "type": "flight_plan",
                "data": flight_plan,
            })

        # Route cost result - chunk per FIR
        route_cost = summary.get("routeCostResult", {})
        if route_cost:
            # Totals chunk
            chunks["totals"].append({
                "type": "planned_totals",
                "total_charge": route_cost.get("total_charge"),
                "total_distance_nm": route_cost.get("total_distance_nm"),
                "currency": route_cost.get("currency"),
                "fir_count": len(route_cost.get("fir_charges", [])),
            })

            # Per-FIR chunks
            for fir in route_cost.get("fir_charges", []):
                chunks["route_costs"].append({
                    "type": "planned_fir",
                    "fir_code": fir.get("fir_code"),
                    "country_code": fir.get("country_code"),
                    "distance_nm": fir.get("distance_nm"),
                    "charge": fir.get("charge"),
                    "currency": fir.get("currency"),
                })

        # Flown data chunk
        flown = summary.get("flownData", {})
        if flown:
            chunks["flown_data"].append({
                "type": "flown_data",
                "data": flown,
            })

        # Invoice chunks - one per invoice
        invoices = summary.get("invoices", [])
        for inv in invoices:
            chunks["invoices"].append({
                "type": "invoice",
                "invoice_number": inv.get("invoice_number"),
                "vendor": inv.get("vendor"),
                "total_amount": inv.get("total_amount"),
                "currency": inv.get("currency"),
                "fir_code": inv.get("fir_code"),
                "invoice_date": inv.get("invoice_date"),
            })

        # Comparison chunks - one per FIR comparison
        for comp in comparison:
            chunks["comparisons"].append({
                "type": "fir_comparison",
                "fir_code": comp.get("fir_code"),
                "planned_charge": comp.get("planned_charge"),
                "invoiced_charge": comp.get("invoiced_charge"),
                "variance": comp.get("variance"),
                "variance_pct": comp.get("variance_pct"),
                "status": comp.get("status"),
            })

        return chunks

    def _select_relevant_chunks(
        self,
        chunks: dict[str, list[dict]],
        persona: str,
    ) -> dict[str, list[dict]]:
        """Select chunks relevant to a specific persona.

        Each persona focuses on different aspects:
        - overflight_charges_analyst: comparisons, route_costs, invoices
        - cost_control_analyst: totals, invoices, comparisons (variance focus)
        - compliance_officer: flight_plan, flown_data, invoices, totals

        Args:
            chunks: All available chunks from _chunk_data.
            persona: The persona identifier.

        Returns:
            Filtered chunks relevant to the persona.
        """
        if persona == "overflight_charges_analyst":
            # Focus on FIR-level discrepancies
            return {
                "comparisons": chunks.get("comparisons", []),
                "route_costs": chunks.get("route_costs", []),
                "invoices": chunks.get("invoices", []),
            }
        elif persona == "cost_control_analyst":
            # Focus on budget/cost analysis
            return {
                "totals": chunks.get("totals", []),
                "invoices": chunks.get("invoices", []),
                "comparisons": [
                    c for c in chunks.get("comparisons", [])
                    if c.get("variance_pct") and abs(float(c.get("variance_pct", 0))) > 2
                ],  # Only significant variances
            }
        elif persona == "compliance_officer":
            # Focus on documentation completeness
            return {
                "flight_plan": chunks.get("flight_plan", []),
                "flown_data": chunks.get("flown_data", []),
                "totals": chunks.get("totals", []),
                "invoices": chunks.get("invoices", []),
            }
        else:
            # Unknown persona - return all
            return chunks

    async def _call_ollama(self, prompt: str) -> str | None:
        """Make a single call to the Ollama API.

        Uses httpx.AsyncClient with 30s connect timeout and 120s read timeout.
        POSTs to {ollama_url}/api/generate with the prompt.

        Args:
            prompt: The prompt text to send to Ollama.

        Returns:
            The response text from Ollama, or None if unreachable/timeout.

        Validates Requirements: 3.5
        """
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=CONNECT_TIMEOUT_S,
                    read=READ_TIMEOUT_S,
                    write=CONNECT_TIMEOUT_S,
                    pool=CONNECT_TIMEOUT_S,
                )
            ) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                    },
                )
                response.raise_for_status()
                return response.json().get("response", "")

        except httpx.ConnectError:
            logger.info("Ollama not reachable — returning None")
            return None
        except httpx.TimeoutException:
            logger.warning("Ollama request timed out — returning None")
            return None
        except Exception:
            logger.exception("Unexpected error calling Ollama")
            return None

    def _build_persona_prompt(
        self,
        persona: str,
        relevant_chunks: dict[str, list[dict]],
        regenerate: bool = False,
    ) -> str:
        """Build a focused prompt for each AI persona using relevant chunks.

        Each persona receives only the data chunks relevant to their analysis,
        keeping prompts smaller and more focused (light RAG approach).

        Args:
            persona: The persona identifier (overflight_charges_analyst,
                     cost_control_analyst, or compliance_officer)
            relevant_chunks: Pre-filtered chunks from _select_relevant_chunks
            regenerate: If True, append directive for fresh analysis

        Returns:
            The complete prompt text for the specified persona.

        Validates Requirements: 3.4, 6.3
        """
        chunks_json = json.dumps(relevant_chunks, indent=2, default=str)

        response_format = """
Respond with a JSON object containing exactly these keys:
{
    "persona_name": "<your persona name>",
    "risk_score": <decimal between 0.0 and 1.0 where 1.0 is highest risk>,
    "findings": [
        {
            "category": "<category string>",
            "severity": "<high|medium|low>",
            "description": "<detailed description>",
            "affected_firs": ["<FIR code>", ...]
        }
    ],
    "recommendations": ["<actionable recommendation>", ...],
    "missing_information": ["<data gap description>", ...],
    "confidence_score": <decimal between 0.0 and 1.0>
}

Respond ONLY with the JSON object, no other text."""

        regenerate_directive = ""
        if regenerate:
            regenerate_directive = (
                "\n\nIMPORTANT: Provide a fresh, independent analysis. "
                "Do not repeat previous assessments."
            )

        if persona == "overflight_charges_analyst":
            return f"""You are an Overflight Charges Analyst specializing in aviation invoice verification.

Analyze the following data chunks for overcharge issues, FIR discrepancies, or invoice problems.

FOCUS:
1. Compare planned FIR charges against invoiced charges
2. Identify overcharges exceeding 5% threshold
3. Flag FIR code mismatches between planned route and invoices
4. Detect missing invoices for billed FIRs

RELEVANT DATA:
{chunks_json}
{regenerate_directive}
{response_format}"""

        elif persona == "cost_control_analyst":
            return f"""You are a Cost Control Analyst specializing in aviation expense management.

Analyze the following data chunks from a budget and cost optimization perspective.

FOCUS:
1. Budget variance between planned and invoiced totals
2. Vendor billing patterns
3. Currency exposure risks
4. Cost optimization opportunities

RELEVANT DATA:
{chunks_json}
{regenerate_directive}
{response_format}"""

        elif persona == "compliance_officer":
            return f"""You are a Compliance Officer specializing in aviation regulatory compliance.

Analyze the following data chunks from a compliance and documentation perspective.

FOCUS:
1. Documentation completeness across wizard steps
2. Audit trail gaps
3. FIR coverage (all planned FIRs have corresponding invoices)
4. Regulatory compliance concerns

RELEVANT DATA:
{chunks_json}
{regenerate_directive}
{response_format}"""

        else:
            raise ValueError(f"Unknown persona: {persona}")

    def _parse_review_result(self, persona: str, raw_text: str) -> dict[str, Any]:
        """Parse Ollama JSON response into AIReviewResult dict.

        On parse failure, returns a dict with raw_response field,
        risk_score=0, confidence_score=0, and empty findings/recommendations.

        Args:
            persona: The persona name for the result
            raw_text: The raw response text from Ollama

        Returns:
            A dict matching the AIReviewResult schema.

        Validates Requirements: 3.6, 3.9
        """
        try:
            # Try to extract JSON from the response
            stripped = raw_text.strip()

            # Handle cases where the LLM wraps JSON in markdown code fences
            if stripped.startswith("```"):
                lines = stripped.split("\n")
                json_lines = [
                    line for line in lines if not line.strip().startswith("```")
                ]
                stripped = "\n".join(json_lines).strip()

            parsed = json.loads(stripped)

            # Extract and validate risk_score
            risk_score = float(parsed.get("risk_score", 0.0))
            risk_score = max(0.0, min(1.0, risk_score))

            # Extract and validate confidence_score
            confidence_score = float(parsed.get("confidence_score", 0.0))
            confidence_score = max(0.0, min(1.0, confidence_score))

            # Parse findings
            findings = []
            for f in parsed.get("findings", []):
                severity = str(f.get("severity", "low")).lower()
                if severity not in ("high", "medium", "low"):
                    severity = "low"
                findings.append({
                    "category": str(f.get("category", "")),
                    "severity": severity,
                    "description": str(f.get("description", "")),
                    "affected_firs": list(f.get("affected_firs", [])),
                })

            # Parse recommendations and missing_information as string lists
            recommendations = [
                str(r) for r in parsed.get("recommendations", [])
            ]
            missing_information = [
                str(m) for m in parsed.get("missing_information", [])
            ]

            return {
                "persona_name": persona,
                "risk_score": risk_score,
                "findings": findings,
                "recommendations": recommendations,
                "missing_information": missing_information,
                "confidence_score": confidence_score,
                "raw_response": None,
            }

        except (json.JSONDecodeError, AttributeError, TypeError, ValueError) as e:
            logger.warning(
                "Could not parse LLM response as JSON for persona %s: %s",
                persona,
                str(e),
            )
            return {
                "persona_name": persona,
                "risk_score": 0.0,
                "findings": [],
                "recommendations": [],
                "missing_information": [],
                "confidence_score": 0.0,
                "raw_response": raw_text,
            }

    def _create_fallback_result(self, persona: str) -> dict[str, Any]:
        """Create a fallback result when Ollama is unreachable.

        Returns a result with risk_score=0, empty findings,
        recommendation for manual review, and confidence_score=0.

        Args:
            persona: The persona name for the result

        Returns:
            A dict matching the AIReviewResult schema with fallback values.

        Validates Requirements: 3.8
        """
        return {
            "persona_name": persona,
            "risk_score": 0.0,
            "findings": [],
            "recommendations": ["AI analysis unavailable — manual review required"],
            "missing_information": [],
            "confidence_score": 0.0,
            "raw_response": None,
        }

    async def generate_review(
        self,
        aggregated_summary: dict,
        charge_comparison: list[dict],
        compliance_enabled: bool,
        regenerate: bool = False,
    ) -> dict[str, Any]:
        """Execute multi-persona AI analysis using chunked data (light RAG).

        Chunks the input data, selects relevant chunks per persona,
        builds focused prompts, and calls Ollama sequentially.

        Args:
            aggregated_summary: Complete aggregated summary from wizard steps 1-4
            charge_comparison: Per-FIR charge comparison data (planned vs invoiced)
            compliance_enabled: Whether to include Compliance Officer persona
            regenerate: Whether to append fresh analysis directive to prompts

        Returns:
            A dict containing MultiPersonaResult with session metadata.

        Validates Requirements: 3.2, 3.3, 3.7
        """
        # Chunk data once, reuse per persona
        chunks = self._chunk_data(aggregated_summary, charge_comparison)

        results: dict[str, Any] = {}
        prompts: dict[str, str] = {}
        raw_responses: dict[str, str | None] = {}

        mandatory_personas = ["overflight_charges_analyst", "cost_control_analyst"]

        for persona in mandatory_personas:
            relevant = self._select_relevant_chunks(chunks, persona)
            prompt = self._build_persona_prompt(persona, relevant, regenerate)
            prompts[persona] = prompt

            raw_response = await self._call_ollama(prompt)
            raw_responses[persona] = raw_response

            if raw_response is None:
                results[persona] = self._create_fallback_result(persona)
            else:
                results[persona] = self._parse_review_result(persona, raw_response)

        compliance_result = None
        if compliance_enabled:
            persona = "compliance_officer"
            relevant = self._select_relevant_chunks(chunks, persona)
            prompt = self._build_persona_prompt(persona, relevant, regenerate)
            prompts[persona] = prompt

            raw_response = await self._call_ollama(prompt)
            raw_responses[persona] = raw_response

            if raw_response is None:
                compliance_result = self._create_fallback_result(persona)
            else:
                compliance_result = self._parse_review_result(persona, raw_response)

        return {
            "multi_persona_result": {
                "overflight_charges_analyst": results["overflight_charges_analyst"],
                "cost_control_analyst": results["cost_control_analyst"],
                "compliance_officer": compliance_result,
            },
            "prompts": prompts,
            "raw_responses": raw_responses,
        }

    def _build_chat_prompt(
        self,
        summary: dict,
        review_result: dict,
        chat_history: list[dict],
        user_message: str,
    ) -> str:
        """Build a chat prompt with full context for follow-up questions.

        Includes the aggregated summary context, the multi-persona AI
        analysis result, the full chat history in chronological order,
        and the new user message.

        Args:
            summary: The aggregated summary data from wizard steps 1-4.
            review_result: The multi-persona AI analysis result.
            chat_history: Previous chat messages in chronological order,
                each with 'role' ('user'/'assistant') and 'message' keys.
            user_message: The new user message to respond to.

        Returns:
            The complete chat prompt text.

        Validates Requirements: 7.2, 7.3, 7.4
        """
        summary_json = json.dumps(summary, indent=2, default=str)
        review_json = json.dumps(review_result, indent=2, default=str)

        prompt = (
            "You are a helpful assistant that answers follow-up questions "
            "about overflight charge analysis.\n\n"
            "You have access to the following context:\n\n"
            "AGGREGATED SUMMARY (Flight plan, route costs, flown data, and invoices):\n"
            f"{summary_json}\n\n"
            "AI ANALYSIS RESULT (Multi-persona review findings):\n"
            f"{review_json}\n\n"
        )

        if chat_history:
            prompt += "PREVIOUS CONVERSATION:\n"
            for msg in chat_history:
                role_label = "User" if msg.get("role") == "user" else "Assistant"
                prompt += f"{role_label}: {msg.get('message', '')}\n"
            prompt += "\n"

        prompt += (
            f"User: {user_message}\n\n"
            "Please provide a helpful, accurate response based on the context above. "
            "If the user asks about specific findings, recommendations, or data points, "
            "reference the relevant information from the context. Be concise but thorough."
        )

        return prompt

    async def send_chat_message(
        self,
        session_id: str,
        user_message: str,
        aggregated_summary: dict,
        multi_persona_result: dict,
        chat_history: list[dict],
    ) -> dict:
        """Send a follow-up chat message to Ollama and return the response.

        Builds a chat prompt using _build_chat_prompt with the full session
        context, calls Ollama, and returns the assistant's response. Database
        persistence is handled by the routes layer, not here.

        Args:
            session_id: The AI review session identifier.
            user_message: The user's follow-up question.
            aggregated_summary: The aggregated summary for context.
            multi_persona_result: The AI analysis result for context.
            chat_history: Previous chat messages for context.

        Returns:
            A dict with the assistant's response message and the prompt used.

        Validates Requirements: 7.2, 7.3, 7.4
        """
        prompt = self._build_chat_prompt(
            summary=aggregated_summary,
            review_result=multi_persona_result,
            chat_history=chat_history,
            user_message=user_message,
        )

        raw_response = await self._call_ollama(prompt)

        if raw_response is None:
            logger.info(
                "Ollama unreachable for chat session %s — returning fallback",
                session_id,
            )
            return {
                "role": "assistant",
                "message": (
                    "I'm sorry, the AI service is currently unavailable. "
                    "Please try again later or review the analysis results above."
                ),
                "prompt": prompt,
            }

        return {
            "role": "assistant",
            "message": raw_response,
            "prompt": prompt,
        }
