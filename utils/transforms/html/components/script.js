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
                    richTextToggles.forEach(toggle => toggle.style.display = 'block');
                }
            }
            function toggleLineBreaks(checkbox) { document.getElementById("content").classList.toggle("show-line-breaks", checkbox.checked); }

            function toggleButtonContainer() {
                const buttonContainer = document.querySelector('.button-container');
                const mobileIcon = document.getElementById('controls-icon');
                console.log('--- Toggling Button Container ---');
                console.log('Container expanded before toggle: ' + buttonContainer.classList.contains('expanded'));
                buttonContainer.classList.toggle('expanded');
                console.log('Container expanded after toggle: ' + buttonContainer.classList.contains('expanded'));
                if (buttonContainer.classList.contains('expanded')) {
                    mobileIcon.style.display = 'none';
                    console.log('Action: Hide burger icon, show container.');
                } else {
                    mobileIcon.style.display = 'block';
                    console.log('Action: Show burger icon, hide container.');
                }
                console.log('Final container className: ' + buttonContainer.className);
                console.log('---------------------------------');
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
        });
