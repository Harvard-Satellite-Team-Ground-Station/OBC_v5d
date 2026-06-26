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
import uplink


# +++++++++++++ INITIALIZATIONS +++++++++++++ #
commands = [
    "reset",
    "exec",
    "change_radio_modulation",
    "send_joke",
    "get_counter",
    "orient_payload",
    "orient_payload_setting",
    "orient_payload_periodic_time",
    "orient_light_threshold",
    "orient_heat_duration",
    "fsm_batt_threshold_orient",
    "fsm_batt_threshold_deploy",
    "deploy_burn_duration",
    "detumble_adjust_frequency",
    "detumble_stabilize_threshold",
    "detumble_max_time",
    "critical_battery_voltage",
    "degraded_battery_voltage",
    "sleep_if_yet_booted_count",
    "sleep_if_yet_deployed_count",
    "cdh_listen_command_timeout",
    "watchdog_reset_sleep",
    "except_reset_allowed_attemps"
]

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
    # Build the message, send it, and wait for the satellite's reply.
    msg_bytes = uplink.build_msg(config, password, command, args)
    resp = uplink.send_and_receive(uhf_packet_manager, msg_bytes)
    if resp is None:
        print("  [satellite]: no response (not received, or out of range)")
    else:
        print("  [satellite]:", uplink._show(resp))
    return resp

def process_input(user_input: str) -> tuple[bool, str]:
    # grab relevant parts of command, validate, then send to send_command

    # Step 0: get user input
    parts = user_input.strip().split()

    if not parts:
        return False, "[ERROR] Empty input."

    # Ground-side orchestration commands (not single satellite commands).
    # patch:  reliable, resumable file upload via the patch_* commands.
    # blast:  one-time bootstrap that writes a file using exec, for installing
    #         the patch commands before they exist on the satellite.
    action = parts[0].lower()
    if action in ("patch", "blast"):
        if len(parts) != 4:
            return False, f"[ERROR] usage: {action} <password> <localfile> <remotepath>"
        confirm = input(
            f"Type 'yes' to {action} {parts[2]} -> {parts[3]}: "
        ).strip().lower()
        if confirm != "yes":
            return False, "[CANCELLED] Not sent."
        if action == "patch":
            ok = uplink.upload_patch(
                uhf_packet_manager, config, logger, parts[1], parts[2], parts[3]
            )
        else:
            ok = uplink.blast_file(
                uhf_packet_manager, config, logger, parts[1], parts[2], parts[3]
            )
        return ok, f"[{'SUCCESS' if ok else 'FAILED'}] {action} {parts[2]}"

    # Step 1: verify at least 3 entries before strip.
    if len(parts) <= 2:
        return False, "[ERROR] Length too short. Must include at least 3 parts. Format: <password> <command> [args...]"
    password = parts[0]
    command = parts[1]
    args = parts[2:]

    # Step 2: see if user accidentally typed command first
    if password in commands:
        return False, "[ERROR] Missing password. You entered a command first."

    # Step 3: validate command
    if command not in commands:
        return False, f"[ERROR] Invalid command '{command}'. Valid commands: {commands}"

    # Step 4: show what will be sent and make user confirm
    preview = {
        "name": "cubesatname",
        "command": command,
        "args": args,
        "password": password
    }
    print("\n[PREVIEW] About to send command:")
    print(json.dumps(preview, indent=2))
    confirm = input("Type 'yes' to confirm: ").strip().lower()
    if confirm != "yes":
        return False, "[CANCELLED] Command not sent."

    # Step 5: send, and report based on whether the satellite actually replied
    resp = send_command(password, command, args)
    if resp is None:
        return False, f"[NO REPLY] '{command}' sent, no response from satellite"
    return True, f"[OK] '{command}' acknowledged"


# +++++++++++++ INTERACTIVE LOOP +++++++++++++ #
if __name__ == "__main__":
    try:
        while True:
            user_input = input("\nEnter command (or 'exit' to quit): ").strip()
            # if user exits, quit main.py file
            if user_input.lower() in ("exit", "quit"):
                print("Exiting.")
                break
            # process input
            success, message = process_input(user_input)
            if success:
                print("[input]: success")
                print(f"  → {message}")
            else:
                print("[input]: FAIL")
                print(f"  → {message}")

    except KeyboardInterrupt:
        print("\nKeyboard interrupt received. Exiting.")
