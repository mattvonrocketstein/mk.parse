#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "click==8.1.8","Jinja2==3.1.6","rich==14.1.0",
# ]
# ///
import collections
import json
import logging
import os
import re
import subprocess
import tempfile
import typing
from pathlib import Path

import click
import jinja2
from rich.console import Console
from rich.logging import RichHandler

## Constants and 3rd-Party
##░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░


DOCS_TEMPLATE = """
[`{{target}}`](#) *(via {{file}}:{{lineno}})*

{%if prereqs and not interpolated%}
* prereqs: <small>{%for p in prereqs%}`{{p}}`{%if not loop.last%}, {%endif%}{%endfor%}</small>
{% else %}
{#* prereqs: *(None)*#}
{%endif %}
{%if docs %}
{%for line in docs%}
{{line}}
{%endfor%}
{% else %}
No documentation available.
{% endif %}
-----------------------
"""

PRIVATE_PREFIXES = "self .".split()
CONSOLE = Console(stderr=True)
_recipe_pattern = "#  recipe to execute (from '"
_variables_pattern = "# Variables"
_variables_end_pattern = "# variable set hash-table stats:"
_ht_stats_pattern = "# files hash-table stats:"

## Logging
##░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░


def get_logger(name, console=CONSOLE):
    log_handler = RichHandler(
        rich_tracebacks=True,
        console=console,
        show_time=False,
    )

    logging.basicConfig(
        format="%(message)s",
        datefmt="[%X]",
        handlers=[log_handler],
    )
    FormatterClass = logging.Formatter
    formatter = FormatterClass(
        fmt=" ".join(["%(name)s", "%(message)s"]),
        # datefmt="%Y-%m-%d %H:%M:%S",
        datefmt="",
    )
    log_handler.setFormatter(formatter)
    logger = logging.getLogger(name)
    logger.setLevel(os.environ.get("MKPARSE_LOG_LEVEL", "warn").upper())
    return logger


LOGGER = get_logger(__name__)

# Boring Helpers
##░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░


def json_output(out):
    print(json.dumps(out, indent=2))
    return out


def validate_makefile(makefile: str, strict: bool = False):
    """
    Validation here isn't *real* validation since it slows things
    down.

    FIXME: finish the strict-mode
    """
    if strict:
        LOGGER.critical("strict mode for validation isnt implemented yet!")
    assert makefile
    tmp = Path(makefile)
    if not all(
        [
            tmp.exists(),
            tmp.is_file(),
        ]
    ):
        err = f"File @ `{makefile}` does not exist"
        LOGGER.critical(err)
        raise ValueError(err)
    else:
        LOGGER.debug(f"parsing makefile @ {makefile}")


def _get_provenance_line(body):
    """
    
    """
    pline = [x for x in body if _recipe_pattern in x]
    pline = pline[0] if pline else None
    return pline


def _get_file(body=None, makefile=None):
    """WARNING: answers according to make's db, but often still wrong!"""
    pline = _get_provenance_line(body)
    if pline:
        return pline.split(_recipe_pattern)[-1].split("'")[0]
    else:
        return str(makefile)


def zip_markdown(docs):
    if isinstance(docs, (list,)):
        docs = "\n".join(docs)
        pattern = r"(^.*?(?:USAGE|EXAMPLE):.*$)\n((?:[ \t]+.+\n?)+)"

        def replacer(match):
            header = match.group(1)
            indented_block = match.group(2)
            # Remove trailing newline from block if present to avoid extra spacing
            indented_block = indented_block.rstrip("\n")
            return f"{header}\n```\n{indented_block}\n```\n"

        result = re.sub(pattern, replacer, docs, flags=re.MULTILINE)
        result = re.sub(r"\n{2,}", "\n\n", result)
        return result.split("\n")


## Targets Entrypoint
##░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

o_locals = click.option(
    "-l",
    "--locals",
    is_flag=True,
    default=False,
    help="Filter for local targets only (no includes)",
)
o_local = click.option(
    "--local", is_flag=True, default=False, help="Alias for --locals"
)


