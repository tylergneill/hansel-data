# HANSEL XML validation: RELAX NG (Jing) + ISO Schematron (Saxon) for every project edition.
#
#   make validate          check all XML against the HANSEL schema; exits 1 on any failure
#   make validate-tei-all  cross-check all XML against stock TEI P5 tei_all (RELAX NG)
#   make schemas           recompile schemas/hansel.odd -> hansel.rng + hansel.isosch
#
# Engines default to the Homebrew CLIs (jing, saxon). For a pip-only setup
# (jingtrang + saxonche, in the repo's requirements.txt; pyjing needs Java, saxonche doesn't):
#   make validate JING=pyjing SAXON="python saxon_cli.py"
# To run the old SARIT check instead:
#   make validate RNG=schemas/sarit.rng SCH=schemas/sarit.isosch

# ===== config =====
XML_DIR ?= ../../../texts/project_editions/xml
RNG     ?= schemas/hansel.rng
SCH     ?= schemas/hansel.isosch
TEI_ALL_RNG ?= schemas/tei_all.rng
SAXON   ?= saxon
JING    ?= jing
PYTHON  ?= python3

# Pinned inputs for compiling the ODD (keep in step with compile_odd.py).
TEI_STYLESHEETS_VERSION := 7.58.0
TEI_P5_VERSION          := 4.10.2
CACHE_DIR       := .cache
STYLESHEETS_ZIP := $(CACHE_DIR)/tei-xsl-$(TEI_STYLESHEETS_VERSION).zip
STYLESHEETS_DIR := $(CACHE_DIR)/tei-xsl-$(TEI_STYLESHEETS_VERSION)
P5SUBSET        := $(CACHE_DIR)/p5subset-$(TEI_P5_VERSION).xml
STYLESHEETS_URL := https://github.com/TEIC/Stylesheets/releases/download/v$(TEI_STYLESHEETS_VERSION)/tei-xsl-$(TEI_STYLESHEETS_VERSION).zip
# Single files from TEI's versioned Vault: byte-identical to the 333 MB release zip's copies.
TEI_VAULT_URL   := https://www.tei-c.org/Vault/P5/$(TEI_P5_VERSION)/xml/tei
P5SUBSET_URL    := $(TEI_VAULT_URL)/odd/p5subset.xml
TEI_ALL_URL     := $(TEI_VAULT_URL)/custom/schema/relaxng/tei_all.rng

# Robust default for skeleton dir even if SKEL="" in env
DEFAULT_SKEL := schemas/iso-schematron
SKEL         ?=
SKEL_DIR     := $(if $(strip $(SKEL)),$(SKEL),$(DEFAULT_SKEL))

OUT_DIR    ?= cli
BUILD_DIR  := $(OUT_DIR)/build
REPORT_DIR := $(OUT_DIR)/reports

OXYGEN_DIR        := oxygen_comparison
CLI_CSV           := $(OXYGEN_DIR)/makefile_fails.csv
OXYGEN_LOG        := $(OXYGEN_DIR)/oxygen_logs.txt
OXYGEN_CSV        := $(OXYGEN_DIR)/oxygen_fails.csv
COMPARE_ONLY_MAKE := $(OXYGEN_DIR)/only_makefile.csv
COMPARE_ONLY_OXY  := $(OXYGEN_DIR)/only_oxygen.csv
COMPARE_SHARED    := $(OXYGEN_DIR)/shared_both.csv
OXYGEN_LOG_PLACEHOLDER := $(OXYGEN_DIR)/oxygen_logs.txt

