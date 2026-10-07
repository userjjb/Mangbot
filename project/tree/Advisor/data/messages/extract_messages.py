#!/usr/bin/env python3
"""Extract every player-facing message call from the MAngband 1.5 server source.

Writes server_messages.csv: id, file, line, function, call, format (the C string literal(s),
concatenated), args (rest of the call, trimmed), msg_type (MSG_* constant if the call has one).
Usage: python3 extract_messages.py
"""
import csv, glob, os, re

SRC = "/projectnb/jbrcs/mangband/github/src/server"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server_messages.csv")
CALL = re.compile(r"\b(msg_print|msg_format|msg_print_near|msg_format_near|msg_broadcast|msg_spell|"
                  r"msg_misc|msg_prayer|msg_print_aux|msg_format_type|msg_format_complex_near|"
                  r"msg_print_p|msg_format_p)\s*\(")
FUNC = re.compile(r"^[A-Za-z_][\w \*]*\b(\w+)\s*\([^;]*$")
STR = re.compile(r'"((?:[^"\\]|\\.)*)"')

rows, n = [], 0
for path in sorted(glob.glob(os.path.join(SRC, "*.c"))):
    lines = open(path, encoding="latin-1").read().split("\n")
    func = ""
    for i, line in enumerate(lines):
        m = FUNC.match(line)
        if m and not line.strip().startswith(("if", "while", "for", "switch", "return", "else")):
            func = m.group(1)
        for c in CALL.finditer(line):
            # gather the call text up to the matching ')' (may span lines)
            text, depth, j, k = "", 0, i, c.end() - 1
            while j < len(lines) and j < i + 8:
                seg = lines[j][k:] if j == i else lines[j]
                for ch in seg:
                    text += ch
                    if ch == "(":
                        depth += 1
                    elif ch == ")":
                        depth -= 1
                        if depth == 0:
                            break
                if depth == 0:
                    break
                j += 1
                text += " "
            fmt = "".join(STR.findall(text))
            mtype = ",".join(re.findall(r"\bMSG_[A-Z_0-9]+", text))
            args = re.sub(r"\s+", " ", STR.sub('""', text))[:200]
            n += 1
            rows.append(dict(id=n, file=os.path.basename(path), line=i + 1, function=func,
                             call=c.group(1), format=fmt, args=args, msg_type=mtype))
with open(OUT, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
print(f"{len(rows)} message calls -> {OUT}; with no string literal: {sum(1 for r in rows if not r['format'])}")
