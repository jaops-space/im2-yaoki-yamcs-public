#!/usr/bin/env python3
"""Export the YAOKI telemetry and command streams used by the analysis notebooks to parquet."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from yamcs.client import YamcsClient


YAMCS_URL = "localhost:8090"
YAMCS_INSTANCE = "im2-yaoki"

IM2_LAUNCH_DATE = "2025-02-27T00:16:30Z"
YAOKI_FIRST_TELEMETRY_DATE = "2025-03-07 02:17:15.150000+00:00"
YAOKI_LAST_TELEMETRY_DATE = "2025-03-07 04:33:04.389000+00:00"


TELEMETRY_STREAMS = [
    *(f"/YAOKI/Rover/ADC_TEMP{i}" for i in range(8)),
    *(f"/YAOKI/Lander/temperature{i}" for i in range(2)),
    "/YAOKI/Rover/last_rssi",
    "/YAOKI/Rover/Rx_cnt",
    "/YAOKI/Rover/RxError_cnt",
    "/YAOKI/Rover/Tx_cnt",
    "/YAOKI/Rover/CamSend_num",
    "/YAOKI/Rover/CamSent_cnt",
    "/YAOKI/Rover/last_packet_num",
    "/YAOKI/Rover/missing_packet_cnt",
    "YAOKI/Xr",
    "YAOKI/x",
    "YAOKI/Yr",
    "YAOKI/y",
    "YAOKI/Zr",
    "YAOKI/z",
]

STATUS_STREAMS = [
    "/YAOKI/Rover/Status_BAT",
    "/YAOKI/Rover/VBAT_CHECK",
    "/YAOKI/Rover/Status_ICUT",
    "/YAOKI/Rover/Status_WCUT",
    "/YAOKI/Rover/Status_CAM",
    "/YAOKI/Rover/Status_MOVE",
    "/YAOKI/Rover/Status_NORX",
    "/YAOKI/Rover/Status_TLM",
]

TELEMETRY_METADATA = {
    "/YAOKI/Rover/ADC_TEMP0": {
        "display_name": "R0: Body (Bottom)",
        "description": "Rover temperature sensor 0, mounted on the bottom of the rover body.",
        "unit": "deg C",
    },
    "/YAOKI/Rover/ADC_TEMP1": {
        "display_name": "R1: Motor board (middleboard)",
        "description": "Rover temperature sensor 1, mounted on the motor board on the middle board stack.",
        "unit": "deg C",
    },
    "/YAOKI/Rover/ADC_TEMP2": {
        "display_name": "R2: UHF radio",
        "description": "Rover temperature sensor 2, mounted at the UHF radio.",
        "unit": "deg C",
    },
    "/YAOKI/Rover/ADC_TEMP3": {
        "display_name": "R3: Body (Top)",
        "description": "Rover temperature sensor 3, mounted on the top of the rover body.",
        "unit": "deg C",
    },
    "/YAOKI/Rover/ADC_TEMP4": {
        "display_name": "R4: On CPU (Middle)",
        "description": "Rover temperature sensor 4, mounted near the CPU on the middle board.",
        "unit": "deg C",
    },
    "/YAOKI/Rover/ADC_TEMP5": {
        "display_name": "R5: Temperature data not sent",
        "description": "Rover temperature sensor 5. No samples are present in this exported dataset because this temperature channel was not sent in telemetry.",
        "unit": "deg C",
    },
    "/YAOKI/Rover/ADC_TEMP6": {
        "display_name": "R6: Battery (Bottom)",
        "description": "Rover temperature sensor 6, mounted at the bottom of the battery.",
        "unit": "deg C",
    },
    "/YAOKI/Rover/ADC_TEMP7": {
        "display_name": "R7: Battery (Top)",
        "description": "Rover temperature sensor 7, mounted at the top of the battery.",
        "unit": "deg C",
    },
    "/YAOKI/Lander/temperature0": {
        "display_name": "L0: Enclosure by burn wire",
        "description": "IM-2 lander temperature sensor 0, located on the YAOKI enclosure near the burn wire.",
        "unit": "deg C",
    },
    "/YAOKI/Lander/temperature1": {
        "display_name": "L1: Enclosure by mounting bracket",
        "description": "IM-2 lander temperature sensor 1, located on the YAOKI enclosure near the mounting bracket.",
        "unit": "deg C",
    },
    "/YAOKI/Rover/last_rssi": {
        "display_name": "Last RSSI",
        "description": "Last received RSSI value from the lander-rover UHF radio link.",
        "unit": "dBm",
    },
    "/YAOKI/Rover/Rx_cnt": {
        "display_name": "Valid command receive count",
        "description": "Rover counter for valid commands received. Pings are not commands. The counter runs from 0 to 98 and then resets to 0.",
        "unit": "count",
    },
    "/YAOKI/Rover/RxError_cnt": {
        "display_name": "Command receive error count",
        "description": "Rover counter for erroneous received commands that were not processed. The counter runs from 0 to 98 and then resets to 0.",
        "unit": "count",
    },
    "/YAOKI/Rover/Tx_cnt": {
        "display_name": "Telemetry transmit count",
        "description": "Rover counter for sent telemetry packet sets. It increments once per telemetry send allocation, roughly every 30 seconds, and resets after 98.",
        "unit": "count",
    },
    "/YAOKI/Rover/CamSend_num": {
        "display_name": "Current image number",
        "description": "Current image number being captured or sent by the rover camera.",
        "unit": "image number",
    },
    "/YAOKI/Rover/CamSent_cnt": {
        "display_name": "Images sent count",
        "description": "Rover counter that increments by one for every 960 camera packets sent, corresponding to one camera image. It resets after 99.",
        "unit": "count",
    },
    "/YAOKI/Rover/last_packet_num": {
        "display_name": "Last packet number",
        "description": "Last packet number received for the current rover camera image.",
        "unit": "packet number",
    },
    "/YAOKI/Rover/missing_packet_cnt": {
        "display_name": "Missing packet count",
        "description": "Number of missing packets for the current rover camera image.",
        "unit": "count",
    },
    "YAOKI/Xr": {
        "display_name": "Raw accelerometer X",
        "description": "Raw X-axis accelerometer reading directly read from the I2C bus without scaling or casting.",
        "unit": "raw counts",
    },
    "YAOKI/Yr": {
        "display_name": "Raw accelerometer Y",
        "description": "Raw Y-axis accelerometer reading directly read from the I2C bus without scaling or casting.",
        "unit": "raw counts",
    },
    "YAOKI/Zr": {
        "display_name": "Raw accelerometer Z",
        "description": "Raw Z-axis accelerometer reading directly read from the I2C bus without scaling or casting.",
        "unit": "raw counts",
    },
    "YAOKI/x": {
        "display_name": "Scaled accelerometer x",
        "description": "Scaled X-axis accelerometer reading cast to floating point.",
        "unit": "scaled accelerometer value",
    },
    "YAOKI/y": {
        "display_name": "Scaled accelerometer y",
        "description": "Scaled Y-axis accelerometer reading cast to floating point.",
        "unit": "scaled accelerometer value",
    },
    "YAOKI/z": {
        "display_name": "Scaled accelerometer z",
        "description": "Scaled Z-axis accelerometer reading cast to floating point.",
        "unit": "scaled accelerometer value",
    },
}

STATUS_METADATA = {
    "/YAOKI/Rover/Status_BAT": {
        "display_name": "Battery on status",
        "description": "Binary rover status bit indicating whether rover battery power is on.",
    },
    "/YAOKI/Rover/VBAT_CHECK": {
        "display_name": "Power source check",
        "description": "Binary rover power-source status. 0 means lander power; 1 means internal YAOKI battery power.",
    },
    "/YAOKI/Rover/Status_ICUT": {
        "display_name": "Wire cut in progress",
        "description": "Binary rover status bit indicating that the deployment wire is currently being cut by the heater relay.",
    },
    "/YAOKI/Rover/Status_WCUT": {
        "display_name": "Wire cut complete",
        "description": "Binary rover status bit indicating that the wire-cut command was sent and the allocated wire-cut heater time elapsed.",
    },
    "/YAOKI/Rover/Status_CAM": {
        "display_name": "Camera active",
        "description": "Binary rover status bit indicating that the camera is actively taking a picture or sending camera data via CSP.",
    },
    "/YAOKI/Rover/Status_MOVE": {
        "display_name": "Move active",
        "description": "Binary rover status bit indicating that the rover should be moving because time remains on the most recent move command.",
    },
    "/YAOKI/Rover/Status_NORX": {
        "display_name": "No receive timeout",
        "description": "Binary rover status bit indicating that no pings were received for the configured timeout, approximately 3 minutes.",
    },
    "/YAOKI/Rover/Status_TLM": {
        "display_name": "Telemetry mode",
        "description": "Binary rover telemetry mode status. 1 means high-frequency telemetry mode; 0 means low-frequency telemetry mode.",
    },
}


def parse_timestamp(value: str) -> datetime:
    if value.endswith("Z"):
        value = value.replace("Z", "+00:00")
    return datetime.fromisoformat(value)


def stream_filename(stream_name: str) -> str:
    clean = stream_name.strip("/")
    clean = re.sub(r"[^A-Za-z0-9._-]+", "__", clean)
    return f"{clean}.parquet"


def to_utc(value: Any) -> pd.Timestamp | None:
    if value is None:
        return None
    return pd.Timestamp(value).tz_convert("UTC") if pd.Timestamp(value).tzinfo else pd.Timestamp(value).tz_localize("UTC")


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


def metadata_for_dataframe(
    df: pd.DataFrame,
    *,
    kind: str,
    source_name: str,
    description: str,
    field_descriptions: dict[str, str],
    display_name: str | None = None,
    unit: str | None = None,
) -> dict[str, Any]:
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
    return metadata


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
    metadata_path = output_path.with_suffix(".metadata.json")
    metadata = metadata_for_dataframe(
        df,
        kind=kind,
        source_name=source_name,
        description=description,
        field_descriptions=field_descriptions,
        display_name=display_name,
        unit=unit,
    )
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata_path


TELEMETRY_FIELD_DESCRIPTIONS = {
    "generation_time": "UTC timestamp assigned when this telemetry sample was generated.",
    "acquisition_time": "UTC timestamp when the sample was acquired, when available in the source data.",
}

STATUS_FIELD_DESCRIPTIONS = {
    "status": "Decoded binary status value for this interval. 0 means off or false; 1 means on or true.",
    "start": "UTC start timestamp for the interval where the status held this value.",
    "stop": "UTC stop timestamp for the interval where the status held this value.",
}

COMMAND_FIELD_DESCRIPTIONS = {
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
}


def telemetry_field_descriptions(stream_name: str) -> dict[str, str]:
    stream_metadata = TELEMETRY_METADATA[stream_name]
    name = stream_metadata["display_name"]
    unit = stream_metadata.get("unit")
    unit_text = f" Units: {unit}." if unit else ""
    return {
        **TELEMETRY_FIELD_DESCRIPTIONS,
        "raw_value": f"Raw telemetry value for {name}.{unit_text}",
        "eng_value": f"Engineering value for {name}.{unit_text} For these exported YAOKI streams this is normally identical to raw_value unless the source archive supplied a calibrated value.",
    }


def export_telemetry_stream(archive: Any, stream_name: str, output_path: Path, start: datetime, stop: datetime) -> int:
    rows = []
    for pval in archive.list_parameter_values(stream_name, descending=False, start=start, stop=stop):
        raw_value = scalar_value(getattr(pval, "raw_value", None))
        eng_value = scalar_value(getattr(pval, "eng_value", None))
        rows.append(
            {
                "generation_time": to_utc(getattr(pval, "generation_time", None)),
                "acquisition_time": to_utc(getattr(pval, "acquisition_time", None)),
                "raw_value": raw_value,
                "eng_value": eng_value,
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
    stream_metadata = TELEMETRY_METADATA[stream_name]
    write_metadata(
        df,
        output_path,
        kind="telemetry",
        source_name=stream_name,
        description=stream_metadata["description"],
        field_descriptions=telemetry_field_descriptions(stream_name),
        display_name=stream_metadata["display_name"],
        unit=stream_metadata.get("unit"),
    )
    return len(df)


def export_status_stream(
    archive: Any,
    stream_name: str,
    output_path: Path,
    start: datetime,
    stop: datetime,
    min_gap: float,
) -> int:
    rows = []
    for prange in archive.list_parameter_ranges(stream_name, start=start, stop=stop, min_gap=min_gap):
        rows.append(
            {
                "status": scalar_value(getattr(prange, "eng_value", None)),
                "start": to_utc(getattr(prange, "start", None)),
                "stop": to_utc(getattr(prange, "stop", None)),
            }
        )

    df = pd.DataFrame(rows, columns=["status", "start", "stop"])
    df.to_parquet(output_path, index=False)
    stream_metadata = STATUS_METADATA[stream_name]
    write_metadata(
        df,
        output_path,
        kind="status",
        source_name=stream_name,
        description=stream_metadata["description"],
        field_descriptions=STATUS_FIELD_DESCRIPTIONS,
        display_name=stream_metadata["display_name"],
    )
    return len(df)


def export_commands(archive: Any, output_path: Path, start: datetime, stop: datetime) -> int:
    import io

    blob = b"".join(archive.export_commands(start=start, stop=stop))
    df = pd.read_csv(io.StringIO(blob.decode("utf-8")), sep="\t")
    if "Generation Time" in df:
        df["Generation Time"] = pd.to_datetime(df["Generation Time"], utc=True)
    df.to_parquet(output_path, index=False)
    write_metadata(
        df,
        output_path,
        kind="commands",
        source_name="commands",
        description="Telecommands exported for the mission interval.",
        field_descriptions=COMMAND_FIELD_DESCRIPTIONS,
    )
    return len(df)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=YAMCS_URL, help=f"Yamcs URL, default: {YAMCS_URL}")
    parser.add_argument("--instance", default=YAMCS_INSTANCE, help=f"Yamcs instance, default: {YAMCS_INSTANCE}")
    parser.add_argument("--output-dir", default="yaoki_parquet", type=Path, help="Directory for parquet output")
    parser.add_argument("--start", default=IM2_LAUNCH_DATE, help="Export start timestamp")
    parser.add_argument(
        "--stop",
        default=(parse_timestamp(YAOKI_LAST_TELEMETRY_DATE) + timedelta(hours=1)).isoformat(),
        help="Export stop timestamp",
    )
    parser.add_argument("--range-min-gap", default=300.0, type=float, help="min_gap for status range exports")
    args = parser.parse_args()

    start = parse_timestamp(args.start)
    stop = parse_timestamp(args.stop)

    telemetry_dir = args.output_dir / "telemetry"
    status_dir = args.output_dir / "status"
    command_dir = args.output_dir / "commands"
    for directory in (telemetry_dir, status_dir, command_dir):
        directory.mkdir(parents=True, exist_ok=True)

    client = YamcsClient(args.url)
    archive = client.get_archive(instance=args.instance)

    manifest: dict[str, Any] = {
        "source_url": args.url,
        "source_instance": args.instance,
        "start": start.astimezone(timezone.utc).isoformat(),
        "stop": stop.astimezone(timezone.utc).isoformat(),
        "telemetry_streams": {},
        "status_streams": {},
        "commands": {},
    }

    print(f"Exporting telemetry streams to {telemetry_dir}")
    for stream_name in TELEMETRY_STREAMS:
        output_path = telemetry_dir / stream_filename(stream_name)
        count = export_telemetry_stream(archive, stream_name, output_path, start, stop)
        manifest["telemetry_streams"][stream_name] = {
            "file": str(output_path.relative_to(args.output_dir)),
            "metadata": str(output_path.with_suffix(".metadata.json").relative_to(args.output_dir)),
            "rows": count,
        }
        print(f"  {stream_name}: {count} rows")

    print(f"Exporting status streams to {status_dir}")
    for stream_name in STATUS_STREAMS:
        output_path = status_dir / stream_filename(stream_name)
        count = export_status_stream(archive, stream_name, output_path, start, stop, args.range_min_gap)
        manifest["status_streams"][stream_name] = {
            "file": str(output_path.relative_to(args.output_dir)),
            "metadata": str(output_path.with_suffix(".metadata.json").relative_to(args.output_dir)),
            "rows": count,
        }
        print(f"  {stream_name}: {count} rows")

    command_path = command_dir / "commands.parquet"
    count = export_commands(archive, command_path, start, stop)
    manifest["commands"] = {
        "file": str(command_path.relative_to(args.output_dir)),
        "metadata": str(command_path.with_suffix(".metadata.json").relative_to(args.output_dir)),
        "rows": count,
    }
    print(f"Exported commands: {count} rows")

    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote manifest: {args.output_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()
