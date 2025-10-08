function toggleBreaks(checkbox) { document.getElementById("content").classList.toggle("show-breaks", checkbox.checked); }
function toggleToc() { document.getElementById('toc').classList.toggle('expanded'); }
function toggleMetadata() { document.getElementById('metadata').classList.toggle('expanded'); }

function toggleViewMode(checkbox) {
    document.body.classList.toggle('simple-view', checkbox.checked);
    const toc = document.getElementById('toc');
    const metadata = document.getElementById('metadata');
    const richTextToggles = document.querySelectorAll('.rich-text-toggle');

    if (checkbox.checked) {
        if(toc) toc.style.display = 'none';
        if(metadata) metadata.style.display = 'none';
        richTextToggles.forEach(toggle => toggle.style.display = 'none');
    } else {
        if(toc) toc.style.display = 'block';
        if(metadata) metadata.style.display = 'block';
        richTextToggles.forEach(toggle => toggle.style.display = 'flex');
    }
}
function toggleLineBreaks(checkbox) { document.getElementById("content").classList.toggle("show-line-breaks", checkbox.checked); }

function toggleLocationMarkers(checkbox) { document.getElementById("content").classList.toggle("hide-location-markers"); }

function toggleButtonContainer() {
    const buttonContainer = document.querySelector('.button-container');
    const mobileIcon = document.getElementById('controls-icon');
    buttonContainer.classList.toggle('expanded');
    if (buttonContainer.classList.contains('expanded')) {
        mobileIcon.style.display = 'none';
    } else {
        mobileIcon.style.display = 'block';
    }
}

function toggleCorrections(checkbox) {
    const content = document.getElementById('content');
    if (!content) return;

    const anteCorrectionElements = content.querySelectorAll('.ante-correction');
    const postCorrectionElements = content.querySelectorAll('.post-correction');

    if (checkbox.checked) { // Show post-correction
        anteCorrectionElements.forEach(el => el.style.display = 'none');
        postCorrectionElements.forEach(el => el.style.display = 'inline');
    } else { // Show ante-correction (default)
        anteCorrectionElements.forEach(el => el.style.display = 'inline');
        postCorrectionElements.forEach(el => el.style.display = 'none');
    }
}

document.addEventListener('DOMContentLoaded', (event) => {
    const tocHeader = document.querySelector('#toc h2');
    if (tocHeader) { tocHeader.addEventListener('click', toggleToc); }
    const metadataHeader = document.querySelector('#metadata h2');
    if (metadataHeader) { metadataHeader.addEventListener('click', toggleMetadata); }

    const mobileControlsIcon = document.getElementById('controls-icon');
    if (mobileControlsIcon) {
        mobileControlsIcon.addEventListener('click', toggleButtonContainer);
    }
    const closeButton = document.getElementById('close-button-container');
    if (closeButton) {
        closeButton.addEventListener('click', toggleButtonContainer);
    }

    const correctionsListItem = document.getElementById('corrections-list-container');
    if (correctionsListItem) {
        const title = correctionsListItem.querySelector('b');
        title.style.cursor = 'pointer';
        title.addEventListener('click', () => {
            const table = correctionsListItem.querySelector('table');
            const caret = title.querySelector('.caret');
            const isHidden = table.style.display === 'none';
            table.style.display = isHidden ? 'table' : 'none';
            caret.textContent = isHidden ? '▼' : '▶';
        });
    }

    const infoIcon = document.getElementById('corrections-info-icon');
    if (infoIcon) {
        infoIcon.addEventListener('click', () => {
            const metadataPanel = document.getElementById('metadata');
            const correctionsListContainer = document.getElementById('corrections-list-container');

            if (metadataPanel) {
                metadataPanel.classList.add('expanded');
            }

            if (correctionsListContainer) {
                const title = correctionsListContainer.querySelector('b');
                const table = correctionsListContainer.querySelector('table');
                const caret = title.querySelector('.caret');
                
                // Expand the corrections list
                table.style.display = 'table';
                caret.textContent = '▼';

                // Wait for animations to finish before scrolling
                setTimeout(() => {
                    correctionsListContainer.scrollIntoView({ behavior: 'smooth' });
                }, 500); // Match the CSS transition duration
            }
        });
    }

    // Transliteration logic
    const transliterationSchemeSelect = document.getElementById('transliteration-scheme');
    const showAllSchemesCheckbox = document.getElementById('show-all-schemes-checkbox');
    const contentDiv = document.getElementById('content');

    if (!contentDiv || !transliterationSchemeSelect) {
        return;
    }

    const originalContent = contentDiv.innerHTML;
    const transliteratedContent = {};

    const allSchemes = {
        "Roman": ["hk", "iast", "iso", "itrans", "slp1", "velthuis", "wx"],
        "Brahmic": ["bengali", "devanagari", "gujarati", "kannada", "malayalam", "oriya", "sinhala", "tamil"]
    };
    const defaultSchemes = ["iast", "devanagari", "hk", "itrans"];
    const schemeDisplayNames = {
        "iast": "IAST",
        "hk": "HK",
        "itrans": "ITRANS",
        "slp1": "SLP1",
        "velthuis": "Velthuis",
        "iso": "ISO 15919",
        "wx": "WX"
    };

    function populateSchemesDropdown(showAll) {
        transliterationSchemeSelect.innerHTML = ''; 

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
        if (targetScheme === 'iast') {
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
            if (/[āīūṛṝḷḹṃḥñṭḍṇśṣĀĪŪṚṜḶḸṂḤÑṬḌṆŚṢ]/.test(node.nodeValue)) {
                node.nodeValue = Sanscript.t(node.nodeValue, 'iast', targetScheme);
            }
        }
        
        transliteratedContent[targetScheme] = tempDiv.innerHTML;
        contentDiv.innerHTML = tempDiv.innerHTML;
    }

    transliterationSchemeSelect.addEventListener('change', (e) => {
        const selectedScheme = e.target.value;
        localStorage.setItem('selectedTransliterationScheme', selectedScheme);
        transliterate(selectedScheme);
    });

    showAllSchemesCheckbox.addEventListener('change', (e) => {
        const showAll = e.target.checked;
        localStorage.setItem('showAllTransliterationSchemes', showAll);
        const currentSelection = transliterationSchemeSelect.value;
        populateSchemesDropdown(showAll);
        transliterationSchemeSelect.value = currentSelection;
    });

    const savedScheme = localStorage.getItem('selectedTransliterationScheme') || 'iast';
    const savedShowAll = localStorage.getItem('showAllTransliterationSchemes') === 'true';

    showAllSchemesCheckbox.checked = savedShowAll;
    populateSchemesDropdown(savedShowAll);
    
    transliterationSchemeSelect.value = savedScheme;
    
    if (savedScheme !== 'iast') {
        transliterate(savedScheme);
    }
});
