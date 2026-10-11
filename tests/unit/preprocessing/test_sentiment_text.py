"""Sentiment cues must survive cleaning without creating keyword evidence."""

import pytest

from kuping_negara.preprocessing.text import (
    clean_text,
    match_keyword,
    prepare_model_text,
    text_fingerprint,
)


@pytest.mark.parametrize(
    "emoji",
    [
        "\U0001f469\u200d\U0001f4bb",
        "\U0001f468\u200d\U0001f469\u200d\U0001f467",
        "\U0001f44d\U0001f3fd",
        "\u2764\ufe0f",
        "\U0001f3f4\U000e0067\U000e0062\U000e007f",
    ],
)
def test_emoji_graphemes_remain_intact(emoji):
    assert prepare_model_text("MBG " + emoji) == "MBG " + emoji
    assert clean_text("MBG " + emoji) == "mbg " + emoji


def test_model_view_preserves_negation_case_emphasis_and_hashtag():
    text = "@akun MBG NGGAK bagus!!! #TolakMBG https://t.co/link"
    assert prepare_model_text(text) == "MBG NGGAK bagus!!! #TolakMBG"
    assert clean_text(text) == "mbg nggak bagus!!! tolakmbg"
    assert (
        prepare_model_text("MBG baguuuus, tapi belum merata :(")
        == "MBG baguuuus, tapi belum merata :("
    )


@pytest.mark.parametrize("tail", ["!!!", "?!", ":)", "\U0001f622", "!!!\U0001f622"])
def test_link_removal_keeps_attached_sentiment(tail):
    assert prepare_model_text("MBG https://t.co/link" + tail) == "MBG " + tail


@pytest.mark.parametrize(
    "text,keyword",
    [
        ("#TolakMBG", "mbg"),
        ("#tolakmbg", "mbg"),
        ("#DukungCKG", "ckg"),
        ("#CekKesehatanGratis", "cek kesehatan gratis"),
        ("#makanbergizigratis", "makan bergizi gratis"),
        ("#SekolahRakyat", "sekolah rakyat"),
    ],
)
def test_program_hashtags_are_relevance_evidence(text, keyword):
    assert match_keyword(prepare_model_text(text), [keyword]) == keyword


@pytest.mark.parametrize(
    "text", ["#mbgossip", "#notmbg", "@mbg", "https://example.test/mbg", "sambg"]
)
def test_substrings_mentions_and_links_do_not_create_relevance(text):
    assert match_keyword(text, ["mbg"]) is None


def test_identity_noise_does_not_change_fingerprint_but_negation_does():
    assert text_fingerprint("@a MBG bagus https://a.test") == text_fingerprint(
        "@b mbg bagus https://b.test"
    )
    assert text_fingerprint("MBG bagus") != text_fingerprint("MBG tidak bagus")
    assert text_fingerprint("MBG bagus!") != text_fingerprint("MBG bagus?")
    assert text_fingerprint("MBG bagus \U0001f60a") != text_fingerprint(
        "MBG bagus \U0001f622"
    )


def test_unsafe_control_characters_removed_without_decoding_loss():
    assert prepare_model_text("MBG\u202e bagus\x00!") == "MBG bagus !"
    assert prepare_model_text("MBG &amp; CKG &lt;3") == "MBG & CKG <3"
