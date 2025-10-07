document.addEventListener('DOMContentLoaded', () => {
    const transliterationSchemeSelect = document.getElementById('transliteration-scheme');
    const showAllSchemesCheckbox = document.getElementById('show-all-schemes-checkbox');
    const contentDiv = document.getElementById('content');
    if (!contentDiv) {
        return;
    }
    let originalContent = contentDiv.innerHTML;
    let transliteratedContent = {};

    const allSchemes = {
        "Roman Schemes": ["cyrillic", "hk", "iast", "iso", "itrans", "itrans_dravidian", "slp1", "velthuis", "wx"],
        "Brahmic Schemes": ["assamese", "balinese", "bengali", "devanagari", "gujarati", "javanese", "kannada", "khmer", "lao_pali", "malayalam", "mon", "oriya", "ranjana", "sinhala", "tamil"]
    };
    const defaultSchemes = ["iast", "devanagari", "hk", "itrans", "slp1", "velthuis"];
    const schemeDisplayNames = {
        "iast": "IAST",
        "devanagari": "Devanāgarī",
        "hk": "HK",
        "itrans": "ITRANS",
        "slp1": "SLP1",
        "velthuis": "Velthuis"
    };

    function populateSchemesDropdown(showAll) {
        if (!transliterationSchemeSelect) {
            return;
        }
        transliterationSchemeSelect.innerHTML = ''; // Clear existing options
        const noneOption = document.createElement('option');
        noneOption.value = 'original';
        noneOption.innerText = 'Original';
        transliterationSchemeSelect.appendChild(noneOption);

        if (showAll) {
            for (const group in allSchemes) {
                const optgroup = document.createElement('optgroup');
                optgroup.label = group;
                allSchemes[group].forEach(scheme => {
                    const option = document.createElement('option');
                    option.value = scheme;
                    option.innerText = scheme.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()); // Capitalize and replace underscores
                    optgroup.appendChild(option);
                });
                transliterationSchemeSelect.appendChild(optgroup);
            }
        } else {
            defaultSchemes.forEach(scheme => {
                const option = document.createElement('option');
                option.value = scheme;
                option.innerText = schemeDisplayNames[scheme] || scheme;
                transliterationSchemeSelect.appendChild(option);
            });
        }
    };

    function transliterate(targetScheme) {
        if (targetScheme === 'original') {
            contentDiv.innerHTML = originalContent;
            return;
        }

        if (transliteratedContent[targetScheme]) {
            contentDiv.innerHTML = transliteratedContent[targetScheme];
            return;
        }

        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = originalContent;

        const walker = document.createTreeWalker(tempDiv, NodeFilter.SHOW_TEXT, null, false);
        let node;
        while(node = walker.nextNode()) {
            // Only transliterate text that looks like IAST.
            // This is a basic check for common diacritics.
            if (/[āīūṛṝḷḹṃḥñṭḍṇśṣĀĪŪṚṜḶḸṂḤÑṬḌṆŚṢ]/.test(node.nodeValue)) {
                node.nodeValue = Sanscript.t(node.nodeValue, 'iast', targetScheme);
            }
        }
        
        transliteratedContent[targetScheme] = tempDiv.innerHTML;
        contentDiv.innerHTML = tempDiv.innerHTML;
    }

    if (transliterationSchemeSelect) {
        transliterationSchemeSelect.addEventListener('change', (e) => {
            transliterate(e.target.value);
        });
    }
    if (showAllSchemesCheckbox) {
        showAllSchemesCheckbox.addEventListener('change', (e) => {
            populateSchemesDropdown(e.target.checked);
        });
    }
    if (transliterationSchemeSelect) {
        populateSchemesDropdown(false);
    }
});
