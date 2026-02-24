# Drama h2 Generation — Analysis & Fix Plan

## Root cause: two independent problems

### Problem 1: Spurious duplicate h2s (e.g. "ch.1, u.16" × 3)

A single speech can contain **multiple `<lg n="1,16">` elements** at the *same* location
(two consecutive verses at the same location both get `n="1,16"`).
My current `<sp>` handler emits an `<h2>` for *every* location-marked child, so the
same location fires multiple times within one speech.

Fix (HTML converter only): track the last-emitted location inside the `<sp>` loop and
skip if the location hasn't changed.

```python
last_sp_location = None
n_attr = sp_child.get("n")
if n_attr and ',' in n_attr and n_attr != last_sp_location:
    speech_div = None
    speech_div_plain = None
    self._emit_location_h2(content_div, n_attr)
    last_sp_location = n_attr
```

---

### Problem 2: Missing h2s for prose-only speeches (e.g. naṭī's short replies)

In the plaintext, **every** speaker change is preceded by a `[x,y]` location marker:

```
[1,9]
naṭī — ˹esa mhi...˼
```

But in `tei_builder.py`, the `[1,9]` marker calls `_open_location("1,9")` which creates
a `<p n="1,9">` element. Then `_open_sp("naṭī")` calls `_close_p()`, which **removes**
that empty `<p>` (it has no content yet). The location is then silently discarded.

The first `<p>` inside naṭī's `<sp>` is created by `_open_location_for_sp()`, which
creates a **bare** `<p>` with no `n` attribute — so the location `1,9` is lost from
the XML entirely.

Fix (tei_builder.py): in `_open_location_for_sp()`, if `s.current_loc_label` is set,
apply it to the new `<p>` as `n` and `xml:id` (just like `_open_location` does),
then clear the consumed flag so subsequent verses in the same speech still pick up
the location from `current_loc_label` as they do today.

```python
def _open_location_for_sp(self) -> None:
    """Open a <p> inside the current <sp>.
    If current_loc_label is set (a [x,y] marker just preceded this speaker),
    stamp the location onto the <p> so the HTML converter can emit an <h2>."""
    s = self.state
    self._flush_verse_group_buffer()
    self._close_p()
    self._close_lg()
    attrs = {}
    if s.current_loc_label is not None and ',' in s.current_loc_label:
        attrs["n"] = s.current_loc_label
        attrs[f"{{{_XML_NS}}}id"] = self._next_loc_xml_id()
        # DO NOT clear current_loc_label — verses in this speech still need it
    s.current_p = etree.SubElement(s.current_sp, "p", attrs)
    s.last_tail_text_sink = None
    s.prev_line_hyphen = False
```

After this fix, naṭī's `<sp>` would have `<p n="1,9" xml:id="p1_l9">` as its first
child, and the HTML converter's existing location-detection code (`n_attr and ',' in
n_attr`) would fire correctly — emitting one `<h2>` for the start of that speech.

---

## Summary of all changes needed

| File | Change |
|------|--------|
| `tei_builder.py` | `_open_location_for_sp()`: stamp `current_loc_label` onto the first `<p>` when it is set |
| `convert_xml_to_html.py` | `<sp>` handler: deduplicate — only emit `<h2>` when location changes (track `last_sp_location`) |

The XML files must be **regenerated** after the tei_builder change so that prose-only
speeches get their location attribute.

---

## What the HTML structure will look like after both fixes

For each `[x,y]` in the plaintext (one per speaker change, one per stage direction,
one per mid-speech location jump), there will be exactly one `<h2 class="location-marker">`.
Consecutive verses at the same location (e.g. two `<lg n="1,16">`) produce only one h2.
