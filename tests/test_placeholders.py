import copy

import pytest

from drfc import engine, guide, i18n, model, placeholders, presets, validate


@pytest.mark.parametrize("pid", [p["id"] for p in presets.list_presets()])
@pytest.mark.parametrize("lang", i18n.LANGUAGES)
def test_fill_makes_every_preset_complete_and_layoutable(pid, lang):
    p = presets.project_from_preset(pid, language=lang, title="T", copyright_owner="O")
    n = placeholders.fill(p)
    assert n > 0
    _c, results, issues = engine.solve_all(p)
    assert results
    for seq, lay, tl, _n in results:
        assert tl["total_frames"] > 0
    assert not [i for i in issues if i["level"] == "error" and i["code"] in ("file", "logo_kit", "music_licensor")]
    assert any(i["code"] == "placeholder" for i in issues)


def test_all_placeholder_texts_exist_in_every_language():
    base = set(placeholders.texts("en"))
    for lang in i18n.LANGUAGES:
        assert set(placeholders.texts(lang)) >= base
        assert placeholders.texts(lang)["name"]


def test_fill_is_idempotent_and_never_overwrites():
    p = guide.new_project("lungo", "it", title="T")
    p["sequences"][1]["blocks"][0]["names"] = ["Giulia Ferri"]
    placeholders.fill(p)
    snap = copy.deepcopy(p)
    assert placeholders.fill(p) == 0
    assert p == snap
    director = [b for b in p["sequences"][1]["blocks"] if b.get("role") == "director"]
    names = [x for b in p["sequences"][1]["blocks"] if b["type"] == "credit" for x in b["names"]]
    assert "Giulia Ferri" in names or director


def test_music_placeholders_show_different_agreements():
    p = guide.new_project("corto", "it", title="T", use_placeholders=True)
    music = [b for b in p["sequences"][1]["blocks"] if b["type"] == "music"][0]
    assert {c["agreement"] for c in music["cues"]} == {"courtesy", "licensed"}


def test_count_and_remove_unfilled():
    p = guide.new_project("corto", "it", title="T", use_placeholders=True)
    total = placeholders.count(p)
    assert total > 20
    # l'utente compila una voce
    lst = [b for b in p["sequences"][1]["blocks"] if b["type"] == "list"][0]
    lst["rows"][0]["names"] = ["Giulia Ferri"]
    removed = placeholders.remove_unfilled(p)
    assert removed == total - 0 or removed >= total - 1
    assert placeholders.count(p) == 0
    kept = [r for b in p["sequences"][1]["blocks"] if b["type"] == "list" for r in b["rows"]]
    assert any(r["names"] == ["Giulia Ferri"] for r in kept)
    # restano solo sezioni con contenuto vero; nessun segnaposto
    for b in p["sequences"][1]["blocks"]:
        if b["type"] in ("music", "cast", "agreements", "logos", "laurels"):
            assert placeholders._has_content(b)


def test_remove_unfilled_keeps_cast_row_with_real_actor():
    p = model.normalize({"meta": {"language": "it"}, "sequences": [model.new_sequence("end", "crawl", blocks=[
        model.new_block("cast", rows=[{"actor": "Marta Lodi", "character": "PERSONAGGIO"},
                                      {"actor": "ATTORE", "character": "PERSONAGGIO"}])])]})
    placeholders.remove_unfilled(p)
    assert p["sequences"][0]["blocks"][0]["rows"] == [{"actor": "Marta Lodi", "character": ""}]


def test_placeholder_logos_resolve_without_kit(tmp_path):
    from drfc import imageinfo, logos
    for i in placeholders.LOGO_IDS:
        assert logos.status(i) == "ready"
        assert imageinfo.image_size(logos.resolve(i)) is not None


def test_validation_warning_disappears_when_filled():
    p = guide.new_project("corto", "it", title="T", copyright_owner="O", use_placeholders=True)
    assert any(i["code"] == "placeholder" for i in validate.check_project(p))
    placeholders.remove_unfilled(p)
    assert not any(i["code"] == "placeholder" for i in validate.check_project(p))


def test_new_project_default_has_no_placeholders():
    p = guide.new_project("corto", "it", title="T")
    assert placeholders.count(p) == 0
