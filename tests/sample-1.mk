clean:; echo cleaning
	@# Project clean

build: helper1 helper2
	@# Project build

test:
	@# Project test
	echo testing

chain-example: clean build test

helper1:
	@# Fake helper the first
	echo helper1

helper2:
	@# Fake helper the second, with markdown table in docstring
	@# | Column 1      | Column 2      |
	@# | ------------- | ------------- |
	@# | Cell 1, Row 1 | Cell 2, Row 1 |
	@# | Cell 1, Row 2 | Cell 1, Row 2 |
	echo helper2

parametric-target-example/%:
	# Example parametric target, with missing/bad docstring

self.private_target:
	@# Private target, self-prefix

.private_target:
	@# Private target, dot-prefix

