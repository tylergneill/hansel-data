"""
XML -> plain text: write a HANSEL TEI edition back out in its plain-text form.

This is the inverse of ``tei_builder.TeiTextBuilder``. The two directions follow
the same correspondence table, ``texts/DATA_MODEL.md``; the contract is that

    txt -> XML -> txt  gives back the original txt (up to the normalisations
                       listed in DATA_MODEL.md, e.g. blank lines), and
    XML -> txt -> XML  gives back the same XML, byte for byte.

``utils/transforms/xml/roundtrip.py`` checks both over the whole corpus.

How it works
------------
The writer walks the TEI ``<body>`` once and appends to a list of output lines.
Block elements (``<div>``, ``<sp>``, ``<p>``, ``<lg>``, ``<label>``) start and end
lines; inline elements (``<stage>``, ``<seg>``, editorial markup) write their
bracket syntax around their content; the break elements decide where physical
lines end:

* ``<lb>`` ends a physical line (``break="no"`` adds the hyphen back);
* ``<pb>`` is a page marker ``<n>``: on its own line, except in a text without
  ``<lb>`` where it sits mid-line (it is followed by more text in its element);
* ``<caesura/>`` ends a physical line inside a verse half; in a line-by-line text
  the ``<lb>`` right after it does that job.

Inside ``<l>`` each new physical line gets its verse prefix: one tab, or in the
condensed format the half-verse label (``[1.1b]<TAB>``).

The XML does not say everything about the plain-text layout (see "Round trip" in
DATA_MODEL.md). Where it is silent the writer produces one canonical layout,
for example a blank line before every speaker cue (which the builder needs) and
around section and location markers.

Chāyās are not written inline: as in the project editions, they go to a companion file
``chaya/<stem>.txt``, one entry per Prakrit passage, entries separated by a blank
line, verse entries one tab-indented line per verse half.
"""
import argparse
import re
from pathlib import Path
from typing import Optional

from lxml import etree

from tei_builder import make_xml_id

XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
INDENT_RE = re.compile(r"indent\((\d+)\)")


def local(el) -> Optional[str]:
    """Local tag name of an element, or None for comments and processing instructions."""
    return etree.QName(el).localname if isinstance(el.tag, str) else None


def real_text(text: Optional[str]) -> str:
    """Text content with pretty-printing artefacts removed.

    The XML files are pretty-printed, which puts whitespace-only text containing
    a newline between elements. The builder never writes a newline into text, so
    such text is layout, not content.
    """
    if not text or (not text.strip() and "\n" in text):
        return ""
    return text


def has_location_marker(el) -> bool:
    """True if a ``[location]`` line in the plain text opened this element.

    The builder gives every element under one location the location as @n, but
    only the first gets the bare xml:id ``make_xml_id(n)``; later ones get
    ``_2``, ``_3`` ... So the bare id marks where the [location] line was.
    """
    n = el.get("n")
    return bool(n) and el.get(XML_ID) == make_xml_id(n)


def starts_with_lb(el) -> bool:
    """True if el opens with an <lb> before any text (a bare speaker cue's line)."""
    return not real_text(el.text) and len(el) > 0 and local(el[0]) == "lb"


def is_condensed_lg(lg) -> bool:
    """True if an <lg> came from the condensed verse format: its <l> carry @n,
    the half-verse letters (e.g. "ab")."""
    return any(local(c) == "l" and c.get("n") for c in lg)


def has_following_content(el) -> bool:
    """True if non-layout text follows el inside its parent element."""
    if real_text(el.tail).strip():
        return True
    for sib in el.itersiblings():
        if "".join(real_text(t) for t in sib.itertext()).strip():
            return True
    return False


class _Verse:
    """Line prefixes inside one <l>: what goes before its first physical line
    (if not written yet) and before each continuation line."""

    def __init__(self, first: Optional[str], continuations: list[str]):
        self.first = first
        self.continuations = list(continuations)

    def next_prefix(self) -> str:
        if self.first is not None:
            prefix, self.first = self.first, None
            return prefix
        return self.continuations.pop(0) if self.continuations else "\t"


