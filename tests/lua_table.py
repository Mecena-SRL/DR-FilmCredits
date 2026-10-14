"""Parser minimale della sintassi a tabelle Lua usata da Fusion (.comp/.setting).
Serve solo ai test: verifica che i file generati siano sintatticamente validi e
permette di ispezionarne il contenuto come strutture Python."""

import re

TOKEN = re.compile(r'\s*(?:(--[^\n]*)|("(?:\\.|[^"\\])*")|(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)|([A-Za-z_][A-Za-z0-9_.]*)|(\[|\]|\{|\}|=|,|\(|\)))')


class LuaSyntaxError(ValueError):
    pass


def tokenize(text):
    pos, out = 0, []
    text = text.rstrip()
    while pos < len(text):
        m = TOKEN.match(text, pos)
        if not m or m.end() == pos:
            raise LuaSyntaxError("Token non valido a %d: %r" % (pos, text[pos:pos + 30]))
        pos = m.end()
        if m.group(1):
            continue
        if m.group(2):
            out.append(("str", bytes(m.group(2)[1:-1], "utf-8").decode("unicode_escape").encode("latin-1").decode("utf-8")))
        elif m.group(3):
            out.append(("num", float(m.group(3))))
        elif m.group(4):
            out.append(("id", m.group(4)))
        else:
            out.append(("sym", m.group(5)))
    return out


class Parser(object):
    def __init__(self, toks):
        self.t, self.i = toks, 0

    def peek(self, k=0):
        return self.t[self.i + k] if self.i + k < len(self.t) else ("eof", None)

    def eat(self, kind, val=None):
        tok = self.peek()
        if tok[0] != kind or (val is not None and tok[1] != val):
            raise LuaSyntaxError("Atteso %s %s, trovato %s" % (kind, val, tok))
        self.i += 1
        return tok

    def value(self):
        tok = self.peek()
        if tok[0] in ("str", "num"):
            self.i += 1
            return tok[1]
        if tok == ("sym", "{"):
            return self.table()
        if tok[0] == "id":
            self.i += 1
            if tok[1] in ("true", "false", "nil"):
                return {"true": True, "false": False, "nil": None}[tok[1]]
            if self.peek() == ("sym", "("):  # ordered()
                self.eat("sym", "(")
                self.eat("sym", ")")
                t = self.table()
                return t
            if self.peek() == ("sym", "{"):  # Constructor { ... }
                t = self.table()
                t["__class__"] = tok[1]
                return t
            if self.peek()[0] == "str":  # FuID "x"
                return self.value()
            return tok[1]
        raise LuaSyntaxError("Valore inatteso %s" % (tok,))

    def table(self):
        self.eat("sym", "{")
        out, idx = {}, 1
        while self.peek() != ("sym", "}"):
            if self.peek()[0] == "id" and self.peek(1) == ("sym", "="):
                k = self.eat("id")[1]
                self.eat("sym", "=")
                out[k] = self.value()
            elif self.peek() == ("sym", "["):
                self.eat("sym", "[")
                k = self.value()
                self.eat("sym", "]")
                self.eat("sym", "=")
                out[k] = self.value()
            else:
                out[idx] = self.value()
                idx += 1
            if self.peek() == ("sym", ","):
                self.eat("sym", ",")
            elif self.peek() != ("sym", "}"):
                raise LuaSyntaxError("Atteso ',' o '}' trovato %s" % (self.peek(),))
        self.eat("sym", "}")
        return out


def parse(text):
    p = Parser(tokenize(text))
    v = p.value()
    if p.peek()[0] != "eof":
        raise LuaSyntaxError("Contenuto extra dopo la tabella: %s" % (p.peek(),))
    return v
