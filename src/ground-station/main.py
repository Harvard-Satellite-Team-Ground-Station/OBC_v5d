# +++++++++++++++++ IMPORTS +++++++++++++++++ #
import json
import time
import board
import digitalio
from lib.pysquared.logger import Logger
from lib.pysquared.nvm.counter import Counter
from lib.pysquared.config.config import Config
from lib.pysquared.hardware.busio import _spi_init
from lib.proveskit_rp2350_v5b.register import Register
from lib.pysquared.hardware.digitalio import initialize_pin
from lib.pysquared.hardware.radio.manager.rfm9x import RFM9xManager
from lib.pysquared.hardware.radio.packetizer.packet_manager import PacketManager


# +++++++++++++ INITIALIZATIONS +++++++++++++ #
error_count: Counter = Counter(index=Register.error_count)

config = Config("config.json")

logger: Logger = Logger(
    error_counter=error_count,
    colorized=False,
)

SPI0_CS0 = initialize_pin(
            logger, board.SPI0_CS0, digitalio.Direction.OUTPUT, True
        )

spi0 = _spi_init(
            logger,
            board.SPI0_SCK,
            board.SPI0_MOSI,
            board.SPI0_MISO,
        )

uhf_radio = RFM9xManager(
                logger,
                config.radio,
                spi0,
                SPI0_CS0,
                initialize_pin(logger, board.RF1_RST, digitalio.Direction.OUTPUT, True),
            )

uhf_packet_manager = PacketManager(
                logger,
                uhf_radio,
                config.radio.license,
                Counter(2),
                0.2,
            )


# +++++++++++++ FUNCTIONS +++++++++++++ #
def send_command(password: str, command: str,  args: list[str] = []):
    # Build message struct
    msg = {
        "name"      : config.cubesat_name,  # satellite name
        "command"   : command,
        "args"      : args,
        "password"  : password
    }

    # Serialize message and send
    msg_bytes = json.dumps(msg).encode("utf-8")
    uhf_packet_manager.send(msg_bytes)
    print(f"Sent command {command} with args {args}")


# +++++++++++++ MAIN LOOP +++++++++++++ #
    # for sending in a telecommand
    # all telemetry data will be acquired via star tracker
try:
    while True:
        # Prompt user for input
        user_input = input("\nEnter command (or 'exit' to quit): ").strip()

        if user_input.lower() in ("exit", "quit"):
            print("Exiting ground station.")
            break
        
        # Grab relevant parts of command
        parts = user_input.split()
        if len(parts) == 0:
            continue

        password = parts[0]
        command = parts[1]
        args = parts[2:] if len(parts) > 1 else []

        # Send the command
        send_command(password, command, args)

except KeyboardInterrupt:
    print("\nKeyboard interrupt received. Exiting.")
