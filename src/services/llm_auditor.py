"""LLM Auditor for async anomaly detection via local Ollama model.

Sends calculation session summaries to a local Ollama instance for
plausibility assessment. Runs asynchronously (fire-and-forget) so that
LLM latency never blocks the API response. When Ollama is unavailable
the verdict is recorded as "skipped" with reason "model unavailable".

After receiving a verdict the auditor updates the session's
``validation.llm_sanity_check`` section in the database.

Validates Requirements: 13.1, 13.2, 13.3, 13.4
"""

import json
import logging
import threading
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from src.database import SessionLocal

logger = logging.getLogger(__name__)

# Ollama defaults — model name is intentionally configurable.
DEFAULT_OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3.2"
CONNECT_TIMEOUT_S = 30
READ_TIMEOUT_S = 120


class LLMAuditor:
    """Async post-calculation anomaly detection via a local Ollama model.

    Validates Requirements: 13.1, 13.2, 13.3, 13.4
    """

    def __init__(
        self,
        ollama_url: str = DEFAULT_OLLAMA_URL,
        model: str = DEFAULT_MODEL,
    ) -> None:
        self.ollama_url = ollama_url
        self.model = model

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def audit_async(self, session: dict, db: Session) -> None:
        """Fire-and-forget: send session summary to Ollama, update session.

        Spawns a daemon thread so the caller returns immediately.  The
        background thread creates its **own** DB session (the caller's
        session belongs to a different thread and must not be shared).

        Args:
            session: Complete Calculation Session dict.
            db: Caller's DB session — used only to read the calculation_id.
                All writes happen on a fresh session inside the thread.

        Validates Requirements: 13.1, 13.2, 13.3, 13.4
        """
        calculation_id = session.get("session", {}).get("calculation_id")
        if not calculation_id:
            logger.warning("audit_async called without a calculation_id — skipping")
            return

        summary = self._build_summary(session)

        thread = threading.Thread(
            target=self._run_audit,
            args=(calculation_id, summary, session),
            daemon=True,
            name=f"llm-audit-{calculation_id[:8]}",
        )
        thread.start()

    # ------------------------------------------------------------------
    # Ollama interaction
    # ------------------------------------------------------------------

    def _send_to_ollama(self, summary: dict) -> dict | None:
        """POST session summary to local Ollama API.

        Returns a verdict dict on success, or ``None`` when Ollama is
        unreachable / returns an error.

        Validates Requirements: 13.1, 13.4
        """
        prompt = self._build_prompt(summary)

        try:
            response = httpx.post(
                self.ollama_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=httpx.Timeout(
                    connect=CONNECT_TIMEOUT_S,
                    read=READ_TIMEOUT_S,
                    write=CONNECT_TIMEOUT_S,
                    pool=CONNECT_TIMEOUT_S,
                ),
            )
            response.raise_for_status()
            raw = response.json().get("response", "")
            return self._parse_verdict(raw)

        except httpx.ConnectError:
            logger.info("Ollama not reachable — skipping LLM audit")
            return None
        except httpx.TimeoutException:
            logger.warning("Ollama request timed out — skipping LLM audit")
            return None
        except Exception:
            logger.exception("Unexpected error calling Ollama")
            return None

    # ------------------------------------------------------------------
    # Anomaly baseline
    # ------------------------------------------------------------------

    def _update_anomaly_baseline(
        self,
        origin: str,
        destination: str,
        session: dict,
        db: Session,
    ) -> None:
        """Upsert calculations.overflight_charges_anomalies for this O→D pair.

        For a **new** record the current session's values seed the baseline.
        For an **existing** record the min/max ranges are expanded if the
        current session falls outside them, the FIR sequence pattern is
        appended, ``sample_count`` is incremented, and ``baseline_source``
        transitions through ``llm`` → ``hybrid`` → ``statistical`` as
        volume increases.

        Baseline source transition thresholds:
        - sample_count < 5  → 'llm'
        - 5 ≤ sample_count < 20 → 'hybrid'
        - sample_count ≥ 20 → 'statistical'

        Validates Requirements: 14.1, 14.2, 14.3
        """
        from src.models.overflight_charges_anomaly import OverflightChargesAnomaly

        # --- Extract current session metrics ---
        fir_crossings = session.get("fir_crossings", [])
        totals = session.get("totals", {})

        current_fir_count = len(fir_crossings)
        current_total_usd = totals.get("total_usd")
        current_fir_sequence = [c.get("icao_code") for c in fir_crossings]

        # --- Look up existing record ---
        record = (
            db.query(OverflightChargesAnomaly)
            .filter(
                OverflightChargesAnomaly.origin == origin,
                OverflightChargesAnomaly.destination == destination,
            )
            .first()
        )

        if record is None:
            # INSERT — seed with this session's values
            record = OverflightChargesAnomaly(
                origin=origin,
                destination=destination,
                expected_fir_count_min=current_fir_count,
                expected_fir_count_max=current_fir_count,
                expected_charge_min=current_total_usd,
                expected_charge_max=current_total_usd,
                expected_fir_sequence=[current_fir_sequence] if current_fir_sequence else [],
                sample_count=1,
                baseline_source="llm",
            )
            db.add(record)
        else:
            # UPDATE — expand ranges and append pattern

            # Expand FIR count range
            if record.expected_fir_count_min is None or current_fir_count < record.expected_fir_count_min:
                record.expected_fir_count_min = current_fir_count
            if record.expected_fir_count_max is None or current_fir_count > record.expected_fir_count_max:
                record.expected_fir_count_max = current_fir_count

            # Expand charge range
            if current_total_usd is not None:
                if record.expected_charge_min is None or current_total_usd < float(record.expected_charge_min):
                    record.expected_charge_min = current_total_usd
                if record.expected_charge_max is None or current_total_usd > float(record.expected_charge_max):
                    record.expected_charge_max = current_total_usd

            # Append FIR sequence pattern
            existing_sequences = record.expected_fir_sequence or []
            if current_fir_sequence and current_fir_sequence not in existing_sequences:
                record.expected_fir_sequence = existing_sequences + [current_fir_sequence]

            # Increment sample count
            record.sample_count = (record.sample_count or 0) + 1

            # Transition baseline_source based on new sample_count
            new_count = record.sample_count
            if new_count >= 20:
                record.baseline_source = "statistical"
            elif new_count >= 5:
                record.baseline_source = "hybrid"
            else:
                record.baseline_source = "llm"

        db.flush()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_audit(self, calculation_id: str, summary: dict, session: dict) -> None:
        """Background thread entry-point.

        Creates its own DB session, calls Ollama, persists the verdict,
        updates anomaly baselines, and closes the session.  Any exception
        is caught so the thread never crashes silently.
        """
        if not SessionLocal:
            logger.error(
                "SessionLocal not configured — cannot persist LLM verdict"
            )
            return

        db: Session | None = None
        try:
            db = SessionLocal()

            verdict_dict = self._send_to_ollama(summary)

            if verdict_dict is None:
                verdict_dict = {
                    "model": self.model,
                    "verdict": "skipped",
                    "notes": "model unavailable",
                    "anomalies": [],
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }

            self._persist_verdict(calculation_id, verdict_dict, db)

            # Update anomaly baselines for this origin→destination pair
            origin = session.get("input", {}).get("origin")
            destination = session.get("input", {}).get("destination")
            if origin and destination:
                try:
                    self._update_anomaly_baseline(origin, destination, session, db)
                except Exception:
                    logger.exception(
                        "Failed to update anomaly baseline for %s→%s",
                        origin,
                        destination,
                    )

            db.commit()

            logger.info(
                "LLM audit complete",
                extra={
                    "calculation_id": calculation_id,
                    "verdict": verdict_dict.get("verdict"),
                },
            )

        except Exception:
            logger.exception(
                "LLM audit thread failed for calculation_id=%s",
                calculation_id,
            )
            if db is not None:
                db.rollback()
        finally:
            if db is not None:
                db.close()

    def _persist_verdict(
        self, calculation_id: str, verdict: dict, db: Session
    ) -> None:
        """Write the verdict into the session's validation.llm_sanity_check.

        Uses a JSONB path update so we only touch the relevant key
        without overwriting the rest of session_data.

        Validates Requirements: 13.2
        """
        from sqlalchemy import text as sa_text

        db.execute(
            sa_text(
                """
                UPDATE calculations.overflight_calculation_sessions
                SET session_data = jsonb_set(
                    session_data,
                    '{validation,llm_sanity_check}',
                    CAST(:verdict AS jsonb)
                )
                WHERE calculation_id = :calc_id
                """
            ),
            {
                "calc_id": calculation_id,
                "verdict": json.dumps(verdict),
            },
        )

    def _build_summary(self, session: dict) -> dict:
        """Extract a concise summary from the full session for the LLM prompt."""
        input_data = session.get("input", {})
        totals = session.get("totals", {})
        fir_crossings = session.get("fir_crossings", [])
        validation = session.get("validation", {})

        fir_list = [
            {
                "icao_code": c.get("icao_code"),
                "fir_name": c.get("fir_name"),
                "country": c.get("country"),
                "segment_distance_nm": c.get("segment_distance_nm"),
            }
            for c in fir_crossings
        ]

        return {
            "origin": input_data.get("origin"),
            "destination": input_data.get("destination"),
            "aircraft_type": input_data.get("aircraft_type"),
            "fir_count": totals.get("fir_count", len(fir_crossings)),
            "total_usd": totals.get("total_usd"),
            "fir_list": fir_list,
            "dual_system_match": validation.get("dual_system", {}).get(
                "fir_lists_match"
            ),
        }

    @staticmethod
    def _build_prompt(summary: dict) -> str:
        """Build the text prompt sent to Ollama."""
        return (
            "You are an aviation overflight charges auditor. "
            "Analyse the following route calculation summary and respond "
            "with a JSON object containing exactly these keys:\n"
            '  "verdict": one of "plausible", "anomaly", or "needs_review"\n'
            '  "notes": a brief explanation\n'
            '  "anomalies": a list of strings describing any anomalies found '
            "(empty list if none)\n\n"
            f"Summary:\n{json.dumps(summary, indent=2)}\n\n"
            "Respond ONLY with the JSON object, no other text."
        )

    def _parse_verdict(self, raw_text: str) -> dict:
        """Best-effort parse of the LLM response into a verdict dict."""
        checked_at = datetime.now(timezone.utc).isoformat()

        try:
            # Try to extract JSON from the response
            stripped = raw_text.strip()
            # Handle cases where the LLM wraps JSON in markdown code fences
            if stripped.startswith("```"):
                lines = stripped.split("\n")
                json_lines = [
                    l for l in lines if not l.strip().startswith("```")
                ]
                stripped = "\n".join(json_lines).strip()

            parsed = json.loads(stripped)

            verdict = parsed.get("verdict", "needs_review")
            if verdict not in ("plausible", "anomaly", "needs_review"):
                verdict = "needs_review"

            return {
                "model": self.model,
                "verdict": verdict,
                "notes": str(parsed.get("notes", "")),
                "anomalies": list(parsed.get("anomalies", [])),
                "checked_at": checked_at,
            }
        except (json.JSONDecodeError, AttributeError):
            logger.warning("Could not parse LLM response as JSON")
            return {
                "model": self.model,
                "verdict": "needs_review",
                "notes": f"Unparseable LLM response: {raw_text[:200]}",
                "anomalies": [],
                "checked_at": checked_at,
            }
