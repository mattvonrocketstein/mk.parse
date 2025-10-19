# About 

A makefile parser, mostly used for returning target-metadata.  Includes details about prerequisites, doc-string extraction or interpolation, and also works with targets defined via `include`'ed files.

# Subcommands 

```bash
$ mk.parse --help
Usage: mk.parse.py [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  targets   Parse Makefile to JSON.
  cblocks   Extract labeled comment-blocks
  includes  Extract names of any included Makefiles
```

# Parse Target Metadata

```bash
$ mk.parse --help
Usage: mk.parse.py targets [OPTIONS] MAKEFILE

  Parse Makefile to JSON.  Includes targets/prereqs details and documentation.

Options:
  --target TEXT  Retrieves help for named target only
  --markdown     Enriches docs by guessing at markdown formatting
  --body         Enriches docs by guessing at markdown formatting
  --public       Filter for public targets only (no prefix in {self|.})
  --private      Filter for private targets only (prefix in {self|.})
  --locals       Filter for local targets only (no includes)
  --prefix TEXT  Prefix to filter for
  --local        Alias for --locals
  --interpolate  Interpolate docstrings
  --shallow      Simple target extraction without make-db. (Does not process includes/macros)
  --parametrics  Filter for parametric-targets only (using %)
  --preview      Pretty-printer (implies --markdown)
  --help         Show this message and exit.
```

# Use the Script 

If you have `uv` installed, you can run [the script](mk.parse.py) directly.

# Docker

Run the parser with docker:

```bash 
docker run --rm -i -v `pwd`:/workspace -w/workspace ghcr.io/mattvonrocketstein/mk.parse:v1.2.4 targets Makefile
```

# Config 

* `MKPARSE_LOG_LEVEL`, set to debug/info/warn