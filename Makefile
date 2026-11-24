PYTHON ?= python3

.PHONY: build install clean

build:            ## Regenerate every logo, icon, palette and guideline image
	$(PYTHON) tools/build.py

install:          ## Install the generator's Python dependencies
	$(PYTHON) -m pip install -r requirements.txt

clean:            ## Remove generated PNG/ICO files (SVG masters and docs are kept)
	rm -rf logos/*/png logos/adamai-mark/icons/*.png logos/adamai-mark/icons/*.ico
