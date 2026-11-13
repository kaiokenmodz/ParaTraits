"""Tiny reader for Paralives .setting files (indentation-based manifest format).

Line = <indent><op><field>[:<arg>]; ops: # object, = field, s array size, i index,
g/@ element by GUID, + add, - / _ remove, ^ dict key.
parse() returns a tree of Node(op, name, arg, children)."""
import sys, io


class Node:
    __slots__ = ("op", "name", "arg", "children", "parent", "line")

    def __init__(self, op, name, arg, parent, line):
        self.op, self.name, self.arg, self.parent, self.line = op, name, arg, parent, line
        self.children = []

    def get(self, field):
        for c in self.children:
            if c.op == "=" and c.name == field:
                return c
        return None

    def val(self, field, default=None):
        n = self.get(field)
        return n.arg if n is not None and n.arg is not None else default

    def items(self, field):
        """Array elements of a field (i/g/@ children)."""
        n = self.get(field)
        return [c for c in (n.children if n else []) if c.op in "ig@+"]

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()

    def dump(self, depth=0, maxdepth=99, out=None):
        out = out if out is not None else []
        if depth > maxdepth:
            return out
        out.append("  " * depth + self.op + self.name + (":" + self.arg if self.arg is not None else ""))
        for c in self.children:
            c.dump(depth + 1, maxdepth, out)
        return out


def parse(path):
    root = Node("#", "root", None, None, 0)
    stack = [(-1, root)]
    with io.open(path, encoding="utf-8-sig") as f:
        for no, raw in enumerate(f, 1):
            line = raw.rstrip("\r\n")
            if not line.strip():
                continue
            ind = len(line) - len(line.lstrip(" "))
            s = line.lstrip(" ")
            op, rest = s[0], s[1:]
            if ":" in rest:
                name, arg = rest.split(":", 1)
            else:
                name, arg = rest, None
            while stack and stack[-1][0] >= ind:
                stack.pop()
            parent = stack[-1][1]
            n = Node(op, name, arg, parent, no)
            parent.children.append(n)
            stack.append((ind, n))
    return root


if __name__ == "__main__":
    r = parse(sys.argv[1])
    print("\n".join(r.dump(maxdepth=int(sys.argv[2]) if len(sys.argv) > 2 else 3)))
