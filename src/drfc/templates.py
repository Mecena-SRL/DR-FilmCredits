"""Title Fusion "manuali" (macro .setting) da trascinare dalla libreria Effetti > Titles.

Complementari al generatore: per un cartello al volo, una lower-third, un brano o la riga
di copyright senza aprire il wizard. Generati da codice per restare coerenti con i temi.

    python -m drfc.templates templates/
"""

import os
import sys

from . import layout
from .fusion_writer import hex_rgba, lua_str, num

EM_K = 1.0 / 1.08  # vedi fusion_constants


def _size(px_at_1080, ref_w=1920.0):
    return (px_at_1080) / (ref_w * EM_K)


def _text(name, text, st, center, anchor=0, size_scale=1.0):
    r, g, b, _a = hex_rgba(st.get("color"))
    lines = [
        "\t\t\t\t%s = TextPlus {" % name,
        "\t\t\t\t\tInputs = {",
        "\t\t\t\t\t\tGlobalOut = Input { Value = 119, },",
        "\t\t\t\t\t\tWidth = Input { Value = 1920, },",
        "\t\t\t\t\t\tHeight = Input { Value = 1080, },",
        "\t\t\t\t\t\tUseFrameFormatSettings = Input { Value = 1, },",
        "\t\t\t\t\t\tCenter = Input { Value = { %s, %s }, }," % (num(center[0]), num(center[1])),
        "\t\t\t\t\t\tStyledText = Input { Value = %s, }," % lua_str(text),
        "\t\t\t\t\t\tFont = Input { Value = %s, }," % lua_str(st["family"]),
        "\t\t\t\t\t\tStyle = Input { Value = %s, }," % lua_str(st.get("style", "Regular")),
        "\t\t\t\t\t\tSize = Input { Value = %s, }," % num(_size(st["size"]) * size_scale),
        "\t\t\t\t\t\tCharacterSpacing = Input { Value = %s, }," % num(float(st.get("tracking", 1.0))),
        "\t\t\t\t\t\tLineSpacing = Input { Value = %s, }," % num(float(st.get("line_spacing", 1.0))),
    ]
    if anchor:
        lines.append("\t\t\t\t\t\tHorizontalLeftCenterRight = Input { Value = %d, }," % anchor)
    lines += [
        "\t\t\t\t\t\tRed1 = Input { Value = %s, }," % num(r),
        "\t\t\t\t\t\tGreen1 = Input { Value = %s, }," % num(g),
        "\t\t\t\t\t\tBlue1 = Input { Value = %s, }," % num(b),
        "\t\t\t\t\t},",
        "\t\t\t\t\tViewInfo = OperatorInfo { Pos = { 0, 0 } },",
        "\t\t\t\t},",
    ]
    return "\n".join(lines)


def _merge(name, bg, fg):
    return ("\t\t\t\t%s = Merge {\n\t\t\t\t\tInputs = {\n"
            "\t\t\t\t\t\tBackground = Input { SourceOp = %s, Source = \"Output\", },\n"
            "\t\t\t\t\t\tForeground = Input { SourceOp = %s, Source = \"Output\", },\n"
            "\t\t\t\t\t},\n\t\t\t\t\tViewInfo = OperatorInfo { Pos = { 110, 0 } },\n\t\t\t\t},") % (name, lua_str(bg), lua_str(fg))


def _bg():
    return ("\t\t\t\tBg = Background {\n\t\t\t\t\tInputs = {\n"
            "\t\t\t\t\t\tGlobalOut = Input { Value = 119, },\n"
            "\t\t\t\t\t\tWidth = Input { Value = 1920, },\n\t\t\t\t\t\tHeight = Input { Value = 1080, },\n"
            "\t\t\t\t\t\tUseFrameFormatSettings = Input { Value = 1, },\n"
            "\t\t\t\t\t\tTopLeftAlpha = Input { Value = 0, },\n"
            "\t\t\t\t\t},\n\t\t\t\t\tViewInfo = OperatorInfo { Pos = { -110, 0 } },\n\t\t\t\t},")