@click.command()
@o_local
@o_locals
@click.option("--target", help="Retrieves help for named target only")
@click.option(
    "-m",
    "--markdown",
    is_flag=True,
    default=False,
    help="Returns raw markdown instead of JSON",
)
@click.option(
    "-b",
    "--body",
    is_flag=True,
    default=False,
    help="Adds target-bodies to output JSON",
)
@click.option(
    "--public",
    is_flag=True,
    default=False,
    help="Filter for public targets only (prefix NOT in {self|.})",
)
@click.option(
    "--private",
    is_flag=True,
    default=False,
    help="Filter for private targets only (prefix in {self|.})",
)
@click.option(
    "-p",
    "--prefix",
    default="",
    help="Prefix to filter for",
)
@click.option(
    "-i", "--interpolate", is_flag=True, default=False, help="Interpolate docstrings"
)
@click.option(
    "-s",
    "--shallow",
    is_flag=True,
    default=False,
    help="Simple target extraction without make's db. (Does not process includes/macros)",
)
@click.option(
    "--parametrics",
    is_flag=True,
    default=False,
    help="Filter for parametric-targets only (using '%')",
)
@click.option(
    "-a",
    "--abs-paths",
    is_flag=True,
    default=False,
    help="Use absolute-paths in metadata (default is relative)",
)
@click.option(
    "-d",
    "--dynamic",
    is_flag=True,
    default=False,
    help="Returns dynamically-generated targets only",
)
@click.option(
    "--implicit", is_flag=True, default=False, help="Returns implicit targets only"
)
@click.option(
    "-n",
    "--names-only",
    is_flag=True,
    default=False,
    help="Returns names only (no metadata)",
)
@click.option(
    "-x",
    "--preview",
    is_flag=True,
    default=False,
    help="Pretty-printer for console (implies --markdown)",
)
@click.argument("makefile")
def targets(*args, **kwargs):
    """
    Parse Makefile targets to JSON, slice targets by prefix, show
    documentation for targets, etc.
    """
    markdown = kwargs["markdown"]
    preview = kwargs["preview"]
    markdown = markdown or preview
    names_only = kwargs["names_only"]
    out = _targets(*args, **kwargs)
    # user requested only target-names
    if names_only:
        return print("\n".join(out.keys()))

    # user requested markdown output, not json
    if markdown:
        template = jinja2.Template(DOCS_TEMPLATE)
        str_out = ""
        for target in out:
            str_out += "\n" + template.render(target=target, **out[target])
        if preview:
            glow_img = "charmcli/glow:v1.5.1"
            glow_theme = "dracula"
            with tempfile.TemporaryDirectory() as tmpdir:
                path = os.path.join(tmpdir, "cache.json")
                with open(path, "w") as fhandle:
                    fhandle.write(str_out)
                has_glow = os.system("which glow") == 0
                if has_glow:
                    LOGGER.info("found that glow is installed, using it for previews")
                    cmd = f"cat  {path} | glow -s dracula"
                else:
                    LOGGER.info("glow is missing, using docker version")
                    cmd = f"cat  {path} | docker run -q -i -v {tmpdir}:{tmpdir}  {glow_img} -s {glow_theme}"
                LOGGER.info(f"cmd: \n{cmd}")
                os.system(cmd)
        else:
            print(str_out)
    else:
        json_output(out)


