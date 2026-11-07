"""Evaluate source retrieval and required answer facts for the local RAG demo."""

import re

from rag_engine import UNSUPPORTED_ANSWER, answer_question


test_cases = [
    {
        "question": "What are the laboratory working hours?",
        "expected_sources": {"lab_rules.txt"},
        "required_facts": [
            {"label": "8:00 AM start", "alternatives": ["8:00 am"]},
            {"label": "5:00 PM end", "alternatives": ["5:00 pm"]},
            {"label": "Monday", "alternatives": ["monday"]},
            {"label": "Saturday", "alternatives": ["saturday"]},
        ],
    },
    {
        "question": "What are the timings of the hospital shifts?",
        "expected_sources": {"duty_roster.txt"},
        "required_facts": [
            {
                "label": "morning shift, 8:00 AM to 2:00 PM",
                "alternatives": ["morning shift: 8:00 am to 2:00 pm"],
            },
            {
                "label": "evening shift, 2:00 PM to 8:00 PM",
                "alternatives": ["evening shift: 2:00 pm to 8:00 pm"],
            },
            {
                "label": "night shift, 8:00 PM to 8:00 AM",
                "alternatives": ["night shift: 8:00 pm to 8:00 am"],
            },
        ],
    },
    {
        "question": "What information is collected during new patient registration?",
        "expected_sources": {"hospital_sop.txt"},
        "required_facts": [
            {"label": "patient name", "alternatives": ["patient name", "name"]},
            {"label": "age", "alternatives": ["age"]},
            {
                "label": "contact details",
                "alternatives": ["contact details", "contact number", "contact information"],
            },
            {"label": "address", "alternatives": ["address"]},
        ],
    },
    {
        "question": "What is the cardiology department's phone number?",
        "expected_sources": set(),
        "expected_answer": UNSUPPORTED_ANSWER,
        "required_facts": [],
    },
]


def normalize(text):
    """Lowercase text and normalize punctuation/spacing for fact matching."""
    text = re.sub(r"[^a-z0-9:]+", " ", text.casefold())
    return re.sub(r"\s+", " ", text).strip()


def evaluate_case(test, result):
    expected_sources = test["expected_sources"]
    actual_sources = {
        source.get("filename")
        for source in result.get("sources", [])
        if source.get("filename")
    }
    expected_answer = test.get("expected_answer")
    answer = result.get("answer", "")

    if expected_sources:
        source_correct = expected_sources.issubset(actual_sources)
    else:
        # The unsupported test passes source correctness only when retrieval is empty.
        source_correct = not actual_sources

    if actual_sources:
        source_precision = len(actual_sources & expected_sources) / len(actual_sources)
    else:
        # No retrieved sources is correct for the unsupported case, but a miss for supported cases.
        source_precision = 1.0 if not expected_sources else 0.0

    if expected_answer is not None:
        answer_correct = answer.strip() == expected_answer
        matched_facts = 1 if answer_correct else 0
        fact_count = 1
        missing_facts = [] if answer_correct else ["exact unsupported fallback"]
    else:
        normalized_answer = normalize(answer)
        matched_labels = [
            fact["label"]
            for fact in test["required_facts"]
            if any(normalize(alternative) in normalized_answer for alternative in fact["alternatives"])
        ]
        missing_facts = [
            fact["label"]
            for fact in test["required_facts"]
            if fact["label"] not in matched_labels
        ]
        fact_count = len(test["required_facts"])
        matched_facts = fact_count - len(missing_facts)
        answer_correct = not missing_facts

    answer_score = matched_facts / fact_count if fact_count else 1.0
    overall_pass = source_correct and source_precision == 1.0 and answer_correct

    return {
        "actual_sources": actual_sources,
        "source_correct": source_correct,
        "source_precision": source_precision,
        "matched_facts": matched_facts,
        "fact_count": fact_count,
        "answer_score": answer_score,
        "answer_correct": answer_correct,
        "missing_facts": missing_facts,
        "overall_pass": overall_pass,
    }


def main():
    source_correct_count = 0
    overall_pass_count = 0
    source_precision_scores = []
    answer_scores = []

    print("\n===== RAG QUALITY EVALUATION =====")
    print("Metrics: expected-source retrieval, source precision, and required answer facts.")
    print("Source precision is 100% for the unsupported case only when no source is returned.\n")

    for index, test in enumerate(test_cases, start=1):
        print(f"\nTest {index}: {test['question']}")

        try:
            result = answer_question(test["question"])
            print("  Validation status:", result.get("validation_status"))
            print("  Validation warnings:", result.get("warnings", []))
            print("  Final answer:", repr(result.get("answer", "")))
            print(
                "  Verified source chunks:",
                [
                    f"{source.get('source_id')} - {source.get('filename')} "
                    f"(chunk {source.get('chunk_index')})"
                    for source in result.get("sources", [])
                ],
            )
            metrics = evaluate_case(test, result)
        except Exception as error:
            metrics = {
                "actual_sources": set(),
                "source_correct": False,
                "source_precision": 0.0,
                "matched_facts": 0,
                "fact_count": 1 if test.get("expected_answer") is not None else len(test["required_facts"]),
                "answer_score": 0.0,
                "answer_correct": False,
                "missing_facts": [f"evaluation error: {error}"],
                "overall_pass": False,
            }

        expected_sources = test["expected_sources"]
        expected_label = ", ".join(sorted(expected_sources)) or "(none)"
        actual_label = ", ".join(sorted(metrics["actual_sources"])) or "(none)"
        source_correct_label = "PASS" if metrics["source_correct"] else "FAIL"
        answer_label = "PASS" if metrics["answer_correct"] else "FAIL"
        overall_label = "PASS" if metrics["overall_pass"] else "FAIL"

        print(f"  Expected sources: {expected_label}")
        print(f"  Actual sources:   {actual_label}")
        print(f"  Source correctness: {source_correct_label}")
        print(
            "  Source precision: "
            f"{metrics['source_precision'] * 100:.1f}% "
            f"({len(metrics['actual_sources'] & expected_sources)}/"
            f"{len(metrics['actual_sources'])} returned sources relevant)"
        )
        if metrics["fact_count"]:
            print(
                f"  Answer facts: {metrics['matched_facts']}/{metrics['fact_count']} "
                f"({metrics['answer_score'] * 100:.1f}%) - {answer_label}"
            )
        else:
            print(f"  Answer facts: no required facts configured - {answer_label}")
        if metrics["missing_facts"]:
            print(f"  Missing facts: {', '.join(metrics['missing_facts'])}")
        print(f"  Overall: {overall_label}")

        source_correct_count += int(metrics["source_correct"])
        overall_pass_count += int(metrics["overall_pass"])
        source_precision_scores.append(metrics["source_precision"])
        answer_scores.append(metrics["answer_score"])

    total = len(test_cases)
    mean_source_precision = sum(source_precision_scores) / total if total else 0.0
    mean_answer_score = sum(answer_scores) / total if total else 0.0

    print("\n===== SUMMARY =====")
    print(f"Source correctness: {source_correct_count}/{total} ({source_correct_count / total * 100:.1f}%)")
    print(f"Mean source precision: {mean_source_precision * 100:.1f}%")
    print(f"Mean answer fact score: {mean_answer_score * 100:.1f}%")
    print(f"Overall passing cases: {overall_pass_count}/{total}")
    print("Note: this is a small synthetic demo evaluation, not validation of real hospital policy.")


if __name__ == "__main__":
    main()