# ===== inputs =====
XMLS    := $(wildcard $(XML_DIR)/*.xml)
REPORTS := $(patsubst $(XML_DIR)/%.xml,$(REPORT_DIR)/%.svrl.xml,$(XMLS))

SKEL_XSLS := \
  $(SKEL_DIR)/iso_dsdl_include.xsl \
  $(SKEL_DIR)/iso_abstract_expand.xsl \
  $(SKEL_DIR)/iso_svrl_for_xslt2.xsl \
  $(SKEL_DIR)/iso_schematron_skeleton_for_saxon.xsl

FAIL_LOG  := $(BUILD_DIR)/failed.txt
JING_LOG  := $(BUILD_DIR)/jing.raw
# One compiled validator per Schematron file, so switching SCH= never reuses a stale one.
VALIDATOR := $(BUILD_DIR)/$(basename $(notdir $(SCH))).validator.xsl

.PHONY: all fetch-skeleton dirs prep validate summary validate-tei-all schemas fetch-tei-all clean compare

all: validate

# One-time: download the ISO Schematron skeleton XSLTs
fetch-skeleton:
	mkdir -p $(SKEL_DIR)
	curl -fsSL -o $(SKEL_DIR)/iso_dsdl_include.xsl \
	  https://raw.githubusercontent.com/Schematron/schematron/master/trunk/schematron/code/iso_dsdl_include.xsl
	curl -fsSL -o $(SKEL_DIR)/iso_abstract_expand.xsl \
	  https://raw.githubusercontent.com/Schematron/schematron/master/trunk/schematron/code/iso_abstract_expand.xsl
	curl -fsSL -o $(SKEL_DIR)/iso_svrl_for_xslt2.xsl \
	  https://raw.githubusercontent.com/Schematron/schematron/master/trunk/schematron/code/iso_svrl_for_xslt2.xsl
	curl -fsSL -o $(SKEL_DIR)/iso_schematron_skeleton_for_saxon.xsl \
	  https://raw.githubusercontent.com/Schematron/schematron/master/trunk/schematron/code/iso_schematron_skeleton_for_saxon.xsl

dirs:
	mkdir -p $(BUILD_DIR) $(REPORT_DIR)

# Start every run clean: old reports would otherwise make Make skip files whose XML
# is unchanged, so an earlier failure could go unreported.
prep: dirs
	@rm -f $(FAIL_LOG) $(JING_LOG) $(REPORT_DIR)/*.svrl.xml
	@touch $(FAIL_LOG) $(JING_LOG)

# Compile Schematron once → validator XSLT
# (The old skeleton prints a harmless "unrecognized element ... param" warning for
# schemas compiled with newer TEI Stylesheets; the checks themselves run correctly.)
$(VALIDATOR): $(SKEL_XSLS) $(SCH) | dirs
	@$(SAXON) -xsl:$(SKEL_DIR)/iso_dsdl_include.xsl    -s:$(SCH)              -o:$(BUILD_DIR)/step1.sch >/dev/null 2>&1
	@$(SAXON) -xsl:$(SKEL_DIR)/iso_abstract_expand.xsl  -s:$(BUILD_DIR)/step1.sch -o:$(BUILD_DIR)/step2.sch >/dev/null 2>&1
	@$(SAXON) -xsl:$(SKEL_DIR)/iso_svrl_for_xslt2.xsl   -s:$(BUILD_DIR)/step2.sch -o:$@                  >/dev/null 2>&1

# Main target
validate: prep $(VALIDATOR) $(REPORTS) summary

# Per-file: run RNG + Schematron quietly, print single status line (plus the first
# errors when a file fails, so CI logs show why). Schematron fails a file on a failed
# <assert> and also on a fired <report>: TEI writes many of its rules as reports
# (e.g. "@when cannot be used with @from/@to"), which a check for failed-assert
# alone would miss.
$(REPORT_DIR)/%.svrl.xml: $(XML_DIR)/%.xml $(VALIDATOR) prep | dirs
	@file=$<; report=$@; status=""; \
	echo "### FILE $$file" >>$(JING_LOG); \
	rng_out=$$($(JING) "$(RNG)" "$$file" 2>&1) || status="RNG FAIL"; \
	printf '%s\n' "$$rng_out" >>$(JING_LOG); \
	$(SAXON) -xsl:$(VALIDATOR) -s:$$file -o:$$report >/dev/null 2>&1 || status="$${status} PIPE FAIL"; \
	if grep -q -E "<svrl:(failed-assert|successful-report)" $$report 2>/dev/null; then status="$${status} SCH FAIL"; fi; \
	if [ -n "$$status" ]; then \
	  echo "❌ $$file  — $${status:-error}" | tee -a $(FAIL_LOG); \
	  if [ -n "$$rng_out" ]; then printf '%s\n' "$$rng_out" | head -n 10 | sed 's/^/     /'; fi; \
	  grep -o '<svrl:text>[^<]*' $$report 2>/dev/null | sed 's/<svrl:text>/     SCH: /' | head -n 10; \
	else \
	  echo "✅ $$file  — OK"; \
	fi

summary: $(REPORTS)
	@if [ -s $(FAIL_LOG) ]; then \
	  echo "⚠️  Some files failed. See $(FAIL_LOG) for a summary."; \
	  exit 1; \
	else \
	  echo "✅  All XML files passed RNG and Schematron."; \
	fi

# Cross-check against stock TEI P5 tei_all (RELAX NG only). HANSEL's schema is a
# customization of TEI, so anything it accepts should be valid TEI too; this catches
# the builder emitting something that HANSEL's schema happens to allow but TEI doesn't.
validate-tei-all:
	@failed=0; \
	for file in $(XMLS); do \
	  if out=$$($(JING) "$(TEI_ALL_RNG)" "$$file" 2>&1); then \
	    echo "✅ $$file  — tei_all OK"; \
	  else \
	    echo "❌ $$file  — tei_all FAIL"; printf '%s\n' "$$out" | head -n 10 | sed 's/^/     /'; failed=1; \
	  fi; \
	done; \
	if [ $$failed -ne 0 ]; then echo "⚠️  Some files are not valid against tei_all."; exit 1; fi; \
	echo "✅  All XML files are valid against tei_all."

# ===== schema compilation (only needed when hansel.odd changes) =====
$(STYLESHEETS_DIR)/xml/tei/stylesheet/odds/odd2odd.xsl:
	mkdir -p $(CACHE_DIR)
	[ -f $(STYLESHEETS_ZIP) ] || curl -fsSL -o $(STYLESHEETS_ZIP) $(STYLESHEETS_URL)
	unzip -q -o $(STYLESHEETS_ZIP) -d $(STYLESHEETS_DIR)

$(P5SUBSET):
	mkdir -p $(CACHE_DIR)
	curl -fsSL -o $@ $(P5SUBSET_URL)

schemas: $(STYLESHEETS_DIR)/xml/tei/stylesheet/odds/odd2odd.xsl $(P5SUBSET)
	$(PYTHON) compile_odd.py schemas/hansel.odd \
	  --stylesheets $(STYLESHEETS_DIR)/xml/tei/stylesheet --p5subset $(P5SUBSET)

# Refresh the committed copy of tei_all.rng (only when bumping TEI_P5_VERSION).
fetch-tei-all:
	curl -fsSL -o $(TEI_ALL_RNG) $(TEI_ALL_URL)

clean:
	rm -rf $(BUILD_DIR) $(REPORT_DIR)
	rm -f $(CLI_CSV) $(OXYGEN_CSV) $(COMPARE_ONLY_MAKE) $(COMPARE_ONLY_OXY) $(COMPARE_SHARED)
	rm -f $(OXYGEN_DIR)/*.txt $(OXYGEN_DIR)/*.csv
	touch $(OXYGEN_LOG_PLACEHOLDER)

$(CLI_CSV): $(OXYGEN_DIR)/make_reports_to_csv.py $(REPORTS) $(JING_LOG)
	$(PYTHON) $(OXYGEN_DIR)/make_reports_to_csv.py

$(OXYGEN_CSV): $(OXYGEN_LOG) $(OXYGEN_DIR)/oxygen_logs_to_csv_blocks.py
	$(PYTHON) $(OXYGEN_DIR)/oxygen_logs_to_csv_blocks.py

$(COMPARE_SHARED) $(COMPARE_ONLY_MAKE) $(COMPARE_ONLY_OXY): $(OXYGEN_DIR)/compare_fail_csvs.py $(CLI_CSV) $(OXYGEN_CSV)
	$(PYTHON) $(OXYGEN_DIR)/compare_fail_csvs.py

compare: validate $(CLI_CSV) $(OXYGEN_CSV) $(COMPARE_SHARED) $(COMPARE_ONLY_MAKE) $(COMPARE_ONLY_OXY)
	@echo "Comparison outputs ready under $(OXYGEN_DIR)/"