def _targets(
    makefile: str = None,
    target: str = "",
    prefix: str = "",
    body: bool = False,
    interpolate: bool = False,
    implicit: bool = False,
    dynamic: bool = False,
    locals: bool = False,
    abs_paths: bool = True,
    local: bool = False,
    public: bool = False,
    names_only: bool = False,
    shallow: bool = False,
    private: bool = False,
    parametrics: bool = False,
    preview: bool = False,
    markdown: bool = False,
    parse_target_aliases: bool = True,
    **kwargs,
):
    """
    
    """
    markdown = markdown or preview
    locals = locals or local
    body = body or interpolate
    pruned = {}
    if names_only:
        err = "--names-only is exclusive with {markdown|preview} "
        assert not any([markdown, preview]), err + f"{markdown,preview}"

    def _test(x):
        tests = [
            ":" in x.strip(),
            not x.startswith("#"),
            not x.startswith("\t"),
        ]
        return all(tests)

    if shallow:
        LOGGER.warning(f"Parsing {makefile} in shallow-mode!")
        LOGGER.warning(
            "This excludes dynamic targets, included targets and target metadata"
        )
        cmd = (
            f"cat {makefile}"
            + """ | awk '/^define/ { in_define = 1 } /^endef/  { in_define = 0; next } !in_define { print }' """
        )
        tmp = subprocess.run(cmd, shell=True, capture_output=True)
        lines = tmp.stdout.decode().split("\n")
        lines = [
            line.split(":")[0]
            for line in lines
            if re.match(r"^[a-zA-Z-_/]+[:][^=]", line)
        ]
        return lines
    db = _database(makefile, **kwargs)
    raw_db = "\n".join(db)
    validate_makefile(makefile)
    with open(makefile) as fhandle:
        raw_content = fhandle.read()
    original = raw_content.split("\n")
    variables_start = db.index(_variables_pattern)
    variables_end = db.index("", variables_start + 2)
    # vars = db[variables_start:variables_end]
    db = db[variables_end:]
    implicit_rule_start = db.index("# Implicit Rules")
    file_rule_start = db.index("# Files")
    file_rule_end = db.index(_ht_stats_pattern)
    for i, line in enumerate(db[implicit_rule_start:]):
        if "implicit rules, " in line and line.endswith(" terminal."):
            implicit_rule_end = implicit_rule_start + i
            break
    else:
        LOGGER.critical("cannot find `implicit_rule_end`!")
        implicit_rule_end = implicit_rule_start
    implicit_targets_section = db[implicit_rule_start:implicit_rule_end]
    file_targets_section = db[file_rule_start:file_rule_end]
    file_target_names = list(filter(_test, file_targets_section))
    implicit_target_names = list(filter(_test, implicit_targets_section))
    targets = file_target_names + implicit_target_names
    out = {}
    targets = [t for t in targets if t != f"{makefile}:"]
    for tline in targets:
        if any(
            [
                tline.startswith(" "),
            ]
            + [
                tline.startswith(x)
                for x in "$ @ & \t".split(" ") + ".SUFFIXES: .INTERMEDIATE:".split()
            ]
            + [";" in tline]
        ):
            continue
        bits = tline.split(":")
        target_name = bits.pop(0)
        childs = ":".join(bits)
        type = "implicit" if tline in implicit_targets_section else "file"
        # NB: line nos are from reformatted output, not original file
        line_start = db.index(tline)
        line_end = db.index("", line_start)
        target_body = db[line_start:line_end]
        pline = _get_provenance_line(target_body)
        file = _get_file(
            body=target_body,
            makefile=makefile,
        )

        # user requested absolute-paths
        if file and not abs_paths:
            try:
                file = str(Path(file).resolve().relative_to(Path.cwd()))
            except ValueError:
                file = str(file)
        if pline:
            # take advice from make's database.
            # we return this because it's authoritative,
            # but actually sometimes it's wrong.  this returns
            # the first line of the target that's tab-indented,
            # but sometimes make macros like `ifeq` are not indented..
            lineno = pline.split("', line ")[-1].split("):")[0]
        else:
            try:
                lineno = original.index(tline)
            except ValueError:
                LOGGER.debug(f"cant find {tline} in {makefile}, included?")
                # target_name
                lineno = None
        lineno = lineno and (int(lineno) - 1)
        prereqs = [x for x in childs.split() if x.strip()]
        header = target_body.pop(0)

        # This is probably an invocation of a parametric target?
        if f"\n# Not a target:\n{target_name}:\n" in raw_db:
            continue

        # FIXME: determining locality is still buggy for complex scenarios, multiple includes, etc
        is_local = file == makefile
        if (
            is_local
            and type != "implicit"
            and not re.findall(
                r"^" + target_name + r"(?: [a-zA-Z\-_/]+)*:.*",
                raw_content,
                re.MULTILINE,
            )
        ):
            LOGGER.debug(f"revoking local: {target_name}")
            is_local = False
        target_docs = [x[len("\t@#") :] for x in target_body if x.startswith("\t@#")]
        if target_docs and target_docs[-1] == "":
            target_docs.pop(-1)
        out[target_name] = {
            "file": file,
            "lineno": lineno,
            "header": header,
            "body": [b.lstrip() for b in target_body if not b.startswith("#  ")],
            "parametric": "%" in target_name,
            "chain": None,
            "type": type,
            "docs": target_docs,
            "prereqs": list(set(prereqs)),
            "local": is_local,
            "private": any(target_name.startswith(x) for x in PRIVATE_PREFIXES),
        }
        if type == "implicit":
            regex = target_name.replace("%", ".*")
            out[target_name].update(regex=regex, implicit=True)
            if file == makefile and not re.findall(
                # rf"^{target_name}:.*", raw_content, re.MULTILINE
                r"^" + target_name + r"(?: [a-zA-Z\-_/]+)*:.*",
                raw_content,
                re.MULTILINE,
            ):
                out[target_name].update(dynamic=True)
                # out['local']

    for target_name, tmeta in out.items():
        if "regex" in tmeta:
            implementors = []
            for impl in out:
                if impl != target_name and re.compile(tmeta["regex"]).match(impl):
                    implementors.append(impl)
            out[target_name]["implementors"] = implementors

    for target_name, tmeta in out.items():
        real_body = [
            b
            for b in tmeta["body"][1:]
            if not b.startswith("#") and not b.startswith("@#")
        ]
        if not real_body:
            LOGGER.debug(f"missing body for: {target_name}")
            for chain in out:
                if target_name in out[chain].get("implementors", []):
                    tmeta["chain"] = chain
            if len(tmeta["prereqs"]) == 1:
                tmeta["chain"] = tmeta["prereqs"][0]
        else:
            tmeta["chain"] = []
        out[target_name] = tmeta

    for target_name, tmeta in out.items():
        # if this is a simple alias with no docs, pull the docs from the principal
        if not tmeta["docs"] and tmeta["chain"]:
            out[target_name]["docs"] = out.get(tmeta["chain"], {}).get("docs", [])

        # user requested enriching docs with markdown
        if markdown:
            docs = out[target_name]["docs"]
            zmd = zip_markdown(docs)
            out[target_name]["docs"] = [] if not any(zmd) else zmd

    # autodocs for target aliases
    if parse_target_aliases:
        tmp = {}
        for aliases_maybe, v in out.items():
            aliases = aliases_maybe.split(" ")
            if len(aliases) > 1:
                primary = aliases.pop(0)
                tmp[primary] = v
                for alias in aliases:
                    tmp[alias] = {
                        **v,
                        **{
                            "alias": True,
                            "primary": primary,
                            "docs": [f"(Alias for '{primary}')"],
                        },
                    }
            else:
                tmp[aliases_maybe] = v
        out = tmp
    ALL = out.copy()

    # filter: user requested only implicits
    if implicit:
        LOGGER.info("Excluding non-implicit targets..")
        out = {k: v for k, v in out.items() if v.get("implicit", False) is True}

    # filter: user requested only dynamic
    if dynamic:
        LOGGER.info("Excluding non-implicit targets..")
        out = {k: v for k, v in out.items() if v.get("dynamic", False) is True}

    # filter: user requested only parametrics
    if parametrics:
        LOGGER.info("Excluding non-parametric targets..")
        out = {k: v for k, v in out.items() if v.get("parametric", False) is True}

    # filter: user requested no target-bodies should be provided
    if not body:
        out = {
            k: {kk: vv for kk, vv in v.items() if kk not in "body header".split()}
            for k, v in out.items()
        }

    # filter: only local targets
    if locals:
        LOGGER.info("Excluding nonlocal targets..")
        out = {k: v for k, v in out.items() if v.get("local", False) is True}

    # user requested target-search
    # NB: this changes the response schema!
    if target:
        out = out.get(target, {})

    # filter: used requested only targets with given prefix
    if prefix:
        out = {k: v for k, v in out.items() if k.startswith(prefix)}

    # filter: user requested only public targets
    if public:
        LOGGER.info("Excluding private targets..")
        out = {k: v for k, v in out.items() if v.get("private", False) is False}

    # filter: user requested only private targets
    if private:
        LOGGER.info("Excluding public targets..")
        out = {k: v for k, v in out.items() if v.get("private", False) is True}

    # enrichment: user requested interpolated docs
    if interpolate:
        for target, data in out.items():
            if not data["docs"]:
                LOGGER.warning(f"interpolating: {target}")
                prereqs = data["prereqs"]
                if not prereqs:
                    docs = []
                else:
                    docs = ["Stepwise summary:\n"]
                for i, p in enumerate(prereqs):
                    alt = p[: p.find("/") + 1] + "%"
                    LOGGER.warning([p, alt])
                    pdocs = ALL.get(p, {}).get("docs", [])
                    if pdocs:
                        pdocs = f"`{p}`: {' '.join(pdocs[:1])}"
                        # pdocs = pdocs[:80]
                        # pdocs=f'{pdocs[:pdocs.find(" ")]} .. '
                    else:
                        subs = ALL.get(p, {}).get("prereqs", [])
                        if subs:
                            pdocs = ",".join([f"`{sub}`" for sub in subs])
                        else:
                            LOGGER.warning(f"failed retrieving docs for {target}")
                            pdocs = f"`{p}`: *(No summary available)* "
                    these_docs = f"{i+1}. {pdocs}"  # ('\n'.join(pdocs))
                    # doc=f"{i}. {p}\n{these_docs}"
                    docs += [these_docs]
                if not docs:
                    docs = (
                        ["Implementation summary:", "```bash"]
                        + out[target]["body"][:3]
                        + ["\n```\n"]
                    )
                out[target]["docs"] = docs
                out[target]["interpolated"] = True

    for k in ALL:
        tmp = out.get(k, {})
        if tmp and not any(
            [tmp.get("file", None), tmp.get("chain", []), tmp.get("docs", [])]
        ):
            pruned[k] = tmp
    if pruned:
        LOGGER.warning(f"pruned these targets with no details: {list(pruned.keys())}")

    out = dict(
        sorted(
            out.items(),
            key=lambda x: x[1]["lineno"] if x[1]["lineno"] is not None else -1,
        )
    )
    return out


