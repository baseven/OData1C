install:
	poetry install

test:
	poetry run pytest

test-coverage:
	poetry run pytest --cov=OData1C --cov-report xml

build:
	poetry build

publish:
	poetry publish

run-metadata:
	poetry run python example/metadata.py