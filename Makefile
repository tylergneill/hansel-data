regen:
	python utils/transforms/regenerate_all.py --xml

# Check the txt <-> XML round trip for every edition, in memory (writes nothing).
# Fails if any txt -> XML -> txt -> XML does not reproduce the same XML.
roundtrip:
	python utils/transforms/xml/roundtrip.py

# Validate all project-edition XML against the HANSEL schema (RNG + Schematron).
# Engines can be overridden as in utils/validation/xml/Makefile, e.g.
#   make validate JING=pyjing SAXON="python saxon_cli.py"
validate:
	$(MAKE) -C utils/validation/xml validate

# Cross-check all project-edition XML against stock TEI P5 tei_all.
validate-tei-all:
	$(MAKE) -C utils/validation/xml validate-tei-all

# Regenerate everything from the txt sources, then run both validations
# (HANSEL schema and tei_all).
regen-and-validate-both: regen validate validate-tei-all

.PHONY: regen roundtrip validate validate-tei-all regen-and-validate-both