## DB Entrypoint
##░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░


@click.command("database")
@click.argument("makefile")
def database(*args, **kwargs):
    """
    Get database for the Makefile.

    This output comes from 'make --print-data-base'
    """
    print("\n".join(_database(*args, **kwargs)))


def _database(makefile: str = "", make="make") -> typing.List[str]:
    """
    Get database for Makefile (This output comes from 'make
    --print-data-base') # FIXME: nix the temporary file and use
    streams.
    """
    LOGGER.debug(f"building database for {makefile}")
    validate_makefile(makefile)
    cmd = f"{make} --print-data-base -pqRrs -f {makefile} > .tmp.mk.db 2>/dev/null"
    os.system(cmd)
    with open(".tmp.mk.db") as fhandle:
        out = fhandle.read().split("\n")
    os.remove(".tmp.mk.db")
    return out


@click.command()
@click.argument("makefile")
def db(*args, **kwargs):
    """
    Alias for 'database' subcommand.
    """
    return print("\n".join(_database(*args, **kwargs)))


@click.command()
@click.argument("makefile")
def includes(*args, **kwargs):
    """
    Extract names of any included Makefiles.
    """
    return json_output(_includes(*args, **kwargs))


def _includes(makefile: str = ""):
    validate_makefile(makefile)
    with open(makefile) as fhandle:
        lines = fhandle.readlines()
        includes = [line for line in lines if line.startswith("include ")]
        includes = [" ".join(line.split()[1:]) for line in includes]
    return includes