class TxtWriter:
    """Writes the <body> of one HANSEL TEI edition as plain text."""

    def __init__(self, line_by_line: bool, extra_space_after_location: bool = False):
        # line_by_line: the text has an <lb> for every physical line, so page
        # markers always stand on their own line.
        self.line_by_line = line_by_line
        # extra_space_after_location: layout only; a blank line after each [location].
        self.extra_space_after_location = extra_space_after_location
        self.lines: list[str] = [""]  # the last entry is the line being written
        self.chaya: list[str] = []  # companion-file entries, in document order
        self.verse: Optional[_Verse] = None  # set while inside an <l>

    # ---- output primitives ----

    def raw(self, s: str) -> None:
        """Append s to the current line as is."""
        self.lines[-1] += s

    def write(self, s: str) -> None:
        """Append content. At the start of a line, drop the join space the
        builder put after a break and, inside a verse, add the verse prefix."""
        if not s:
            return
        if self.lines[-1] == "":
            s = s.lstrip(" ")
            if not s:
                return
            if self.verse is not None:
                s = self.verse.next_prefix() + s
        self.lines[-1] += s

    def newline(self) -> None:
        """End the current line (no-op on an empty line)."""
        if self.lines[-1] != "":
            self.lines[-1] = self.lines[-1].rstrip()
            self.lines.append("")

    def blank(self) -> None:
        """Make sure a blank line separates what follows from what came before."""
        self.newline()
        if len(self.lines) >= 2 and self.lines[-2] != "":
            self.lines.append("")

    def own_line(self, s: str) -> None:
        self.newline()
        self.raw(s)
        self.newline()

    def hyphenate(self) -> None:
        """Put back the hyphen of a word broken across lines (break="no")."""
        if self.lines[-1]:
            self.lines[-1] = self.lines[-1].rstrip() + "-"
        elif len(self.lines) >= 2:
            self.lines[-2] = self.lines[-2].rstrip() + "-"

    def text(self) -> str:
        lines = [l.rstrip() for l in self.lines]
        while lines and not lines[0]:
            lines.pop(0)
        while lines and not lines[-1]:
            lines.pop()
        return "\n".join(lines) + "\n"

    # ---- blocks ----

    def body(self, body) -> None:
        for div in body:
            if local(div) == "div":
                self.div(div)

    def div(self, div) -> None:
        if div.get("n"):  # n="" is the wrapper the builder adds when a text has no {sections}
            self.blank()
            self.own_line("{" + div.get("n") + "}")
            self.blank()
        for child in div:
            self.block(child)

    def block(self, el) -> None:
        tag = local(el)
        if tag is None:
            return
        if tag == "p":
            self.p(el)
        elif tag == "lg":
            self.lg(el)
        elif tag == "sp":
            self.sp(el)
        elif tag == "label":
            self.label(el)
        elif tag == "pb":
            self.pb(el)
        else:
            raise ValueError(f"unexpected block element <{tag}>")

    def marker(self, el) -> None:
        """Write the [location] line that opened el, if there was one."""
        if has_location_marker(el):
            self.blank()
            self.own_line(f"[{el.get('n')}]")
            if self.extra_space_after_location:
                self.blank()

    def p(self, p, on_cue_line: bool = False) -> None:
        if on_cue_line:
            if not starts_with_lb(p):
                self.raw(" ")
        else:
            self.marker(p)
            self.newline()
        self.inline(p)
        self.newline()

    def label(self, label) -> None:
        self.marker(label)
        self.blank()
        self.own_line("<" + self.render(label) + ">")
        self.blank()

    def sp(self, sp) -> None:
        """A speech: the cue "name —" opens a new block (after a blank line) and
        the speech's first paragraph or verse continues on the cue's line."""
        content = [c for c in sp if local(c) not in (None, "speaker")]
        if content:
            self.marker(content[0])
        self.blank()
        self.raw(f"{sp.get('who')} —")
        for i, child in enumerate(content):
            if i == 0 and local(child) == "p":
                self.p(child, on_cue_line=True)
            elif i == 0 and local(child) == "lg":
                if not self.line_by_line:
                    # Without <lb> the XML cannot say whether the verse began on
                    # the cue's line; it starts on the next line, as it usually does.
                    self.newline()
                self.lg(child, on_cue_line=True)
            else:
                self.block(child)
        self.newline()

    def lg(self, lg, on_cue_line: bool = False, nested: bool = False) -> None:
        if is_condensed_lg(lg):
            self.condensed_lg(lg)
            return
        if not (on_cue_line or nested):
            self.marker(lg)
            self.newline()
        # A Prakrit verse is the <lg> that carries a chāyā <lg>: the plain text wraps
        # it in ˹...˼ and keeps the chāyā in the companion file.
        ls = [c for c in lg if local(c) == "l"]
        prakrit = any(local(c) == "lg" and c.get("type") == "chāyā" for c in lg)
        for child in lg:
            tag = local(child)
            if tag is None:
                continue
            if tag == "head":
                self.write(self.render(child))
            elif tag == "l":
                self.l(child,
                       open_prakrit=prakrit and child is ls[0],
                       close_prakrit=prakrit and child is ls[-1])
            elif tag == "lg" and child.get("type") == "chāyā":
                self.chaya.append("\n".join("\t" + self.render(l) for l in child if local(l) == "l"))
            elif tag == "lg":
                self.lg(child, nested=True)
            elif tag == "trailer":
                # Text after the closing daṇḍa, on the last pāda's line.
                self.lines[-1] = self.lines[-1].rstrip()
                self.raw(" ")
                self.inline(child)
                self.newline()
            else:
                raise ValueError(f"unexpected <{tag}> in <lg>")
        self.newline()

    def l(self, l, open_prakrit=False, close_prakrit=False,
          first: Optional[str] = None, continuations: Optional[list[str]] = None) -> None:
        """One verse half. Its first line starts with N tabs (rend="indent(N)" for
        staggered dialogue verse, else 1), continuation lines with one tab.
        The condensed format passes its own label prefixes instead."""
        if first is None:
            m = INDENT_RE.fullmatch(l.get("rend") or "")
            first = "\t" * (int(m.group(1)) if m else 1)
        if open_prakrit:
            first += "˹"
        if starts_with_lb(l):
            # A bare speaker cue's line: the <lb> ends it; the tabs come after.
            self.verse = _Verse(first, continuations or [])
        else:
            self.raw(first)
            self.verse = _Verse(None, continuations or [])
        children = [c for c in l if local(c) is not None]
        final_lb = children[-1] if children and local(children[-1]) == "lb" else None
        # The closing ˼ goes after the verse's last words, before any trailing
        # run of line and page breaks.
        close_at = len(children)
        while (close_at > 0 and local(children[close_at - 1]) in ("lb", "pb")
               and not real_text(children[close_at - 1].tail).strip()):
            close_at -= 1
        self.write(real_text(l.text))
        for i, child in enumerate(children):
            if close_prakrit and i == close_at:
                self.raw("˼")
            self.inline_node(child)
            tail = real_text(child.tail)
            if child is final_lb and tail.strip() and not self.is_caesura_continuation(child):
                # Text after the verse's last line break came from a "_text" line.
                self.verse = None
                self.own_line("_" + tail.strip())
            else:
                self.write(tail)
        if close_prakrit and close_at == len(children):
            self.raw("˼")
        self.verse = None
        nxt = l.getnext()
        while nxt is not None and local(nxt) is None:
            nxt = nxt.getnext()
        if nxt is None or local(nxt) != "trailer":
            self.newline()

    @staticmethod
    def is_caesura_continuation(lb) -> bool:
        """An <lb> right after a <caesura> starts the verse half's second
        physical line; its text is verse, not a pending "_" line."""
        prev = lb.getprevious()
        while prev is not None and local(prev) is None:
            prev = prev.getprevious()
        return prev is not None and local(prev) == "caesura"

    def condensed_lg(self, lg) -> None:
        """Condensed verse format: every physical line starts with its own
        half-verse label, [1.1ab]<TAB>... An <l n="ab"> that runs over two
        physical lines came from two lines labelled a and b."""
        base = lg.get("n")
        for child in lg:
            tag = local(child)
            if tag is None:
                continue
            if tag != "l":
                raise ValueError(f"unexpected <{tag}> in condensed <lg>")
            seg = child.get("n") or ""
            breaks = sum(1 for c in child if local(c) == "caesura")
            if breaks and len(seg) == breaks + 1:
                labels = [base + letter for letter in seg]
            else:
                labels = [base + seg]
            self.newline()
            self.l(child, first=f"[{labels[0]}]\t", continuations=[f"[{x}]\t" for x in labels[1:]])

    # ---- inline content ----

    def inline(self, el) -> None:
        """Write el's mixed content (text, inline children, tails)."""
        self.write(real_text(el.text))
        for child in el:
            self.inline_node(child)
            self.write(real_text(child.tail))

    def render(self, el) -> str:
        """el's inline content as a one-line string, for labels, heads and chāyās."""
        sub = TxtWriter(self.line_by_line)  # layout options do not matter inline
        sub.chaya = self.chaya
        sub.inline(el)
        return " ".join(l.strip() for l in sub.lines if l.strip())

    def inline_node(self, el) -> None:
        tag = local(el)
        if tag is None:
            return
        if tag == "lb":
            if el.get("break") == "no":
                self.hyphenate()
            self.newline()
        elif tag == "pb":
            self.pb(el)
        elif tag == "caesura":
            if not self.line_by_line:
                self.newline()
        elif tag == "stage":
            self.write("((")
            self.inline(el)
            self.write("))")
        elif tag == "seg" and el.get("type") == "prakrit":
            self.write("˹")
            self.inline(el)
            self.write("˼")
        elif tag == "seg" and el.get("type") == "chāyā":
            self.chaya.append(self.render(el))
        elif tag == "choice":
            self.inline(el)
        elif tag in ("sic", "del"):
            self.write("≤")
            self.inline(el)
            self.write("≥")
        elif tag in ("corr", "supplied"):
            self.write("«")
            self.inline(el)
            self.write("»")
        elif tag == "unclear":
            self.write("¿")
            self.inline(el)
            self.write("¿")
        else:
            raise ValueError(f"unexpected inline element <{tag}>")

    def pb(self, pb) -> None:
        """Page marker. Mid-line only in a text without <lb>, and only when more
        text follows in the same element; otherwise on its own line."""
        marker = f"<{pb.get('n')}>"
        if not self.line_by_line and has_following_content(pb) and self.lines[-1]:
            self.raw(marker)
            return
        if pb.get("break") == "no":
            self.hyphenate()
        verse, self.verse = self.verse, None  # the marker line gets no verse prefix
        if local(pb.getparent()) == "p" and not has_following_content(pb):
            self.blank()  # a page break ending a paragraph stands apart
        self.own_line(marker)
        self.verse = verse


