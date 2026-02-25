flag_map = {
    "bANa_kAdambarI": '--line-by-line',
    "vAkyapadIyaprameyasaMgraha": '--line-by-line --extra-space-after-location',
    "zukasaptati_s": '--line-by-line --extra-space-after-location',
    "zukasaptati_o": '--line-by-line --extra-space-after-location',
    "kRSNamizra_prabodhacandrodaya": '--drama',
}

# Maps text stem → (page_label, line_label) to override how editorial coordinates are displayed.
# E.g. ("ch", "u") renders [3,24] as "ch.3, u.24" instead of "p.3, l.24".
# When labels differ from the default "p"/"l", the coordinate system is treated as independent
# of PDF page numbering: <pb> links always use plain "p.N" and location markers never create
# inline page links.
editorial_coord_labels_map = {
    "kRSNamizra_prabodhacandrodaya": ("ch", "u"),
}