def macro(name, texts, inputs):
    """texts: [(tool, text, style, center, anchor)], inputs: [(tool, source, label)]"""
    tools = [_bg()]
    prev = "Bg"
    for i, (tool, text, st, center, anchor) in enumerate(texts):
        tools.append(_text(tool, text, st, center, anchor))
        m = "Merge%d" % (i + 1)
        tools.append(_merge(m, prev, tool))
        prev = m
    ins = []
    for i, (tool, source, label) in enumerate(inputs):
        ins.append("\t\t\t\tInput%d = InstanceInput { SourceOp = %s, Source = %s, Name = %s, },"
                   % (i + 1, lua_str(tool), lua_str(source), lua_str(label)))
    return (
        "{\n\tTools = ordered() {\n\t\t%s = MacroOperator {\n\t\t\tCtrlWZoom = false,\n"
        "\t\t\tInputs = ordered() {\n%s\n\t\t\t},\n"
        "\t\t\tOutputs = {\n\t\t\t\tMainOutput1 = InstanceOutput { SourceOp = %s, Source = \"Output\", },\n\t\t\t},\n"
        "\t\t\tViewInfo = GroupInfo { Pos = { 0, 0 } },\n"
        "\t\t\tTools = ordered() {\n%s\n\t\t\t},\n\t\t},\n\t},\n\tActiveTool = %s\n}\n"
        % (name, "\n".join(ins), lua_str(prev), "\n".join(tools), lua_str(name))
    )


def build_all(out_dir, theme="classic"):
    th = layout.themes()[theme]["styles"]
    files = {}
    files["DRFC Cartello Ruolo-Nome"] = macro("DRFC_Card", [
        ("Role", "Regia", th["card_role"], (0.5, 0.55), 0),
        ("Name", "NOME COGNOME", th["card_name"], (0.5, 0.47), 0),
    ], [("Role", "StyledText", "Ruolo"), ("Name", "StyledText", "Nome"), ("Role", "Font", "Font ruolo"),
        ("Name", "Font", "Font nome"), ("Role", "Size", "Dimensione ruolo"), ("Name", "Size", "Dimensione nome")])
    files["DRFC Due Colonne"] = macro("DRFC_TwoColumn", [
        ("Role", "Direttore della fotografia", th["role"], (0.488, 0.5), 1),
        ("Name", "NOME COGNOME", th["name"], (0.512, 0.5), -1),
    ], [("Role", "StyledText", "Ruolo"), ("Name", "StyledText", "Nomi"), ("Role", "Center", "Posizione ruolo"),
        ("Name", "Center", "Posizione nomi"), ("Role", "Size", "Dimensione ruolo"), ("Name", "Size", "Dimensione nomi")])
    files["DRFC Lower Third Credito"] = macro("DRFC_LowerThird", [
        ("Role", "Regia", th["card_role"], (0.08, 0.17), -1),
        ("Name", "NOME COGNOME", th["card_name"], (0.08, 0.11), -1),
    ], [("Role", "StyledText", "Ruolo"), ("Name", "StyledText", "Nome"), ("Role", "Center", "Posizione ruolo"),
        ("Name", "Center", "Posizione nome")])
    files["DRFC Brano Musicale"] = macro("DRFC_MusicCue", [
        ("Song", "«Titolo del brano»", th["name"], (0.5, 0.56), 0),
        ("Details", "di Autore\nEseguita da Interprete\nPer gentile concessione di Etichetta", th["small"], (0.5, 0.47), 0),
    ], [("Song", "StyledText", "Titolo"), ("Details", "StyledText", "Dettagli")])
    files["DRFC Copyright"] = macro("DRFC_Copyright", [
        ("Legal", "© 2026 Società di produzione. Tutti i diritti riservati.", th["legal"], (0.5, 0.12), 0),
    ], [("Legal", "StyledText", "Testo")])
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    paths = []
    for name, text in files.items():
        p = os.path.join(out_dir, name + ".setting")
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        paths.append(p)
    return paths


if __name__ == "__main__":
    for p in build_all(sys.argv[1] if len(sys.argv) > 1 else "templates"):
        print(p)
