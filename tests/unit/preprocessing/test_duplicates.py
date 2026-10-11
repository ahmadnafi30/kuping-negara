"""Duplicate labels are target-specific; grouping hints are global."""

from kuping_negara.preprocessing.duplicates import TextReference, compare_text


def reference(text="Program MBG membantu siswa", *, program="mbg", eligible=True):
    return TextReference("first", program, text, eligible, "group:first")


def test_different_ids_with_identical_text_are_duplicate_labels():
    result = compare_text(
        tweet_id="second",
        program_id="mbg",
        text="Program MBG membantu siswa",
        references=[reference()],
    )
    assert result.duplicate_text and not result.duplicate_id
    assert result.split_group_id == "group:first"


def test_cross_target_copy_remains_available_with_shared_group():
    result = compare_text(
        tweet_id="first",
        program_id="ckg",
        text="Program MBG membantu siswa",
        references=[reference()],
    )
    assert not result.duplicate_id and not result.duplicate_text
    assert result.split_group_id == "group:first"


def test_review_record_does_not_poison_future_labeling():
    result = compare_text(
        tweet_id="second",
        program_id="mbg",
        text="Program MBG membantu siswa",
        references=[reference(eligible=False)],
    )
    assert not result.duplicate_text
    assert result.split_group_id == "group:first"


def test_small_negation_edit_requires_review_not_same_label():
    positive = "Program MBG sangat membantu siswa mendapatkan makanan sehat setiap hari"
    negative = (
        "Program MBG tidak sangat membantu siswa mendapatkan makanan sehat setiap hari"
    )
    result = compare_text(
        tweet_id="second",
        program_id="mbg",
        text=negative,
        references=[reference(positive)],
    )
    assert result.near_duplicate and not result.duplicate_text
    assert result.similar_to == "first"


def test_short_opinions_are_not_fuzzy_deduplicated():
    result = compare_text(
        tweet_id="second",
        program_id="mbg",
        text="MBG tidak bagus",
        references=[reference("MBG bagus")],
    )
    assert not result.near_duplicate and not result.duplicate_text


def test_edited_tweet_keeps_group_across_targets():
    result = compare_text(
        tweet_id="first",
        program_id="ckg",
        text="CKG kurang merata",
        references=[reference()],
    )
    assert result.split_group_id == "group:first"
    assert not result.duplicate_id
