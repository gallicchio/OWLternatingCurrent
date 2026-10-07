"""A small reader for KiCad's s-expression files.

    parse(text) -> a list of nodes.  A node is a list whose items are nodes or
    tokens; a token is ("str", text) for a quoted string or ("atom", text) for
    anything else.

    head(node)          the node's name, e.g. "symbol" for (symbol ...)
    kids(node, name)    its children called `name`
    kid(node, name)     the first of them, or None
    val(node, i=1)      the text of item i
    num(node, i)        item i as a float
"""


def parse(text):
    toks, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c in "()":
            toks.append(c)
            i += 1
        elif c == '"':
            j, buf = i + 1, []
            while text[j] != '"':
                if text[j] == "\\":
                    j += 1
                    buf.append({"n": "\n", "t": "\t"}.get(text[j], text[j]))
                else:
                    buf.append(text[j])
                j += 1
            toks.append(("str", "".join(buf)))
            i = j + 1
        elif c.isspace():
            i += 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in '()"':
                j += 1
            toks.append(("atom", text[i:j]))
            i = j
    pos = [0]

    def read():
        t = toks[pos[0]]
        pos[0] += 1
        if t == "(":
            out = []
            while toks[pos[0]] != ")":
                out.append(read())
            pos[0] += 1
            return out
        if t == ")":
            raise ValueError("unbalanced parenthesis")
        return t
    out = []
    while pos[0] < len(toks):
        out.append(read())
    return out


def head(node):
    if isinstance(node, list) and node and isinstance(node[0], tuple):
        return node[0][1]
    return None


def kids(node, name):
    return [c for c in node if isinstance(c, list) and head(c) == name]


def kid(node, name):
    k = kids(node, name)
    return k[0] if k else None


def val(node, i=1):
    v = node[i]
    return v[1] if isinstance(v, tuple) else v


def num(node, i):
    return float(val(node, i))


def quote(s):
    return '"%s"' % (str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n"))


def ser(node, indent=0):
    """Write a node back as text, one child list per line, tabs for indent
    (KiCad's own layout, so a regenerated file diffs cleanly)."""
    pad = "\t" * indent
    if isinstance(node, tuple):
        return quote(node[1]) if node[0] == "str" else node[1]
    if all(not isinstance(c, list) for c in node):
        return pad + "(" + " ".join(ser(c) for c in node) + ")"
    out = [pad + "(" + ser(node[0])]
    inline = []
    for c in node[1:]:
        if isinstance(c, list):
            if inline:
                out[-1] += " " + " ".join(inline)
                inline = []
            out.append(ser(c, indent + 1))
        else:
            inline.append(ser(c))
    if inline:
        out[-1] += " " + " ".join(inline)
    out.append(pad + ")")
    return "\n".join(out)
