"""Signal-cli HTTP daemon client for receiving messages via JSON-RPC."""

import asyncio
import json
import logging
import uuid
from configparser import ConfigParser
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from functools import partial
from pathlib import Path
from typing import Any, Awaitable, Callable

import pytak

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).parent
LOCAL_CONFIG_PATH = CONFIG_DIR / "local_config.ini"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "config.ini"


def load_config() -> ConfigParser:
    """Load configuration from INI file.

    Tries local_config.ini first, falls back to config.ini.
    """
    config = ConfigParser()
    if LOCAL_CONFIG_PATH.exists():
        config.read(LOCAL_CONFIG_PATH)
    else:
        config.read(DEFAULT_CONFIG_PATH)
    return config


class Affiliation(Enum):
    HOSTILE = "h"
    FRIENDLY = "f"
    NEUTRAL = "n"
    UNKNOWN = "u"


# CoT type codes for ground units
# Format: a-{affiliation}-G-{category}
COT_TYPE_MAP: dict[str, str] = {
    "tank": "G-U-C-F-M",  # Ground-Unit-Combat-Armor-MainBattleTank
    "apc": "G-U-C-F-A",  # Ground-Unit-Combat-Armor-APC
    "infantry": "G-U-C-I",  # Ground-Unit-Combat-Infantry
    "artillery": "G-U-C-F-D",  # Ground-Unit-Combat-Field Artillery
    "mlrs": "G-U-C-F-D-M",  # Ground-Unit-Combat-Field Artillery-MLRS
    "sam": "G-U-W-M-S",  # Ground-Unit-Weapon-Missile-SAM
    "radar": "G-U-S-R",  # Ground-Unit-Sensor-Radar
    "truck": "G-U-S-T",  # Ground-Unit-Support-Transport
    "helicopter": "A-M-H",  # Air-Military-Helicopter
    "drone": "A-M-F-Q",  # Air-Military-Fixed wing-UAV
}


@dataclass(frozen=True)
class CoordinateMessage:
    lat: float
    lon: float
    description: str
    affiliation: Affiliation = Affiliation.UNKNOWN
    event_id: str = field(default_factory=lambda: f"Signal-Bot-{uuid.uuid4()}")

    def __post_init__(self) -> None:
        # Validate latitude
        if not -90 <= self.lat <= 90:
            raise ValueError(f"Invalid latitude: {self.lat}")
        # Validate longitude
        if not -180 <= self.lon <= 180:
            raise ValueError(f"Invalid longitude: {self.lon}")
        # Validate label
        if not self.description:
            raise ValueError("Label cannot be empty")

    @classmethod
    def from_string(cls, text: str) -> "CoordinateMessage":
        """Parse 'lat lon label' format."""
        parts = text.strip().split(maxsplit=2)
        if len(parts) != 3:
            raise ValueError(f"Expected 'lat lon label', got: {text!r}")

        try:
            lat = float(parts[0])
            lon = float(parts[1])
        except ValueError as e:
            raise ValueError(f"Invalid coordinates: {e}") from e

        return cls(lat=lat, lon=lon, description=parts[2])

    @property
    def cot_type(self) -> str:
        """Generate CoT type string like 'a-h-G-U-C-F-M'."""
        base = COT_TYPE_MAP.get(self.description.lower())
        if not base:
            base = "G-U"
        return f"a-{self.affiliation.value}-{base}"

    def gen_cot(
        self,
        hae: float = 0,
        stale: int = 120,
        ce: int = 50,
        le: int = 9999999,
    ) -> bytes | None:
        return pytak.gen_cot(
            lat=self.lat,
            lon=self.lon,
            uid=self.event_id,
            ce=ce,
            le=le,
            hae=hae,
            cot_type=self.cot_type,
            stale=stale,
        )


async def _cot_message_handler(cot_message_raw: str, queue: asyncio.Queue) -> None:
    try:
        cot_bytes = CoordinateMessage.from_string(cot_message_raw).gen_cot()
        if cot_bytes:
            await queue.put(item=cot_bytes)
        else:
            logger.warning(f"Failed to generate cot bytes for : {cot_message_raw}")

    except ValueError:
        logger.warning(f"message could not be parsed: {cot_message_raw}")


