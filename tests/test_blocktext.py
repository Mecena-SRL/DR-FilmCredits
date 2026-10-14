import pytest

from drfc import blocktext, model


@pytest.mark.parametrize("btype,text", [
    ("credit", "director: Giulia Ferri"),
    ("list", "cinematographer: Luca Marini\nfirst_ac: Anna Costa, Ivo Serra"),
    ("cast", "Marta Lodi = Elena\nPaolo Gentile = Tommaso"),
    ("names", "A\nB\nC"),
    ("music", "titolo: Il mare\nautori: A, B\ninterpreti: Band\naccordo: courtesy\nlicenziante: Band\n\ntitolo: Due\nautori: C\naccordo: original"),
    ("agreements", "Villa Rossi | Famiglia Rossi | free\nPorto | Comune | public"),
    ("logos", "loghi/mic.png | mic | 1.2 | Ministero"),
    ("media", "bts/01.jpg | Sul set | 0.8"),
    ("legal", "@copyright\n@ai_disclosure uses=montaggio, voce\nTesto libero"),
    ("title", "Il film"),
])
def test_roundtrip(btype, text):
    b = blocktext.parse(model.new_block(btype), text)
    again = blocktext.parse(model.new_block(btype), blocktext.render(b))
    for k in ("role", "names", "rows", "cues", "entries", "items", "text"):
        assert b.get(k) == again.get(k), k


def test_list_parsing_details():
    b = blocktext.parse(model.new_block("list"), "gaffer: A; B\n  C\nkey_grip: D")
    assert b["rows"] == [{"role": "gaffer", "names": ["A", "B", "C"]}, {"role": "key_grip", "names": ["D"]}]


def test_music_parsing_fields():
    b = blocktext.parse(model.new_block("music"), "title: Song\nwriters: A, B\nteam: si\nagreement: licensed\nlicensor: L")
    cue = b["cues"][0]
    assert cue["writers"] == ["A", "B"] and cue["writers_team"] is True and cue["licensor"] == "L"


def test_legal_values():
    b = blocktext.parse(model.new_block("legal"), "@ai_disclosure uses=montaggio, voce year=2025")
    assert b["items"][0]["values"] == {"uses": "montaggio, voce", "year": "2025"}


def test_card_lines_with_styles():
    b = blocktext.parse(model.new_block("card"), "[card_role] presenta\n[card_name] Acme")
    assert [l["style"] for l in b["lines"]] == ["card_role", "card_name"]
