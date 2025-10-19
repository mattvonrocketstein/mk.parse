#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "click","jinja2","rich",
# ]
# ///
import os
import re
import json
import typing
import logging
import tempfile
from pathlib import Path

import click
import jinja2
from rich.console import Console
from rich.logging import RichHandler

# parser = parse
help_t = """
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

stderr = CONSOLE = Console(stderr=True)
_recipe_pattern = "#  recipe to execute (from '"
_variables_pattern = "# Variables"
_ht_stats_pattern = "# files hash-table stats:"


def get_logger(name, console=stderr):
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

    # FIXME: get this from some kind of global config
    # logger.setLevel("DEBUG")
    logger.setLevel("info".upper())

    return logger


LOGGER = get_logger(__name__)


def json_output(out):
    print(json.dumps(out, indent=2))
    return out


def validate_makefile(makefile: str):
    assert makefile
    tmp = Path(makefile)
    if not all(
        [
            tmp.exists,
            tmp.is_file,
        ]
    ):
        raise ValueError(f"{makefile} does not exist")
    else:
        LOGGER.warning(f"parsing makefile @ {makefile}")


def _get_prov_line(body):
    """ """
    pline = [x for x in body if _recipe_pattern in x]
    pline = pline[0] if pline else None
    return pline


def _get_file(body=None, makefile=None):
    """WARNING: answers according to make's db, but often still wrong!"""
    pline = _get_prov_line(body)
    if pline:
        return pline.split(_recipe_pattern)[-1].split("'")[0]
    else:
        return str(makefile)


@click.command()
@click.argument("makefile")
def includes(makefile: str = ""):
    """ """
    validate_makefile(makefile)
    with open(makefile) as fhandle:
        lines = fhandle.readlines()
        includes = [line for line in lines if line.startswith("include ")]
        includes = [line.split()[1:] for line in includes]
    return json_output(includes)


def _database(makefile: str = "", make="make") -> typing.List[str]:
    """
    Get database for Makefile
    (This output comes from 'make --print-data-base')
    FIXME: nix the temporary file..
    """
    LOGGER.critical(f"building database for {makefile}")
    validate_makefile(makefile)
    cmd = f"{make} --print-data-base -pqRrs -f {makefile} > .tmp.mk.db"
    os.system(cmd)
    out = open(".tmp.mk.db").read().split("\n")
    os.remove(".tmp.mk.db")
    return out


