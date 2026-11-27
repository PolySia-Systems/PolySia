PYTHON ?= python3
NPM ?= npm
POLYSIA_DB ?= $(CURDIR)/.polysia/workspace.sqlite3
NPM_CACHE ?= $(CURDIR)/.cache/npm
WEB := apps/web
WEB_TOOLS := $(WEB)/node_modules/.polysia-installed
BROWSER_ENV := .venv
BROWSER_TOOLS := $(BROWSER_ENV)/.polysia-installed

.PHONY: setup web build run check browser-test provider-test install-test verify
.PHONY: release-check fresh-install-check
.DEFAULT_GOAL := setup

setup: web

$(WEB_TOOLS): $(WEB)/package.json $(WEB)/package-lock.json
	$(NPM) --prefix $(WEB) ci --cache "$(NPM_CACHE)" --no-fund --no-audit
	@touch $@

web: $(WEB_TOOLS)
	$(NPM) --prefix $(WEB) run build

build: web
	$(PYTHON) deploy/build.py

run: web
	POLYSIA_DB="$(POLYSIA_DB)" $(PYTHON) -m apps.server

check:
	$(PYTHON) -m unittest discover -s tests -v

$(BROWSER_TOOLS): tests/browser/requirements.txt
	$(PYTHON) -m venv "$(BROWSER_ENV)"
	$(BROWSER_ENV)/bin/python -m pip install --disable-pip-version-check --cache-dir "$(CURDIR)/.cache/pip" -r $<
	@touch $@

browser-test: build $(BROWSER_TOOLS)
	$(BROWSER_ENV)/bin/python tests/browser/journey.py $(BROWSER_ARGS)
	$(BROWSER_ENV)/bin/python tests/browser/wallet_address_input.py dist/polysia.pyz

provider-test: build $(BROWSER_TOOLS)
	$(BROWSER_ENV)/bin/python tests/browser/journey.py --public-smoke $(BROWSER_ARGS)

install-test: build
	$(PYTHON) tests/install_smoke.py

RELEASE_BUNDLE ?= dist/polysia.pyz
RELEASE_GUIDE ?= install

release-check:
	$(PYTHON) tests/install_smoke.py --release-bundle "$(RELEASE_BUNDLE)" --release-guide "$(RELEASE_GUIDE)"

fresh-install-check:
	$(PYTHON) tests/fresh_install.py $(FRESH_INSTALL_ARGS)

verify: check browser-test install-test
