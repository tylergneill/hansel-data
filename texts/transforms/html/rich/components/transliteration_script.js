document.addEventListener('DOMContentLoaded', () => {
    const transliterationSchemeSelect = document.getElementById('transliteration-scheme');
    const showAllSchemesCheckbox = document.getElementById('show-all-schemes-checkbox');
    const contentDiv = document.getElementById('content');

    if (!contentDiv || !transliterationSchemeSelect) {
        return;
    }

    // Store the original state of the content
    const originalContent = contentDiv.innerHTML;
    // Cache for already transliterated content
    const transliteratedContent = {};

    const allSchemes = {
        "Roman Schemes": ["hk", "iast", "iso", "itrans", "slp1", "velthuis", "wx"],
        "Brahmic Schemes": ["bengali", "devanagari", "gujarati", "kannada", "malayalam", "oriya", "sinhala", "tamil"]
    };
    const defaultSchemes = ["iast", "devanagari", "hk", "itrans"];
    const schemeDisplayNames = {
        "iast": "IAST (Original)", // Clarify that IAST is the original
        "hk": "HK",
        "itrans": "ITRANS",
        "slp1": "SLP1",
        "velthuis": "Velthuis",
        "iso": "ISO 15919",
        "wx": "WX"
    };

    function populateSchemesDropdown(showAll) {
        transliterationSchemeSelect.innerHTML = ''; // Clear existing options

        if (showAll) {
            for (const group in allSchemes) {
                const optgroup = document.createElement('optgroup');
                optgroup.label = group;
                allSchemes[group].forEach(scheme => {
                    const option = document.createElement('option');
                    option.value = scheme;
                    option.innerText = schemeDisplayNames[scheme] || scheme.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                    optgroup.appendChild(option);
                });
                transliterationSchemeSelect.appendChild(optgroup);
            }
        } else {
            defaultSchemes.forEach(scheme => {
                const option = document.createElement('option');
                option.value = scheme;
                option.innerText = schemeDisplayNames[scheme] || scheme.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                transliterationSchemeSelect.appendChild(option);
            });
        }
    }

    function transliterate(targetScheme) {
        // If target is IAST, restore original content
        if (targetScheme === 'iast') {
            contentDiv.innerHTML = originalContent;
            return;
        }

        // If we have cached this transliteration, use it
        if (transliteratedContent[targetScheme]) {
            contentDiv.innerHTML = transliteratedContent[targetScheme];
            return;
        }

        // Otherwise, perform transliteration
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = originalContent;

        const walker = document.createTreeWalker(tempDiv, NodeFilter.SHOW_TEXT, null, false);
        let node;
        while(node = walker.nextNode()) {
            if (/[āīūṛṝḷḹṃḥñṭḍṇśṣĀĪŪṚṜḶḸṂḤÑṬḌṆŚṢ]/.test(node.nodeValue)) {
                node.nodeValue = Sanscript.t(node.nodeValue, 'iast', targetScheme);
            }
        }
        
        // Cache and set the new content
        transliteratedContent[targetScheme] = tempDiv.innerHTML;
        contentDiv.innerHTML = tempDiv.innerHTML;
    }

    // --- Event Listeners ---
    transliterationSchemeSelect.addEventListener('change', (e) => {
        const selectedScheme = e.target.value;
        localStorage.setItem('selectedTransliterationScheme', selectedScheme);
        transliterate(selectedScheme);
    });

    showAllSchemesCheckbox.addEventListener('change', (e) => {
        const showAll = e.target.checked;
        localStorage.setItem('showAllTransliterationSchemes', showAll);
        // Repopulate and restore selection
        const currentSelection = transliterationSchemeSelect.value;
        populateSchemesDropdown(showAll);
        transliterationSchemeSelect.value = currentSelection;
        // If the current selection is not in the new list, it will reset. This is acceptable.
    });

    // --- Initial Page Load ---
    const savedScheme = localStorage.getItem('selectedTransliterationScheme') || 'iast';
    const savedShowAll = localStorage.getItem('showAllTransliterationSchemes') === 'true';

    showAllSchemesCheckbox.checked = savedShowAll;
    populateSchemesDropdown(savedShowAll);
    
    // Set dropdown to the saved scheme
    transliterationSchemeSelect.value = savedScheme;
    
    // If the saved scheme is not the default, transliterate
    if (savedScheme !== 'iast') {
        transliterate(savedScheme);
    }
});