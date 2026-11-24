PYTHON ?= python3

.PHONY: build check install clean

build:            ## Regenerate every logo, icon, palette and guideline image
	$(PYTHON) tools/build.py

check: build      ## Rebuild assets and check README links
	$(PYTHON) tools/check_readme_links.py

install:          ## Install the generator's Python dependencies
	$(PYTHON) -m pip install -r requirements.txt

clean:            ## Remove generated PNG/ICO files (SVG masters and docs are kept)
	rm -rf logos/*/png logos/adamai-mark/icons/*.png logos/adamai-mark/icons/*.ico
