"""
Drone Path Prediction Pipeline

Steps:
0. Extract telemetry (altitude, GPS) from subtitle stream
1. Sample frames (configurable step)
2. Compute optical flow between consecutive frames
3. Convert pixel motion → world coordinates (intrinsics + altitude)
4. Accumulate path with drift correction (optional: GPS anchors)
5. Visualize on map with GPS reference point
"""

import re
from dataclasses import dataclass

import ffmpeg


@dataclass(frozen=True)
class TelemetryFrame:
    """Single frame of drone telemetry data."""

    timestamp_sec: float
    longitude: float
    latitude: float
    gps_altitude: float
    distance_from_home: float
    height: float


# Regex pattern for parsing DJI SRT telemetry lines
TELEMETRY_PATTERN = re.compile(
    r"GPS\s*\(([\d.]+),\s*([\d.]+),\s*([-\d.]+)\),\s*"
    r"D\s*([\d.]+)m,\s*"
    r"H\s*([-\d.]+)m,\s*"
)

TIMESTAMP_PATTERN = re.compile(r"(\d+):(\d+):(\d+),(\d+)")


def extract_srt_content(video_path: str, stream_index: str = "0:2") -> str:
    """Extract subtitle stream from video to string.

    Args:
        video_path: Path to video file
        stream_index: Stream map index (default '0:2' for DJI subtitle)

    Returns:
        SRT content as string
    """
    out, _ = (
        ffmpeg.input(video_path)
        .output("pipe:", format="srt", map=stream_index)
        .run(capture_stdout=True, capture_stderr=True)
    )
    return out.decode("utf-8")


def parse_timestamp(timestamp_line: str) -> float | None:
    """Parse SRT timestamp to seconds."""
    match = TIMESTAMP_PATTERN.match(timestamp_line)
    if not match:
        return None
    h, m, s, ms = map(int, match.groups())
    return h * 3600 + m * 60 + s + ms / 1000


def parse_telemetry_line(data_line: str) -> dict | None:
    """Parse telemetry data from SRT content line."""
    match = TELEMETRY_PATTERN.search(data_line)
    if not match:
        return None
    return {
        "longitude": float(match.group(1)),
        "latitude": float(match.group(2)),
        "gps_altitude": float(match.group(3)),
        "distance_from_home": float(match.group(4)),
        "height": float(match.group(5)),
    }


def parse_srt_telemetry(srt_content: str) -> list[TelemetryFrame]:
    """Parse SRT telemetry content into structured frames.

    Args:
        srt_content: Raw SRT file content

    Returns:
        List of TelemetryFrame objects
    """
    frames: list[TelemetryFrame] = []
    blocks = re.split(r"\n\n+", srt_content.strip())

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue

        timestamp = parse_timestamp(lines[1])
        if timestamp is None:
            continue

        telemetry = parse_telemetry_line(" ".join(lines[2:]))
        if telemetry is None:
            continue

        frames.append(TelemetryFrame(timestamp_sec=timestamp, **telemetry))

    return frames


if __name__ == "__main__":
    VIDEO_PATH = "/Users/agerasymchuk/private_repo/cv_nav/data/video1.MP4"

    # Step 0: Extract and parse telemetry
    print("Extracting telemetry from video...")
    srt_content = extract_srt_content(VIDEO_PATH)

    print("Parsing telemetry data...")
    frames = parse_srt_telemetry(srt_content)

    print(f"\n✓ Parsed {len(frames)} telemetry frames")
    print(f"\nFirst frame: {frames[0]}")
    print(f"Last frame:  {frames[-1]}")
