from drfc import guide, outline, placeholders


def _project():
    return guide.new_project("corto", "it", use_placeholders=True)


def test_build_covers_every_sequence_and_has_entries():
    p = _project()
    rows = outline.build(p)
    assert sum(r["kind"] == "seq" for r in rows) == len(p["sequences"])
    assert any(r["kind"] == "entry" for r in rows)
    assert all(r["seq"] is not None for r in rows)


def test_entry_roundtrip_and_find():
    p = _project()
    rows = outline.build(p)
    i = next(i for i, r in enumerate(rows) if r["kind"] == "entry")
    r = rows[i]
    outline.set_entry(p, r, "gaffer", ["A B"])
    assert outline.entry_values(p, r) == ("gaffer", ["A B"])
    assert outline.find(outline.build(p), r["seq"], r["block"], r["row"]) == i


def test_add_delete_and_move():
    p = _project()
    rows = outline.build(p)
    r = next(r for r in rows if r["kind"] == "entry" and outline.block_of(p, r)["type"] == "list")
    b = outline.block_of(p, r)
    n = len(b["rows"])
    assert outline.add_entry_after(p, r, "gaffer", ["X"])
    assert len(b["rows"]) == n + 1
    assert outline.delete_entry(p, dict(r, row=r["row"] + 1)) == "entry"
    assert len(b["rows"]) == n
    blocks = p["sequences"][r["seq"]]["blocks"]
    first = blocks[r["block"]]
    assert outline.move_section(p, r, 1) == r["block"] + 1
    assert blocks[r["block"] + 1] is first
    assert outline.delete_section(p, dict(r, block=r["block"] + 1))
    assert first not in blocks


def test_removing_placeholders_leaves_no_empty_sections():
    p = _project()
    assert placeholders.count(p) > 0
    placeholders.remove_unfilled(p)
    assert placeholders.count(p) == 0
    assert all(placeholders._has_content(b) for s in p["sequences"] for b in s["blocks"]
               if b["type"] in placeholders.FILLABLE and b["type"] not in ("title", "card"))
