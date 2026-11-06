"""Basic source-presence evaluation for the local hospital RAG demo."""

from rag_engine import answer_question


test_cases = [
    {
        "question": "What are the laboratory working hours?",
        "expected_source": "lab_rules.txt",
    },
    {
        "question": "What are the timings of the hospital shifts?",
        "expected_source": "duty_roster.txt",
    },
    {
        "question": "What information is collected during new patient registration?",
        "expected_source": "hospital_sop.txt",
    },
    {
        "question": "What is the cardiology department's phone number?",
        "expected_source": None,
    },
]


def main():
    passed = 0
    failed = 0

    print("\n===== RAG SYSTEM EVALUATION =====")
    print("Checking expected source presence; answer correctness is not scored.\n")

    for index, test in enumerate(test_cases, start=1):
        question = test["question"]
        expected_source = test["expected_source"]
        print(f"\nTest {index}: {question}")

        try:
            result = answer_question(question)
            actual_sources = {
                source.get("filename")
                for source in result.get("sources", [])
                if source.get("filename")
            }

            if expected_source is None:
                test_passed = not actual_sources
                expected = "no sources"
            else:
                test_passed = expected_source in actual_sources
                expected = expected_source

            status = "PASS" if test_passed else "FAIL"
            print(f"  Expected source: {expected}")
            print(f"  Actual sources: {', '.join(sorted(actual_sources)) or '(none)'}")
            print(f"  Result: {status}")

            if test_passed:
                passed += 1
            else:
                failed += 1
        except Exception as error:
            failed += 1
            print(f"  Result: FAIL (error: {error})")

    total = passed + failed
    accuracy = (passed / total * 100) if total else 0.0
    print("\n===== SUMMARY =====")
    print(f"Passed: {passed}/{total}")
    print(f"Failed: {failed}/{total}")
    print(f"Source-presence pass rate: {accuracy:.1f}%")
    print("Note: extra unrelated sources and answer correctness are not evaluated.")


if __name__ == "__main__":
    main()
