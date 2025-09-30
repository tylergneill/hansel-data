function toggleVerseFormatting(checkbox) {
    document.body.classList.toggle('simple-verse-style', !checkbox.checked);
    const sliderToggle = document.querySelector('.verse-format-toggle');
    if (sliderToggle) {
        sliderToggle.style.display = checkbox.checked ? 'block' : 'none';
    }
}

document.addEventListener('DOMContentLoaded', (event) => {
    const slider = document.getElementById('width-slider');
    if (slider) {
        slider.addEventListener('input', (e) => {
            document.documentElement.style.setProperty('--left-col-width', e.target.value + '%');
        });
    }

    // Set initial state based on the toggle
    const verseFormatToggle = document.querySelector('input[onchange="toggleVerseFormatting(this)"]');
    if (verseFormatToggle) {
        toggleVerseFormatting(verseFormatToggle);
    }
});
