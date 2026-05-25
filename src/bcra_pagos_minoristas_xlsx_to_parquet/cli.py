from __future__ import annotations

import json
from pathlib import Path

import typer

from .config import load_config
from .logging_utils import get_logger, log_event
from .pipeline import run_all, run_build, run_fetch, run_parse

app = typer.Typer(add_completion=False)
_LOGGER = get_logger(__name__)


def _write_metadata(payload: dict, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")


@app.command()
def fetch(
    config: Path | None = typer.Option(None, "--config", help="Path to bcra.toml"),
    log_level: str = typer.Option("INFO", "--log-level", help="Log verbosity"),
) -> None:
    _LOGGER.setLevel(log_level.upper())
    settings = load_config(config)
    result = run_fetch(settings)
    _write_metadata(
        {
            "discovery": result["discovery"].model_dump(),
            "downloads": [download.model_dump() for download in result["downloads"]],
        },
        Path("data/metadata/fetch.json"),
    )
    log_event(_LOGGER, "cli.fetch.completed")


@app.command()
def parse(
    config: Path | None = typer.Option(None, "--config", help="Path to bcra.toml"),
    log_level: str = typer.Option("INFO", "--log-level", help="Log verbosity"),
) -> None:
    _LOGGER.setLevel(log_level.upper())
    settings = load_config(config)
    parsed = run_parse(settings)
    _write_metadata(
        {"metadata": parsed.metadata.model_dump()},
        Path("data/metadata/parse.json"),
    )
    log_event(_LOGGER, "cli.parse.completed")


@app.command()
def build(
    config: Path | None = typer.Option(None, "--config", help="Path to bcra.toml"),
    log_level: str = typer.Option("INFO", "--log-level", help="Log verbosity"),
) -> None:
    _LOGGER.setLevel(log_level.upper())
    settings = load_config(config)
    result = run_build(settings)
    if "results" in result:
        payload = {
            "results": [
                {
                    "normalized": item["normalized"].model_dump(by_alias=True),
                    "storage": item["storage"].model_dump(),
                }
                for item in result["results"]
            ]
        }
    else:
        payload = {
            "normalized": result["normalized"].model_dump(by_alias=True),
            "storage": result["storage"].model_dump(),
        }
    _write_metadata(payload, Path("data/metadata/build.json"))
    log_event(_LOGGER, "cli.build.completed")


@app.command()
def run(
    config: Path | None = typer.Option(None, "--config", help="Path to bcra.toml"),
    log_level: str = typer.Option("INFO", "--log-level", help="Log verbosity"),
) -> None:
    _LOGGER.setLevel(log_level.upper())
    settings = load_config(config)
    result = run_all(settings)
    payload = {
        "discovery": result["discovery"].model_dump(),
        "downloads": [download.model_dump() for download in result["downloads"]],
        "results": [
            {
                "download": item["download"].model_dump(),
                "normalized": item["normalized"].model_dump(by_alias=True),
                "storage": item["storage"].model_dump(),
            }
            for item in result["results"]
        ],
    }
    _write_metadata(payload, Path("data/metadata/run.json"))
    log_event(_LOGGER, "cli.run.completed")