## Stats Entrypoint
##░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░


@click.command()
@click.argument("makefile")
def stats(*args, **kwargs):
    """
    Returns various statistics.
    """
    return json_output(_stats(*args, **kwargs))


def _stats(*args, **kwargs) -> typing.Dict:
    data = _targets(*args, **kwargs)
    out = collections.defaultdict(int)
    for _k, v in data.items():
        for attr in "dynamic implicit private local".split():
            if v.get(attr):
                out[attr] += 1
    out.update(count=len(data))
    includes = _includes(*args, **kwargs)
    tmp = {k: len(v) for k, v in _vars(*args, **kwargs).items()}
    return dict(
        targets=out, vars=tmp, includes=dict(files=includes, count=len(includes))
    )


## Vars Entrypoint
##░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░


@click.command()
@o_local
@click.argument("makefile")
def vars(*args, **kwargs):
    """
    Details about variables and assignments.
    """
    return json_output(_vars(*args, **kwargs))


def _vars(*args, **kwargs) -> typing.Dict:
    """
    Extract variables and assignment metadata.
    """
    makefile = kwargs["makefile"]
    local = kwargs.pop("local", False)
    db = _database(*args, **kwargs)
    variables_start = db.index(_variables_pattern)
    variables_end = db.index(_variables_end_pattern)
    text = "\n".join(db[variables_start:variables_end])
    p1 = re.compile(r"[#] makefile [(]from .*, line \d+[)]")
    p2 = re.compile("[#] environment")
    key1 = "makefile"
    key2 = "environment"
    result = {key1: [], key2: []}
    matches = []
    for match in p1.finditer(text):
        matches.append((match.end(), key1))
    for match in p2.finditer(text):
        matches.append((match.end(), key2))
    matches.sort(key=lambda x: x[0])
    for i, (pos, pattern_key) in enumerate(matches):
        if not var_is_local(
            pattern_key=pattern_key, pos=pos, makefile=makefile, text=text, local=local
        ):
            continue
        # Extract text from current match end to next match start
        # Find where the next pattern actually starts (before its end position)
        # Search backwards from next match end to find match start
        if i + 1 < len(matches):
            next_match_start = matches[i + 1][0]
            next_pattern = matches[i + 1][1]
            next_pattern_obj = p1 if next_pattern == key1 else p2
            for _m in next_pattern_obj.finditer(text[:next_match_start]):
                pass  # Get last match before next_match_start
            block = (
                text[pos : _m.start()]
                if "_m" in locals()
                else text[pos:next_match_start]
            )
            result[pattern_key].append(block)
        # Last match - extract to end of string
        else:
            result[pattern_key].append(text[pos:])
    data = collections.defaultdict(dict)
    for sect in result["makefile"]:
        if sect.startswith("\ndefine"):
            sect = sect.lstrip()
            name = sect.split()[2]
            data["defines"][name] = sect
        else:
            sect = sect.lstrip()
            bits = sect.split()
            lhs = bits[0]
            assn = bits[1]
            assert assn in [
                ":=",
                "=",
            ], f"expected assignment would be := or =, got {assn}"
            rhs = bits[2:]
            data[assn][lhs] = " ".join(rhs)
    return data


