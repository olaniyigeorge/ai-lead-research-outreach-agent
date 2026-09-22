import pytest

from apps.api.agent.validation import looks_like_gibberish


@pytest.mark.parametrize(
    "objective",
    [
        "ssssssssss",
        "aaaaaaaaaaaaaaaaaaaa",
        "asdkjfhaskdjfhaskdjfh",  # keyboard mash, one long "word"
        "!!!!!!!!!!!!!!!!!!!!",
    ],
)
def test_gibberish_is_rejected(objective):
    assert looks_like_gibberish(objective) is True


@pytest.mark.parametrize(
    "objective",
    [
        "Find 10 US B2B SaaS companies with 10 to 100 employees",
        "find some good saas companies",  # vague, but a real attempt -- must NOT be rejected
        "operations-heavy agencies in Canada with 20-50 employees",
    ],
)
def test_real_objectives_are_not_rejected(objective):
    assert looks_like_gibberish(objective) is False
