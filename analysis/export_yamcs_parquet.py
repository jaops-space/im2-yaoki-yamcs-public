#!/usr/bin/env python3
"""Export the YAOKI telemetry and command streams used by the analysis notebooks to parquet."""

from __future__ import annotations

import argparse
import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import pandas as pd
import yaml
from yamcs.client import YamcsClient

def require_keys(mapping: dict[str, Any], keys: tuple[str, ...], context: str) -> None:
    missing = [key for key in keys if key not in mapping]
    if missing:
        raise ValueError(f"{context} is missing required key(s): {', '.join(missing)}")


def load_config(path: Path) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    require_keys(
        config,
        ("defaults", "telemetry_streams", "commands"),
        str(path),
    )
    require_keys(
        config["defaults"],
        ("url", "instance", "output_dir", "start", "stop"),
        f"{path}: defaults",
    )
    require_keys(config["commands"], ("source_name", "description", "file", "fields"), f"{path}: commands")
    for index, stream in enumerate(config["telemetry_streams"]):
        require_keys(stream, ("name", "display_name", "description", "file", "fields"), f"{path}: telemetry_streams[{index}]")
    return config

def to_utc(value: Any) -> pd.Timestamp:
    if value is None or value is pd.NaT:
        return pd.NaT
    ts = pd.Timestamp(value)
    return ts.tz_convert("UTC") if ts.tzinfo else ts.tz_localize("UTC")

def scalar_value(value: Any) -> Any:
    """Convert Yamcs scalar wrappers into parquet-friendly Python values."""
    if value is None:
        return None
    for attr in ("value", "raw_value", "eng_value"):
        if hasattr(value, attr):
            return scalar_value(getattr(value, attr))
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def observed_range(series: pd.Series) -> dict[str, Any]:
    clean = series.dropna()
    result: dict[str, Any] = {
        "null_count": int(series.isna().sum()),
        "non_null_count": int(clean.size),
    }
    if clean.empty:
        return result
    if pd.api.types.is_datetime64_any_dtype(series):
        result["min"] = clean.min().isoformat()
        result["max"] = clean.max().isoformat()
    elif pd.api.types.is_numeric_dtype(series):
        result["min"] = scalar_value(clean.min())
        result["max"] = scalar_value(clean.max())
    elif clean.nunique(dropna=True) <= 20:
        result["values"] = [scalar_value(value) for value in clean.drop_duplicates()]
    return result


def write_metadata(
    df: pd.DataFrame,
    output_path: Path,
    *,
    kind: str,
    source_name: str,
    description: str,
    field_descriptions: dict[str, str],
    display_name: str | None = None,
    unit: str | None = None,
) -> Path:
    metadata_path = output_path.with_suffix(".metadata.yaml")
    metadata = {
            "kind": kind,
            "source_name": source_name,
            "description": description,
            "rows": len(df),
            "fields": {
                column: {
                    "description": field_descriptions.get(column, "No description available."),
                    "dtype": str(df[column].dtype),
                    "observed": observed_range(df[column]),
                }
                for column in df.columns
            },
        }
    if display_name is not None:
        metadata["display_name"] = display_name
    if unit is not None:
        metadata["unit"] = unit
    metadata_path.write_text(yaml.safe_dump(metadata, sort_keys=False), encoding="utf-8")
    return metadata_path

def export_telemetry_stream(
    archive: Any,
    stream: dict[str, Any],
    output_path: Path,
    start: datetime,
    stop: datetime,
) -> int:
    stream_name = stream["name"]
    rows = []
    for pval in archive.list_parameter_values(stream_name, descending=False, start=start, stop=stop):
        rows.append(
            {
                "generation_time": to_utc(getattr(pval, "generation_time", None)),
                "acquisition_time": to_utc(getattr(pval, "acquisition_time", None)),
                "raw_value": scalar_value(getattr(pval, "raw_value", None)),
                "eng_value": scalar_value(getattr(pval, "eng_value", None)),
            }
        )

    df = pd.DataFrame(
        rows,
        columns=[
            "generation_time",
            "acquisition_time",
            "raw_value",
            "eng_value",
        ],
    )
    df.to_parquet(output_path, index=False)
    write_metadata(
        df,
        output_path,
        kind="telemetry",
        source_name=stream_name,
        description=stream["description"],
        field_descriptions=stream["fields"],
        display_name=stream["display_name"],
        unit=stream.get("unit"),
    )
    return len(df)


