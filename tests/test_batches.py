import pytest

from cleanyourphone_app.domain.batches import split_batches


def test_default_size_is_five():
    packages = [f"pkg{i}" for i in range(12)]
    assert split_batches(packages) == [packages[:5], packages[5:10], packages[10:]]


def test_exactly_five_packages_make_one_batch():
    packages = ["a", "b", "c", "d", "e"]
    assert split_batches(packages) == [["a", "b", "c", "d", "e"]]


def test_six_packages_make_a_full_batch_and_a_remainder():
    packages = ["a", "b", "c", "d", "e", "f"]
    assert split_batches(packages) == [["a", "b", "c", "d", "e"], ["f"]]


def test_custom_size_is_honored():
    assert split_batches(["a", "b", "c", "d", "e"], size=2) == [
        ["a", "b"],
        ["c", "d"],
        ["e"],
    ]


def test_empty_input_emits_no_batches():
    assert split_batches([]) == []


def test_duplicates_are_skipped_while_preserving_order():
    assert split_batches(["a", "b", "a", "c", "b"]) == [["a", "b", "c"]]


def test_duplicates_can_cross_batch_boundaries():
    assert split_batches(["a", "b", "c", "d", "e", "a", "f"]) == [
        ["a", "b", "c", "d", "e"],
        ["f"],
    ]


def test_repeated_packages_do_not_emit_an_empty_batch():
    assert split_batches(["a", "a", "a"]) == [["a"]]


@pytest.mark.parametrize("size", [0, -1])
def test_non_positive_size_raises(size):
    with pytest.raises(ValueError):
        split_batches(["a"], size=size)


def test_input_sequence_is_not_mutated():
    packages = ["a", "b", "a"]
    split_batches(packages)
    assert packages == ["a", "b", "a"]
