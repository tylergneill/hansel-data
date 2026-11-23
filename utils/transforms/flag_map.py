# Per-text CLI flags for convert_plaintext_to_xml.py and convert_xml_to_html.py.
# Texts are built line by line (an <lb> for every physical line, any coordinate system)
# unless marked --no-line-by-line, for texts whose plain-text lines do not follow printed
# lines (e.g. one line per speech).
# --drama and line-by-line are orthogonal: a drama text can be either.
# --drama enables speech/stage-direction/Prakrit-chāyā parsing; it says nothing about coords.
# --hide-milestones is display-only: <label> stays in the XML, hidden at render time.
flag_map = {
    "bANa_kAdambarI": '--hide-milestones',
    "kumArilabhaTTa_zlokavArttika": '--no-line-by-line',
    "kRSNamizra_prabodhacandrodaya": '--drama --chaya --no-line-by-line',
    "bhagavadajjuka": '--drama --chaya',
    "bhAskarabhaTTa_unmattarAghava": '--drama --chaya',
    "virUpAkSadeva_unmattarAghava": '--drama --chaya',
}


def is_line_by_line(flags: str) -> bool:
    """True unless the text's flags say --no-line-by-line (the default is line by line)."""
    return "--no-line-by-line" not in flags.split()

# Maps text stem → (page_label, line_label) to override how editorial coordinates are displayed.
# E.g. ("ch", "u") renders [3,24] as "ch.3, u.24" instead of "p.3, l.24".
# When labels differ from the default "p"/"l", the coordinate system is treated as independent
# of PDF page numbering: <pb> links always use plain "p.N" and location markers never create
# inline page links.
# NOTE: this is independent of flag_map. A drama text with [page,line] coords will have
# --drama in flag_map but no entry here (uses default "p"/"l" labels).
editorial_coord_labels_map = {
    "kRSNamizra_prabodhacandrodaya": ("ch", "u"),
}
