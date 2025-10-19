FROM python:3.12-slim-trixie
# FROM docker
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
# RUN apk add --update --no-cache coreutils procps make curl tree
RUN apt-get update -y -qq && apt-get install -y -qq procps make curl tree
# RUN mkdir -p /opt/mkp
COPY mk.parse.py /usr/local/bin/mk.parse
RUN /usr/local/bin/mk.parse --help
COPY --from=charmcli/glow:v1.5.1 /usr/local/bin/glow /usr/local/bin/glow
ENTRYPOINT ["/usr/local/bin/mk.parse"]