def convert(xml_path: Path, extra_space_after_location: bool = False) -> tuple[str, list[str]]:
    """Return (plain text, chāyā entries) for one TEI file."""
    return convert_element(etree.parse(str(xml_path)).getroot(), extra_space_after_location)


def convert_element(root, extra_space_after_location: bool = False) -> tuple[str, list[str]]:
    """Return (plain text, chāyā entries) for a TEI element containing <body>
    (the whole <TEI>, or the <text> the builder returns).
    extra_space_after_location only changes layout (see the flag in flag_map)."""
    body = root.find(".//{*}body")
    if body is None:
        return "", []
    writer = TxtWriter(line_by_line=body.find(".//{*}lb") is not None,
                       extra_space_after_location=extra_space_after_location)
    writer.body(body)
    return writer.text(), writer.chaya


def configure_cli(parser: argparse.ArgumentParser):
    parser.description = "Convert a HANSEL TEI-XML edition back into its plain-text form."
    parser.add_argument("src", type=Path, help="Source TEI-XML file")
    parser.add_argument("out", type=Path, help="Destination plain-text file")
    parser.add_argument("--chaya", action="store_true",
                        help="Also write the chāyās to the companion file chaya/<name> next to OUT.")
    parser.add_argument("--extra-space-after-location", action="store_true",
                        help="Layout: put a blank line after each [location] line.")
    # Accepted for compatibility with flag_map, which is shared with the builder;
    # the writer reads what it needs from the XML itself.
    for flag in ("--line-by-line", "--drama"):
        parser.add_argument(flag, action="store_true", help=argparse.SUPPRESS)


def cli():
    parser = argparse.ArgumentParser()
    configure_cli(parser)
    args = parser.parse_args()
    plaintext, chaya = convert(args.src, args.extra_space_after_location)
    args.out.write_text(plaintext, encoding="utf-8")
    print(f"Wrote {args.out}")
    if args.chaya and chaya:
        chaya_out = args.out.parent / "chaya" / args.out.name
        chaya_out.parent.mkdir(exist_ok=True)
        chaya_out.write_text("\n\n".join(chaya) + "\n", encoding="utf-8")
        print(f"Wrote {chaya_out}")


if __name__ == "__main__":
    cli()
