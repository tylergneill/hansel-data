document.addEventListener('DOMContentLoaded', (event) => {
    const slider = document.getElementById('width-slider');
    if (slider) {
        slider.addEventListener('input', (e) => {
            document.documentElement.style.setProperty('--left-col-width', e.target.value + '%');
        });
    }
});
