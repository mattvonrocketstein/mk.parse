clean:; echo cleaning
	@# Project clean

build: helper1 helper2
	@# Project build

test:
	@# Project test
	echo testing

helper1:
	@# Fake helper the first
	echo helper1

helper2:
	@# Fake helper the second
	echo helper2

parametric-target/%:
	# Example parametric target, and bad docstrings

self.private_target:
	@# Private target, self-prefix

.private_target:
	@# Private target, dot-prefix