def export_commands(
    archive: Any,
    output_path: Path,
    start: datetime,
    stop: datetime,
    metadata: dict[str, Any],
) -> int:
    blob = b"".join(archive.export_commands(start=start, stop=stop))
    df = pd.read_csv(io.StringIO(blob.decode("utf-8")), sep="\t")
    if "Generation Time" in df:
        df["Generation Time"] = pd.to_datetime(df["Generation Time"], utc=True)
    df.to_parquet(output_path, index=False)
    write_metadata(
        df,
        output_path,
        kind="commands",
        source_name=metadata["source_name"],
        description=metadata["description"],
        field_descriptions=metadata["fields"],
    )
    return len(df)


def main() -> None:
    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument("--config", default="export_yamcs_parquet.yaml", type=Path, help="YAML export configuration")
    config_args, _ = config_parser.parse_known_args()
    config = load_config(config_args.config)
    defaults = config["defaults"]

    parser = argparse.ArgumentParser(description=__doc__, parents=[config_parser])
    parser.add_argument("--url", default=defaults["url"], help=f"Yamcs URL, default: {defaults['url']}")
    parser.add_argument(
        "--instance",
        default=defaults["instance"],
        help=f"Yamcs instance, default: {defaults['instance']}",
    )
    parser.add_argument("--output-dir", default=defaults["output_dir"], type=Path, help="Directory for parquet output")
    parser.add_argument("--start", default=defaults["start"], help="Export start timestamp")
    parser.add_argument("--stop", default=defaults["stop"], help="Export stop timestamp")
    args = parser.parse_args()

    start = datetime.fromisoformat(args.start)
    stop = datetime.fromisoformat(args.stop)

    telemetry_dir = args.output_dir / "telemetry"
    command_dir = args.output_dir / "commands"
    for directory in (telemetry_dir, command_dir):
        directory.mkdir(parents=True, exist_ok=True)

    client = YamcsClient(args.url)
    archive = client.get_archive(instance=args.instance)

    manifest: dict[str, Any] = {
        "source_url": args.url,
        "source_instance": args.instance,
        "start": start.astimezone(timezone.utc).isoformat(),
        "stop": stop.astimezone(timezone.utc).isoformat(),
        "telemetry_streams": {},
        "commands": {},
    }

    print(f"Exporting telemetry streams to {telemetry_dir}")
    for stream in config["telemetry_streams"]:
        stream_name = stream["name"]
        filename = stream["file"]
        if filename.startswith("TODO:"):
            raise ValueError(
                f"Stream {stream_name!r} has an unresolved filename conflict.\n"
                f"Edit the 'file:' key in the config to a unique filename.\n"
                f"Hint: {filename}"
            )
        output_path = telemetry_dir / filename
        count = export_telemetry_stream(
            archive,
            stream,
            output_path,
            start,
            stop,
        )
        manifest["telemetry_streams"][stream_name] = {
            "file": str(output_path.relative_to(args.output_dir)),
            "metadata": str(output_path.with_suffix(".metadata.yaml").relative_to(args.output_dir)),
            "rows": count,
        }
        print(f"  {stream_name}: {count} rows")

    command_path = command_dir / config["commands"]["file"]
    count = export_commands(archive, command_path, start, stop, config["commands"])
    manifest["commands"] = {
        "file": str(command_path.relative_to(args.output_dir)),
        "metadata": str(command_path.with_suffix(".metadata.yaml").relative_to(args.output_dir)),
        "rows": count,
    }
    print(f"Exported commands: {count} rows")

    manifest_path = args.output_dir / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    print(f"Wrote manifest: {manifest_path}")


if __name__ == "__main__":
    main()
