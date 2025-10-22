
[About](#about) | [Features](#features) | [Usage](#usage) | [Subcommands](#subcommands) | [Target metadata](#target-metadata)

----------------------------------------

# ABOUT

`mk.parse` is a Makefile parser.

At a high level it uses `make --print-data-base` to get a normalized form, then converts those details to JSON.  But it enriches that information too which creates more interesting possibilities, like supporting docstrings, documentation-generation, and extracting prerequisite-graphs.

This tool is self-contained script that uses `uv` for dependencies, and [optionally runs via docker](#docker).  

----------------------------------------

# FEATURES

* Extracts details about line-numbers, target headers/bodies, prerequisites, etc
* Support for parametric targets, can also find where they are used (aka "implementors")
* Filter targets by type or by prefix, constraining output
* Extracts python-style docstrings from target bodies.
* Supports docstring-interpolation (aka a reasonable summary in case no docstring is present).
* Metadata includes tags that indicate whether target is local vs included, private vs public.
* Metadata includes tags that indicate whether target parametric, implicit, explicit, dynamic.

Other helpers for extracting things like includes, variables, aggregate statistics, and comment-blocks are also available, but this should be considered more experimental than the support for targets.

The main use-case is **autogenerating complete documentation, and/or displaying target-help interactively.**  This works because target-docstrings can use markdown, and those docstrings can be combined with target-metadata to make even more markdown.  

For interactive help from the CLI, target slicing and filtering can be used, followed by rendering some pretty markdown on the console.  Rendering uses [charmbracelet/glow](https://github.com/charmbracelet/glow), which is bundled with the [docker container](#docker), but if you're planning to [use the script](#use-the-script) directly then you'll want to make sure it's installed.

For something a bit more involved that builds on `mk.parse` to add more advanced reflection and automatic "help" capabilities, see [compose.mk](https://robot-wranglers.github.io/compose.mk/cli-help) which uses this.

----------------------------------------

# USAGE

## Use the Script 

If you have `uv` installed, you can run [the script](mk.parse.py) directly.  If the project's cloned already, use `sudo make install`.  Otherwise you can install manually using something like this:

```bash
$ wget https://raw.githubusercontent.com/mattvonrocketstein/mk.parse/refs/heads/main/src/mk.parse.py
$ mv mk.parse.py /usr/local/bin/mk.parse
$ chmod +x /usr/local/bin/mk.parse

# Dependencies downloaded/cached after first run
mk.parse --help
```

## Use Docker
<a name=docker></a>

Run with docker:

```bash 
docker run --rm -i -v `pwd`:/workspace -w/workspace \
  ghcr.io/mattvonrocketstein/mk.parse:v1.2.4 targets Makefile
```

----------------------------------------

# SUBCOMMANDS

```bash
$ mk.parse --help
Usage: mk.parse [OPTIONS] COMMAND [ARGS]...

  mk.parse: Makefile parsing and metadata extraction.

Options:
  --help  Show this message and exit.

Commands:
  cblocks   Extract labeled comment-blocks.
  database  Get database for the Makefile.
  db        Alias for 'database' subcommand.
  includes  Extract names of any included Makefiles.
  stats     Returns various statistics.
  targets   Parse Makefile to JSON.
  vars      Details about variables and assignments.
```

----------------------------------------

# TARGETS & METADATA

Usually you want the the `targets` subcommand:

```bash
$ mk.parse targets --help
Usage: mk.parse.py targets [OPTIONS] MAKEFILE

  Parse Makefile to JSON.  
  Includes targets/prereqs details and documentation.

Options:
  --local          Alias for --locals
  -l, --locals     Filter for local targets only (no includes)
  --target TEXT    Retrieves help for named target only
  --markdown       Returns raw markdown instead of JSON
  --body           Adds target-bodies to output JSON
  --public         Filter for public targets only (prefix NOT in {self|.})
  --private        Filter for private targets only (prefix in {self|.})
  --prefix TEXT    Prefix to filter for
  --interpolate    In case of no target docstring, the pre-requisite chain 
                   is inspected, and a docstring is created from those docstrings
  --shallow        Simple target extraction without make's db. (Does not process includes/macros)
  --parametrics    Filter for parametric-targets only (using '%')
  -a, --abs-paths  Use absolute-paths in metadata (default is relative)
  --dynamic        Returns dynamically-generated targets only
  --implicit       Returns implicit targets only
  --names-only     Returns names only (no metadata)
  --preview        Pretty-printer for console (implies --markdown)
  --help           Show this message and exit.
```

## Example Output (JSON)

```bash
$ mk.parse targets tests/sample-1.mk
```

```json
{
  "clean": {
    "file": "tests/sample-1.mk",
    "lineno": 0,
    "parametric": false,
    "chain": [],
    "type": "file",
    "docs": [" Project clean"],
    "prereqs": [],
    "local": true,
    "private": false,
  },
  "build": {
    "file": "tests/sample-1.mk",
    "lineno": 4,
    "parametric": false,
    "chain": null,
    "type": "file",
    "docs": [" Project build"],
    "prereqs": ["helper1", "helper2"],
    "local": true,
    "private": false,
  },
  "test": {
    "file": "tests/sample-1.mk",
    "lineno": 6,
    "parametric": false,
    "chain": [],
    "type": "file",
    "docs": [" Project test"],
    "prereqs": [],
    "local": true,
    "private": false,
  },
  ..
}
```

## Example Output (Markdown)

```bash
$ mk.parse targets --markdown tests/sample-1.mk
```

```markdown
[`clean`](#) *(via tests/sample-1.mk:0)*

Project clean

-----------------------

[`build`](#) *(via tests/sample-1.mk:4)*

* prereqs: <small>`helper2`, `helper1`</small>

Project build

-----------------------

[`test`](#) *(via tests/sample-1.mk:7)*

Project test
```

## Example Output (Rendered)

A typical example of rendered output:

```bash
$ mk.parse targets --markdown tests/sample-1.mk
```

<img src=docs/img/example-1.png>

Running with `--interpolate` changes some of the output, trying to improve on "No documentation available".  

Afterwards the `chain-example` target above looks like this:

<img src=docs/img/example-2.png>

----------------------------------------

# CONFIG

* `MKPARSE_LOG_LEVEL`: Supports debug/info/warn/critical as usual.

----------------------------------------

# REFS

* [https://www.gnu.org/software/make/manual/make.html](https://www.gnu.org/software/make/manual/make.html)

----------------------------------------
