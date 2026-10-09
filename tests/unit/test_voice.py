"""The voice check (QA plan 4.4): warnings in the run summary, never a gate."""

import pytest

from citemark.evals.voice import voice_problems


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("Sorry, the help center doesn't say.", "apologizes"),
        ("We apologize for that.", "apologizes"),
        ("Done!", "has an exclamation mark"),
        ("Click Save \U0001f44d", "has an emoji"),
        ("As an AI, I can't see your screen.", 'says "As an AI"'),
        (" ".join(["word"] * 121), "is over 120 words without numbered steps"),
        ("The passages cover several of these.", "mentions its passages or instructions"),
        ("Based on the search results, yes.", "mentions its passages or instructions"),
    ],
)
def test_each_voice_rule(text, problem):
    assert problem in voice_problems(text)


def test_a_plain_answer_and_long_numbered_steps_pass():
    steps = "\n".join(f"{n}. " + " ".join(["step"] * 20) for n in range(1, 8))
    assert voice_problems("Turn it off in **Personal settings**.") == []
    assert voice_problems(steps) == []