def var_is_local(
    pos: int = -1,
    makefile: str = "",
    pattern_key: str = "",
    text: str = "",
    local: bool = False,
):
    """
    Everything is local if locals weren't requested, If only
    local vars requested, check file provenance and answer.
    """
    if not local:
        return True
    if pattern_key == "makefile":
        pline = text[text[:pos].rfind("\n") : pos]
        pattern = r"[#] makefile [(]from '(?P<filename>[^']+)', line \d+[)]"
        fname = re.search(pattern, pline).group(1)
        if fname == makefile:
            return True


## Comment-Block Entrypoint
##░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░


@click.command()
@click.argument("makefile")
@click.option(
    "--pattern",
    default="",
    help="Pattern to look for in keys",
)
@click.option(
    "--lucky",
    is_flag=True,
    default=False,
    help="Pattern to look for in keys",
)
def cblocks(
    makefile: str = None,
    pattern: str = "",
    lucky: bool = False,
    start_check=lambda s: any([s.startswith(x) for x in ["## BEGIN:", "# BEGIN:"]]),
    end_check=lambda s: any([not s.strip(), not s.startswith("#")]),
):
    """
    Extract labeled comment-blocks.
    """
    blocks = collections.defaultdict(list)
    with open(makefile) as fhandle:
        lines = fhandle.readlines()
        for i, line in enumerate(lines):
            if start_check(line):
                label = line.split("BEGIN:")[-1].strip()
                for j in range(i + 1, len(lines)):
                    k = lines[j].strip()
                    is_div = all(
                        [
                            len(k) > 3,
                            not k.replace("#", "")
                            .replace("-", "")
                            .replace("_", "")
                            .replace("░", "")
                            .strip(),
                        ]
                    )
                    if is_div or end_check(k):
                        break
                    else:
                        k = k[1:]
                        if k.startswith("#"):
                            k = k[1:].strip()
                        blocks[label].append(k)
    out = blocks
    if pattern:
        tmp = {}
        for k in blocks:
            if re.match(f".*{pattern}.*", k):
                tmp[k] = blocks[k]
        out = tmp
    if lucky:
        out = list(out.items())
        out = out[0] if out else None
        out = dict(label=out[0], block=out[1]) if out else None
    return json_output(out)


## Final Assembly & Main Entrypoint
##░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░


@click.group()
def main():
    """
    mk.parse: Makefile parsing and metadata extraction.
    """


[main.add_command(x) for x in [vars, stats, cblocks, database, db, targets, includes]]

if __name__ == "__main__":
    main()
