# TEST FILE
# This file sets up some tests to verify that the input system properly checks commands


# +++++++++++++++++ IMPORTS +++++++++++++++++ #
import json


# +++++++++++++++++ VARIABLES +++++++++++++++++ #
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


# +++++++++++++ FUNCTIONS +++++++++++++ #
def send_command(password: str, command: str, args: list[str] = []):
    # build message, serialize, then send out bytes
    # in this test file, no actual sending
    msg = {
        "name": "cubesatname",
        "command": command,
        "args": args,
        "password": password
    }
    msg_bytes = json.dumps(msg).encode("utf-8")
    return msg_bytes

def process_input(user_input: str) -> tuple[bool, str]:
    # grab relevant parts of command, validate, then send to send_command

    # Step 0: get user input
    parts = user_input.strip().split()

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

    # Step 5: actually send
    msg_bytes = send_command(password, command, args)
    return True, f"[SUCCESS] Sent: {msg_bytes}"


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