MessageHandlerType = Callable[[str], Awaitable[None]]


async def receive_from_tcp_socket(
    host: str,
    port: int,
    message_handler: MessageHandlerType | None = None,
) -> None:
    """Connect to signal-cli daemon via TCP socket and read messages.

    Requires daemon started with: signal-cli -u <phone> daemon --tcp
    """
    logger.info(f"Connecting to signal-cli daemon at {host}:{port}...")

    while True:
        try:
            reader, writer = await asyncio.open_connection(host, port)
            logger.info(f"Connected to {host}:{port}")
            try:
                while True:
                    line = await reader.readline()
                    if not line:
                        logger.warning("Connection closed by server")
                        break

                    line_str = line.decode("utf-8").strip()
                    if not line_str:
                        continue

                    logger.debug(f"Raw: {line_str}")

                    try:
                        message = json.loads(line_str)
                        await handle_socket_message(
                            message, message_hanlder=message_handler
                        )
                    except json.JSONDecodeError:
                        logger.debug(f"Non-JSON: {line_str}")

            finally:
                writer.close()
                await writer.wait_closed()

        except ConnectionRefusedError:
            logger.error("Connection refused. Is daemon running with --tcp?")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Connection error: {e}, reconnecting in 5s...")
            await asyncio.sleep(5)


async def handle_socket_message(
    message: dict[str, Any],
    message_hanlder: MessageHandlerType | None = None,
    filter_param: str = "dataMessage",
) -> None:
    """
    Generic message handler, can be configured for concrete strategy via callback message_hanlder
    """
    method = message.get("method")

    if method == "receive":
        params = message.get("params", {})
        envelope = params.get("envelope", {})
        if filter_param not in envelope:
            return

        account = params.get("account")

        source = envelope.get("sourceNumber") or envelope.get("source")
        data_message = envelope.get("dataMessage", {})
        text = data_message.get("message")

        if text:
            logger.info(f"[{account[:7]}...] Message from {source[:10]}...: {text}")
            if message_hanlder:
                await message_hanlder(text)
        else:
            logger.debug(f"Non-text message from {source}...: {envelope.keys()}")
    else:
        logger.debug(f"Other notification: {message}")


async def run(cmd: str) -> asyncio.subprocess.Process:
    """Start a long-running process without waiting for output."""

    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.DEVNULL,  # we do not care about out
        stderr=asyncio.subprocess.DEVNULL,
    )
    logger.info(f"Started process: {cmd!r} (PID: {proc.pid})")
    return proc


@asynccontextmanager
async def cleaning_up_proc(cmd):
    process = await run(cmd)
    try:
        yield
    finally:
        process.terminate()
        await process.wait()


async def run_incomming_message_processing(
    cmd: str, queue: asyncio.Queue, host: str, port: int
) -> None:
    cot_message_handler = partial(_cot_message_handler, queue=queue)  # type: ignore
    async with cleaning_up_proc(cmd):
        await receive_from_tcp_socket(host, port, cot_message_handler)


async def main():
    app_config = load_config()
    phone_number = app_config.get("signal", "phone_number")
    daemon_host = app_config.get("signal", "daemon_host")
    daemon_port = app_config.getint("signal", "daemon_port")
    cot_url = app_config.get("wintak", "cot_url")
    cmd = f"signal-cli -u {phone_number} daemon --tcp"

    pytak_config = ConfigParser()
    pytak_config["pytak"] = {"COT_URL": cot_url}
    config = pytak_config["pytak"]

    # Initializes worker queues and tasks.
    clitool = pytak.CLITool(config)
    await clitool.setup()
    queue = clitool.tx_queue

    async with asyncio.TaskGroup() as tg:
        tg.create_task(
            run_incomming_message_processing(cmd, queue, daemon_host, daemon_port)
        )  # type: ignore
        tg.create_task(clitool.run())


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    asyncio.run(main())
