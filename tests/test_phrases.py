import pytest

from drfc import i18n, phrases
from drfc.model import AGREEMENT_KINDS, MUSIC_AGREEMENTS


@pytest.mark.parametrize("lang", i18n.LANGUAGES)
def test_music_agreements_all_languages(lang):
    for ag in MUSIC_AGREEMENTS:
        cue = {"title": "Song", "writers": ["A", "B"], "performers": ["P"], "publisher": "Pub",
               "agreement": ag, "licensor": "Lic", "cc_license": "CC BY 4.0", "agent": "Ag"}
        lines = phrases.music_cue_lines(cue, lang)
        assert lines[0][1] == "name"
        for text, _ in lines:
            assert "{" not in text and text.strip()


@pytest.mark.parametrize("lang", i18n.LANGUAGES)
def test_agreement_kinds_all_languages(lang):
    for kind, ags in AGREEMENT_KINDS.items():
        for ag in ags:
            t = phrases.agreement_line(kind, {"name": "Villa", "provider": "Rossi", "agreement": ag}, lang)
            assert "{" not in t and t


@pytest.mark.parametrize("lang", i18n.LANGUAGES)
def test_legal_keys_all_languages(lang):
    keys = i18n.phrases("en")["legal"].keys()
    for k in keys:
        t = phrases.legal_text({"key": k, "values": {"uses": ["montaggio", "VFX"], "cert_no": "123",
                                                     "rating": "PG", "unions": "IATSE", "society": "SIAE",
                                                     "name": "X", "country": "Italia"}},
                               lang, {"year": 2026, "copyright_owner": "Acme"})
        assert "{" not in t


def test_free_vs_paid_music_wording():
    free = phrases.music_cue_lines({"title": "X", "agreement": "courtesy", "licensor": "Band"}, "it")
    paid = phrases.music_cue_lines({"title": "X", "agreement": "licensed", "licensor": "Label"}, "it")
    assert "gentile concessione" in free[-1][0]
    assert "licenza" in paid[-1][0]


def test_wga_team_vs_and():
    assert i18n.join_names(["A", "B"], "en", team=True) == "A & B"
    assert i18n.join_names(["A", "B", "C"], "en") == "A, B and C"
    assert i18n.join_names(["A", "B"], "it") == "A e B"


def test_missing_licensor_produces_no_agreement_line():
    lines = phrases.music_cue_lines({"title": "X", "agreement": "licensed"}, "en")
    assert len(lines) == 1


def test_role_labels_complete():
    for k, r in i18n.roles()["roles"].items():
        for lang in i18n.LANGUAGES:
            assert r.get(lang), (k, lang)
        assert r["dept"] in i18n.roles()["departments"], k
