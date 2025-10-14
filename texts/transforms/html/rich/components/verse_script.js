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
        const handleSliderChange = (value) => {
            document.documentElement.style.setProperty('--verse-spacing', value + 'em');
            if (parseFloat(value) === 0) {
                document.body.classList.add('no-verse-padding');
            } else {
                document.body.classList.remove('no-verse-padding');
            }
        };

        slider.addEventListener('input', (e) => {
            handleSliderChange(e.target.value);
        });

        // Set initial state
        handleSliderChange(slider.value);
    }

    // Set initial state based on the toggle
    const verseFormatToggle = document.querySelector('input[onchange="toggleVerseFormatting(this)"]');
    if (verseFormatToggle) {
        toggleVerseFormatting(verseFormatToggle);
    }
});
