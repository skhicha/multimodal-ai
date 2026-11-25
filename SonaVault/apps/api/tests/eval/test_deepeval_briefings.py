"""DeepEval Quantitative Evaluation Suite for Sovereign RAG Briefings.

Executes quantitative evaluations on citation precision, factual faithfulness,
answer relevancy, and adversarial injection resistance using DeepEval.
"""

import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase

from tests.eval.dataset import EVALUATION_DATASET, HASH_CI_AUDIO
from tests.eval.metrics import (
    AdversarialResistanceMetric,
    AnswerRelevancyMetric,
    CitationPrecisionMetric,
    EvidenceFaithfulnessMetric,
)


@pytest.mark.parametrize("test_case", EVALUATION_DATASET[:3])
def test_briefing_citation_precision(test_case: LLMTestCase):
    """Evaluates that all citations strictly match retrieved evidence."""
    metric = CitationPrecisionMetric(threshold=1.0)
    assert_test(test_case, [metric])


@pytest.mark.parametrize("test_case", EVALUATION_DATASET[:3])
def test_briefing_evidence_faithfulness(test_case: LLMTestCase):
    """Evaluates that claims in the briefing are faithfully grounded."""
    metric = EvidenceFaithfulnessMetric(threshold=0.75)
    assert_test(test_case, [metric])


@pytest.mark.parametrize("test_case", EVALUATION_DATASET[:3])
def test_briefing_answer_relevancy(test_case: LLMTestCase):
    """Evaluates semantic relevancy and responsiveness to the operational inquiry."""
    metric = AnswerRelevancyMetric(threshold=0.75)
    assert_test(test_case, [metric])


def test_adversarial_injection_resistance():
    """Evaluates that prompt injection attempts do NOT leak system prompt or security tokens."""
    adversarial_case = EVALUATION_DATASET[3]
    metric = AdversarialResistanceMetric(threshold=1.0)
    assert_test(adversarial_case, [metric])


def test_hallucinated_citation_detected_and_failed():
    """Confirms CitationPrecisionMetric strictly fails when a fake SHA-256 hash is cited."""
    fake_case = LLMTestCase(
        input="Describe vessel speed.",
        actual_output="Vessel was speeding at 24 knots [deadbeef00112233 @ 01:23].",
        retrieval_context=[
            f'<evidence sha256="{HASH_CI_AUDIO}">Vessel logged at 12 knots.</evidence>'
        ],
    )
    metric = CitationPrecisionMetric(threshold=1.0)
    score = metric.measure(fake_case)
    assert score == 0.0
    assert metric.is_successful() is False
    assert "deadbeef00112233" in metric.reason
