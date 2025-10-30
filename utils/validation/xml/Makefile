# ===== config =====
XML_DIR ?= ../../../texts/project_editions/xml
RNG     ?= schemas/sarit.rng
SCH     ?= schemas/sarit.isosch
SAXON   ?= saxon
JING    ?= jing
PYTHON  ?= python3

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

FAIL_LOG := $(BUILD_DIR)/failed.txt
JING_LOG := $(BUILD_DIR)/jing.raw

.PHONY: all fetch-skeleton dirs prep validate summary clean compare

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

prep: dirs
	@rm -f $(FAIL_LOG) $(JING_LOG)
	@touch $(FAIL_LOG) $(JING_LOG)

# Compile Schematron once → validator XSLT
$(BUILD_DIR)/validator.xsl: $(SKEL_XSLS) $(SCH) | dirs
	@$(SAXON) -xsl:$(SKEL_DIR)/iso_dsdl_include.xsl    -s:$(SCH)              -o:$(BUILD_DIR)/step1.sch >/dev/null 2>&1
	@$(SAXON) -xsl:$(SKEL_DIR)/iso_abstract_expand.xsl  -s:$(BUILD_DIR)/step1.sch -o:$(BUILD_DIR)/step2.sch >/dev/null 2>&1
	@$(SAXON) -xsl:$(SKEL_DIR)/iso_svrl_for_xslt2.xsl   -s:$(BUILD_DIR)/step2.sch -o:$@                  >/dev/null 2>&1

# Main target
validate: prep $(BUILD_DIR)/validator.xsl $(REPORTS) summary

# Per-file: run RNG + Schematron quietly, print single status line
$(REPORT_DIR)/%.svrl.xml: $(XML_DIR)/%.xml $(BUILD_DIR)/validator.xsl | dirs
	@file=$<; report=$@; status=""; \
	echo "### FILE $$file" >>$(JING_LOG); \
	$(JING) "$(RNG)" "$$file" >>$(JING_LOG) 2>&1 || status="RNG FAIL"; \
	$(SAXON) -xsl:$(BUILD_DIR)/validator.xsl -s:$$file -o:$$report >/dev/null 2>&1 || status="$${status} PIPE FAIL"; \
	if grep -q "<svrl:failed-assert" $$report 2>/dev/null; then status="$${status} SCH FAIL"; fi; \
	if [ -n "$$status" ]; then \
	  echo "❌ $$file  — $${status:-error}" | tee -a $(FAIL_LOG); \
	else \
	  echo "✅ $$file  — OK"; \
	fi

summary:
	@if [ -s $(FAIL_LOG) ]; then \
	  echo "⚠️  Some files failed. See $(FAIL_LOG) for a summary."; \
	else \
	  echo "✅  All XML files passed RNG and Schematron."; \
	fi

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
