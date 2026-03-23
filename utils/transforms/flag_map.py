# Per-text CLI flags for convert_plaintext_to_xml.py and convert_xml_to_html.py.
# --drama and --line-by-line are orthogonal: a drama text can have either, both, or neither.
# --drama enables speech/stage-direction/Prakrit-chāyā parsing; it says nothing about coords.
# --line-by-line emits <lb> for every physical source line; it works with any coordinate system.
flag_map = {
    "bANa_kAdambarI": '--line-by-line',
    "vAkyapadIyaprameyasaMgraha": '--line-by-line --extra-space-after-location',
    "zukasaptati_s": '--line-by-line --extra-space-after-location',
    "zukasaptati_o": '--line-by-line --extra-space-after-location',
    "kRSNamizra_prabodhacandrodaya": '--drama --chaya',
    "bhagavadajjuka": '--drama --line-by-line --chaya',
}

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