@click.command()
@click.option("--target", help="Retrieves help for named target only")
@click.option(
    "--markdown",
    is_flag=True,
    default=False,
    help="Enriches docs by guessing at markdown formatting",
)
@click.option(
    "--body",
    is_flag=True,
    default=False,
    help="Enriches docs by guessing at markdown formatting",
)
@click.option(
    "--public",
    is_flag=True,
    default=False,
    help="Filter for public targets only (no prefix in {self|.})",
)
@click.option(
    "--private",
    is_flag=True,
    default=False,
    help="Filter for private targets only (prefix in {self|.})",
)
@click.option(
    "--locals",
    is_flag=True,
    default=False,
    help="Filter for local targets only (no includes)",
)
@click.option("--local", is_flag=True, default=False, help="Alias for --locals")
@click.option(
    "--interpolate", is_flag=True, default=False, help="Interpolate docstrings"
)
@click.option(
    "--parametrics",
    is_flag=True,
    default=False,
    help="Filter for parametric-targets only (using '%')",
)
@click.option(
    "--preview", is_flag=True, default=False, help="Pretty-printer (implies --markdown)"
)
@click.option(
    "--module-docs", is_flag=True, default=False, help="Only return module docs"
)
@click.argument("makefile")
def targets(
    makefile: str = None,
    target: str = "",
    body: bool = False,
    interpolate: bool = False,
    locals: bool = False,
    local: bool = False,
    public: bool = False,
    private: bool = False,
    parametrics: bool = False,
    preview: bool = False,
    markdown: bool = False,
    module_docs: bool = False,
    parse_target_aliases: bool = True,
    **kwargs,
):
    """
    Parse Makefile to JSON.  Includes targets/prereqs details and documentation.
    """
    markdown = markdown or preview
    locals = locals or local
    body = body or interpolate

    def _enricher(text, pattern):
        """ """
        # raise Exception(text)
        pat = re.compile(pattern, re.MULTILINE)

        def rrr(match):
            label = match.group("label")
            indent = match.group("indent")
            content = match.group("content")
            dedented_content = re.sub(r"^[\t\s]{2,4}", "", content, flags=re.MULTILINE)
            code_block = (
                f"{indent}\n\nEXAMPLE:{label}\n\n```bash\n{dedented_content}```\n"
            )
            return code_block

        result = pat.sub(rrr, text)
        return result

    def _test(x):
        """ """
        tests = [
            ":" in x.strip(),
            not x.startswith("#"),
            not x.startswith("\t"),
        ]
        return all(tests)

    def zip_markdown(docs):
        if isinstance(docs, (str,)):
            docs = docs.split("\n")
        rfmt = [""]
        while docs:
            tmp = docs.pop(0)
            if any(tmp.lstrip().startswith(x) for x in "* |".split()) or any(
                x in tmp for x in "USAGE: EXAMPLE: ```".split()
            ):
                rfmt = rfmt + [tmp] + docs
                break
            if tmp.lstrip().startswith("---"):
                rfmt += [tmp]
                continue
            elif tmp:
                rfmt[-1] += f" {tmp}"
            else:
                rfmt += ["", tmp]
        return rfmt

    assert makefile and os.path.exists(makefile), f"file @ {makefile} does not exist"
    db = _database(makefile, **kwargs)
    raw_content = open(makefile).read()
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
            tline.startswith(" ") or tline.startswith(x) for x in "$ @ & \t".split(" ")
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
        pline = _get_prov_line(target_body)
        file = _get_file(
            body=target_body,
            makefile=makefile,
        )
        # file can still be wrong in the makefile database, depends how include happened..
        if file == makefile and not re.findall(
            f"^{target_name}:.*", raw_content, re.MULTILINE
        ):
            file = None
        if pline:
            # take advice from make's database.
            # we return this because it's authoritative,
            # but actually sometimes it's wrong.  this returns
            # the first like of the target that's tab-indented,
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
        target_body = [b.lstrip() for b in target_body if not b.startswith("#  ")]
        out[target_name] = {
            "file": file,
            "lineno": lineno,
            "header": header,
            "body": target_body,
            "parametric": "%" in target_name,
            "chain": None,
            "type": type,
            "docs": [x[len("\t@#") :] for x in target_body if x.startswith("\t@#")],
            "prereqs": list(set(prereqs)),
        }
        if type == "implicit":
            regex = target_name.replace("%", ".*")
            out[target_name].update(regex=regex)
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
            out[target_name]["docs"] = out[tmeta["chain"]]["docs"]
        # user requested enriching docs with markdown
        if markdown:
            docs = [x.lstrip() for x in out[target_name]["docs"]]
            for i, line in enumerate(docs):
                if line.startswith("EXAMPLE:") or line.startswith("USAGE:"):
                    docs[i] = (
                        line.replace("EXAMPLE:", "*EXAMPLE:*")
                        .replace("USAGE:", "*USAGE:*")
                        .replace("REFS:", "*REFS:*")
                        + "\n```bash"
                    )
                    for j, line2 in enumerate(docs[i:]):
                        if not line2:
                            docs[i + j] = line2 + "```\n"
                            break
            zmd = zip_markdown(docs)
            out[target_name]["docs"] = [] if zmd == [""] else zmd
    ALL = out.copy()

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
        tmp = {}
        for k, v in out.items():
            if v["file"] == makefile:
                tmp[k] = v
        out = tmp

    # user requested target aliases should be treated
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

    # user requested target-search
    if target:
        out = out[target]

    # filter: user requested only public targets
    if public:
        out = {
            k: v
            for k, v in out.items()
            if not any(k.startswith(x) for x in "self .".split())
        }
    # filter: user requested only private targets
    if private:
        out = {
            k: v
            for k, v in out.items()
            if any(k.startswith(x) for x in "self .".split())
        }

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

    # user requested lookup string or module docs
    if module_docs:
        modules = []
        blocks = {}
        for k in out.keys():
            k = k.strip().lstrip()
            k = k.split(".")[0]
            if not k:
                continue
            if k[0] in "_ \t $ self".split():
                continue
            if any(x in k for x in "& /".split(" ")):
                continue
            if k not in modules:
                modules.append(k)
        LOGGER.debug(f"found modules: {modules}")
        lines = open(makefile).readlines()
        for i, line in enumerate(lines):
            line = line.lstrip()
            if not line.startswith("#") and not line.startswith("@#"):
                continue
            if "BEGIN" in line:
                len(lines)
                for j, l2 in enumerate(lines[i:]):
                    if not l2.strip():
                        block_end = i + j - 1
                        break
                found = None
                for mod in modules:
                    if mod in line:
                        found = mod
                        break
                if not found:
                    LOGGER.warning(f"could not find module for block: {line}")
                    blocks[line[line.index("BEGIN") :].strip()] = lines[
                        i + 1 : block_end
                    ]
                else:
                    blocks[found] = lines[i:block_end]
        blocks = {
            k: [line[len("## ") :].strip() for line in v] for k, v in blocks.items()
        }
        for k, v in blocks.items():
            blocks[k] = zip_markdown(v[1:])

        if module_docs:
            return blocks

    if markdown:
        template = jinja2.Template(help_t)
        str_out = ""
        for target in out:
            str_out += "\n" + template.render(target=target, **out[target])
        if preview:
            # from python_on_whales import docker
            # import docker
            # client = docker.from_env()
            glow_img = "charmcli/glow:v1.5.1"
            glow_theme = "dracula"
            with tempfile.TemporaryDirectory() as tmpdir:
                path = os.path.join(tmpdir, "cache.json")
                fhandle = open(path, "w")
                # with tempfile.NamedTemporaryFile(delete_on_close=False) as fhandle:
                fhandle.write(str_out)
                fhandle.close()
                # print(str_out)
                has_glow = 0 == os.system("which glow")
                if has_glow:
                    LOGGER.warning(
                        "found that glow is installed, using it for previews"
                    )
                    cmd = f"cat  {path} | glow -s dracula"
                else:
                    LOGGER.warning("glow is missing, using docker version")
                    cmd = f"cat  {path} | docker run -q -i -v {tmpdir}:{tmpdir}  {glow_img} -s {glow_theme}"
                LOGGER.warning(f"calling \n{cmd}")
                os.system(cmd)
        else:
            print(str_out)
    else:
        json_output(out)


@click.group()
def main():
    """ """


# @main.command('db')
[main.add_command(x) for x in [targets, includes]]
if __name__ == "__main__":
    main()
