from drfc import model


def sample_project(theme="minimal", **timing):
    p = model.new_project(title="Prova", copyright_owner="Acme srl", year=2026, preset="it_cinema")
    p["style"]["theme"] = theme
    p["timing"].update(timing)
    seq = model.new_sequence("end", "crawl", blocks=[
        model.new_block("credit", role="director", names=["Giulia Ferri"]),
        model.new_block("list", heading="dept:camera", rows=[
            {"role": "cinematographer", "names": ["Luca Marini"]},
            {"role": "first_ac", "names": ["Anna Costa", "Ivo Serra"]}]),
        model.new_block("cast", heading="h:cast", rows=[{"actor": "Marta Lodi", "character": "Elena"}]),
        model.new_block("names", heading="h:thanks", names=["Persona %d" % i for i in range(14)]),
        model.new_block("music", cues=[{"title": "Notte", "writers": ["A. B"], "performers": ["Band"],
                                         "agreement": "courtesy", "licensor": "Label X"}]),
        model.new_block("legal", items=[{"key": "copyright"}, {"key": "fiction"}], hold_s=2.0),
    ])
    cards = model.new_sequence("opening", "cards", blocks=[
        model.new_block("card", lines=[{"text": "Acme presenta", "style": "card_name"}]),
        model.new_block("title", text="Prova"),
        model.new_block("card", role="director", names=["Giulia Ferri"]),
    ])
    p["sequences"] = [cards, seq]
    return model.normalize(p)
