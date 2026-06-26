#!/usr/bin/env python3
"""Generate export_yamcs_parquet.yaml from the live YAMCS Mission Database.

Queries a running YAMCS server for every parameter under /YAOKI/Lander/* and
/YAOKI/Rover/* and emits a YAML in the shape expected by export_yamcs_parquet.py,
using exact strings taken from the MDB. The defaults and commands sections are
hardcoded constants below; only telemetry_streams is derived from the server.
"""
from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml
from yamcs.client import YamcsClient


def stream_filename(stream_name: str) -> str:
    clean = stream_name.strip("/")
    clean = re.sub(r"[^A-Za-z0-9._-]+", "__", clean)
    return f"{clean}.parquet"


DEFAULTS = {
    "url": "localhost:8090",
    "instance": "im2-yaoki",
    "output_dir": "yaoki_parquet",
    "start": "2025-02-27T00:16:30+00:00",
    "stop": "2025-03-07T05:42:56.476+00:00",
}

NAMESPACES = ["/YAOKI/Lander", "/YAOKI/Rover"]

GENERATION_TIME_DESC = (
    "UTC timestamp assigned when this telemetry sample was generated."
)
ACQUISITION_TIME_DESC = (
    "UTC timestamp when the sample was acquired, when available in the source data."
)

COMMANDS_BLOCK = {
    "source_name": "commands",
    "description": "Telecommands exported for the mission interval.",
    "file": "commands.parquet",
    "fields": {
        "Generation Time": "UTC timestamp when the command was generated.",
        "Command Name": "Fully qualified command name.",
        "Arguments": "Command arguments as exported from the source archive.",
        "Origin": "Command origin reported by the source archive.",
        "Sequence Number": "Command sequence number reported by the source archive.",
        "Username": "User name associated with the command.",
        "Queue": "Command queue name.",
        "Binary": "Binary command payload value, when available.",
        "Acknowledge_Queued": "Queued acknowledgement status.",
        "Acknowledge_Released": "Released acknowledgement status.",
        "Acknowledge_Sent": "Sent acknowledgement status.",
        "Completion": "Command completion status value, when available.",
        "Return Value": "Command return value, when available.",
    },
}


def under_namespace(qualified_name: str, namespaces: list[str]) -> str | None:
    for ns in namespaces:
        if qualified_name.startswith(ns + "/"):
            return ns
    return None


def clean_text(text: str | None) -> str:
    if not text:
        return ""
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def derive_display_name(param: Any) -> str:
    short = clean_text(param.description)
    if short and "\n" not in short and len(short) <= 80:
        return short
    return param.qualified_name.rsplit("/", 1)[-1]


def derive_unit(param: Any) -> str:
    return param.units[0] if param.units else "unitless"


def telemetry_entry(param: Any) -> dict[str, Any]:
    display_name = derive_display_name(param)
    unit = derive_unit(param)
    description = clean_text(param.long_description)

    if param.type == "enumeration":
        labels = ", ".join(f"{e.value}={e.label}" for e in (param.enum_values or []))
        raw_desc = (
            f"Raw integer code for {display_name}."
            + (f" Enumeration: {labels}." if labels else "")
        )
        eng_desc = (
            f"Decoded enumeration label for {display_name} as defined by the MDB."
            + (f" Mapping: {labels}." if labels else "")
        )
    else:
        raw_desc = f"Raw telemetry value for {display_name}. Units: {unit}."
        eng_desc = (
            f"Engineering value for {display_name}. Units: {unit}. "
            f"Identical to raw_value unless the MDB defines a calibrator."
        )

    return {
        "name": param.qualified_name,
        "display_name": display_name,
        "description": description,
        "unit": unit,
        "type": param.type,
        "file": stream_filename(param.qualified_name),
        "fields": {
            "generation_time": GENERATION_TIME_DESC,
            "acquisition_time": ACQUISITION_TIME_DESC,
            "raw_value": raw_desc,
            "eng_value": eng_desc,
        },
    }


def annotate_filename_conflicts(streams: list[dict[str, Any]]) -> list[str]:
    """Inject a file: TODO marker into streams whose filenames collide case-insensitively.

    Returns warning strings for each conflict group found.
    """
    groups: dict[str, list[int]] = defaultdict(list)
    for i, stream in enumerate(streams):
        groups[stream_filename(stream["name"]).lower()].append(i)

    warnings = []
    for fname, indices in groups.items():
        if len(indices) < 2:
            continue
        names = [streams[i]["name"] for i in indices]
        for i in indices:
            others = [n for n in names if n != streams[i]["name"]]
            default = streams[i]["file"]
            streams[i]["file"] = (
                f"TODO: rename '{default}' to resolve case-insensitive filename collision with: {', '.join(others)}"
            )
        warnings.append(f"Filename collision on {fname!r}: {', '.join(names)}")
    return warnings


def build_telemetry_streams(mdb: Any, namespaces: list[str]) -> list[dict[str, Any]]:
    ns_index = {ns: i for i, ns in enumerate(namespaces)}
    params = []
    for p in mdb.list_parameters():
        ns = under_namespace(p.qualified_name, namespaces)
        if ns is not None:
            params.append((ns_index[ns], p.qualified_name, p))
    params.sort(key=lambda t: (t[0], t[1]))
    return [telemetry_entry(p) for _, _, p in params]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULTS["url"], help="Yamcs URL")
    parser.add_argument("--instance", default=DEFAULTS["instance"], help="Yamcs instance")
    parser.add_argument(
        "--output",
        default=Path(__file__).resolve().parent / "export_yamcs_parquet.yaml",
        type=Path,
        help="Output YAML path",
    )
    parser.add_argument(
        "--namespace",
        action="append",
        default=None,
        help="Repeatable. Namespace prefix to include (default: /YAOKI/Lander, /YAOKI/Rover).",
    )
    args = parser.parse_args()

    namespaces = args.namespace if args.namespace else list(NAMESPACES)

    client = YamcsClient(args.url)
    mdb = client.get_mdb(instance=args.instance)
    telemetry_streams = build_telemetry_streams(mdb, namespaces)

    for w in annotate_filename_conflicts(telemetry_streams):
        print(f"WARNING: {w}")

    document = {
        "defaults": dict(DEFAULTS),
        "telemetry_streams": telemetry_streams,
        "commands": COMMANDS_BLOCK,
    }

    args.output.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(f"Wrote {len(telemetry_streams)} telemetry streams to {args.output}")


if __name__ == "__main__":
    main()
