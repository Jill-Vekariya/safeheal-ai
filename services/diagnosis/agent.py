"""Validate model hypotheses against independently derived support; never execute actions."""
import math
from copy import deepcopy

from services.diagnosis.evidence import Bundle, CAUSES, EXPLANATIONS, encoded, timestamp, validate_bundle
from services.diagnosis.provider import ProviderError
from services.incidents.telemetry import SERVICES


def validate_proposal(proposal, bundle):
    validate_bundle(bundle)
    if not isinstance(proposal, dict) or set(proposal) != {"hypotheses"}:
        raise ValueError("Invalid proposal schema")
    items = proposal["hypotheses"]
    if not isinstance(items, list) or len(items) > 3:
        raise ValueError("Invalid hypothesis count")
    records = {r.id: r for r in bundle.records}
    result, seen = [], set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {"classification", "service", "confidence", "evidence_refs"}:
            raise ValueError("Invalid hypothesis schema")
        cause, service, confidence, refs = (item[k] for k in ("classification", "service", "confidence", "evidence_refs"))
        if cause not in CAUSES or service not in SERVICES:
            raise ValueError("Unknown classification or service")
        if type(confidence) not in (int, float) or not 0 <= confidence <= 1 or not math.isfinite(confidence):
            raise ValueError("Invalid confidence")
        if not isinstance(refs, list) or not 1 <= len(refs) <= 6 or any(not isinstance(r, str) for r in refs) or len(set(refs)) != len(refs):
            raise ValueError("Evidence references are required and unique")
        for ref in refs:
            record = records.get(ref)
            if record is None or record.service != service or cause not in record.supports:
                raise ValueError("Unknown or unsupported evidence reference")
        if (cause, service) in seen:
            raise ValueError("Duplicate hypothesis")
        seen.add((cause, service))
        result.append({"classification": cause, "service": service,
                       "confidence": min(float(confidence), .80 if cause == "process_exit" else .70),
                       "evidence_refs": refs, "explanation": EXPLANATIONS[cause]})
    return sorted(result, key=lambda h: (-h["confidence"], CAUSES.index(h["classification"]), -SERVICES.index(h["service"])))


class DiagnosisAgent:
    def __init__(self, provider=None, confidence_threshold=.65):
        if type(confidence_threshold) not in (float, int) or not math.isfinite(confidence_threshold) or not .5 <= confidence_threshold <= 1:
            raise ValueError("Confidence threshold must be .5..1")
        self.provider = provider
        self.threshold = float(confidence_threshold)

    def diagnose(self, bundle):
        hypotheses, source, reason = [], "deterministic_fallback", "provider_disabled"
        invalid = False
        try:
            bundle = deepcopy(validate_bundle(bundle))
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError):
            try:
                at = timestamp(bundle.as_of)
            except (ValueError, TypeError, AttributeError, OverflowError):
                at = 0.
            bundle = Bundle(at, issues=["invalid_evidence"])
            invalid = True
        if invalid:
            reason = "invalid_evidence"
        elif not bundle.eligible:
            reason = "insufficient_evidence"
        elif not bundle.candidates():
            reason = "no_supported_fault_hypothesis"
        elif self.provider is not None:
            try:
                # An adapter gets a detached copy, never the trusted validator input.
                proposal = self.provider.propose(deepcopy(bundle))
                hypotheses = validate_proposal(proposal, bundle)
                if hypotheses:
                    source, reason = "llm", "validated"
                else:
                    reason = "model_abstained"
            except ProviderError as exc:
                # ProviderError codes belong to our transport; other provider implementations are untrusted.
                allowed = {"provider_disabled", "input_budget_exceeded", "call_budget_exhausted",
                           "provider_http_error", "provider_response_too_large", "provider_timeout",
                           "provider_incomplete_response", "provider_invalid_response", "provider_unavailable",
                           "provider_output_budget_exceeded", "provider_unsupported_encoding"}
                reason = str(exc) if str(exc) in allowed else "provider_unavailable"
            except (ValueError, TypeError):
                reason = "model_output_rejected"
            except Exception:
                # Unexpected adapter exceptions degrade without exposing text or retry.
                reason = "provider_unavailable"
        if not hypotheses and bundle.eligible and reason != "model_abstained":
            candidates = bundle.candidates()[:3]
            hypotheses = validate_proposal({"hypotheses": [{**c, "confidence": .55} for c in candidates]}, bundle)
        top = hypotheses[0] if hypotheses else None
        status = ("insufficient_evidence" if top is None else
                  "supported_hypothesis" if top["confidence"] >= self.threshold else "low_confidence")
        result = {"schema_version": "day6-diagnosis-v1", "as_of": bundle.as_of,
                  "status": status, "source": source, "provider_status": reason,
                  "confidence_threshold": self.threshold,
                  "suspected_root_service": top["service"] if top else None,
                  "summary": top["explanation"] if top else "Evidence is insufficient for a supported fault hypothesis.",
                  "hypotheses": hypotheses, "evidence": bundle.document(),
                  "uncertainties": ["Root service is a hypothesis based on observations and fixed topology.",
                                    "Confidence is uncalibrated; an injection mechanism is not inferred.",
                                    *sorted(set(bundle.issues))],
                  "next_step": "human_review" if status == "supported_hypothesis" else "collect_read_only_evidence",
                  "execution_allowed": False}
        encoded(result)  # Refuse non-JSON/non-finite results before persistence.
        return result
