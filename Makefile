.PHONY: install build clean

install:
	pip install -e ".[dev]"

build:
	python -m pip install pyinstaller
	python -m PyInstaller \
		--onefile \
		--name branchsync \
		--clean \
		--noconfirm \
		--console \
		--hidden-import branchsync.cli \
		src/branchsync/cli.py

clean:
	rm -rf build dist *.spec
