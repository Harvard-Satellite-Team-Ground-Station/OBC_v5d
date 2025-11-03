import time
import json
import traceback
from lib.pysquared.cdh import CommandDataHandler

class ExtendedCommandDataHandler(CommandDataHandler):
    """
    CDH that also includes a command to control orient payload.
    CommandDataHandler:
        logger: Logger,
        config: Config or ExtendedConfig,
        packet_manager: PacketManager,
        send_delay: float = 0.2,
    """
    
    command_orient_payload: str = "orient_payload"

    def listen_for_commands(self, timeout: int) -> None:
        """Listens for commands from the radio and handles them.

        Args:
            timeout: The time in seconds to listen for commands.
        """
        self._log.debug("Listening for commands...", timeout=timeout)

        json_bytes = self._packet_manager.listen(timeout)
        if json_bytes is None:
            return

        try:
            json_str = json_bytes.decode("utf-8")

            msg: dict[str, str] = json.loads(json_str)

            # Check for OSCAR password first
            if msg.get("password") == self.oscar_password:
                self._log.debug("OSCAR command received", msg=msg)
                cmd = msg.get("command")
                if cmd is None:
                    self._log.warning("No OSCAR command found in message", msg=msg)
                    self._packet_manager.send(
                        f"No OSCAR command found in message: {msg}".encode("utf-8")
                    )
                    return

                args: list[str] = []
                raw_args = msg.get("args")
                if isinstance(raw_args, list):
                    args: list[str] = raw_args

                # Delay to give the ground station time to switch to listening mode
                time.sleep(self._send_delay)
                self._packet_manager.send_acknowledgement()

                self.oscar_command(cmd, args)
                return

            # If message has password field, check it
            if msg.get("password") != self._config.super_secret_code:
                self._log.debug(
                    "Invalid password in message",
                    msg=msg,
                )
                return

            if msg.get("name") != self._config.cubesat_name:
                self._log.debug(
                    "Satellite name mismatch in message",
                    msg=msg,
                )
                return

            # If message has command field, execute the command
            cmd = msg.get("command")
            if cmd is None:
                self._log.warning("No command found in message", msg=msg)
                self._packet_manager.send(
                    f"No command found in message: {msg}".encode("utf-8")
                )
                return

            args: list[str] = []
            raw_args = msg.get("args")
            if isinstance(raw_args, list):
                args: list[str] = raw_args

            self._log.debug("Received command message", cmd=cmd, args=args)

            # Delay to give the ground station time to switch to listening mode
            time.sleep(self._send_delay)
            self._packet_manager.send_acknowledgement()

            if cmd == self.command_orient_payload:
                self.set_orient_payload(args)
            elif cmd == self.command_reset:
                self.reset()
            elif cmd == self.command_change_radio_modulation:
                self.change_radio_modulation(args)
            elif cmd == self.command_send_joke:
                self.send_joke()
            else:
                self._log.warning("Unknown command received", cmd=cmd)
                self._packet_manager.send(
                    f"Unknown command received: {cmd}".encode("utf-8")
                )

        except Exception as e:
            self._log.error("Failed to process command message", err=e)
            self._packet_manager.send(
                f"Failed to process command message: {traceback.format_exception(e)}".encode(
                    "utf-8"
                )
            )
            return

    def set_orient_payload(self, args: list[str]):
        try:
            if len(args) < 2:
                self._log.debug("Not enough arguments for orient_payload command. Require setting and periodic time (periodic time only will take affect if setting = 2).")
                return
            orient_payload_setting = args[0]
            orient_payload_periodic_time = args[1]
            if str(orient_payload_setting) in ["0", "1", "2"]:
                self._config.update_config("orient_payload_setting", int(orient_payload_setting), temporary=False)
            else:
                self._log.debug("Invalid orient payload setting.  Set as 0, 1, or 2")
            if 0 < float(orient_payload_periodic_time) <= 24:
                self._config.update_config("orient_payload_periodic_time", float(orient_payload_periodic_time), temporary=False)
            else:
                self._log.debug("Invalid orient payload periodic time.  Set as as float (hours) between 0, exclusive, and 24, inclusive.")
        except ValueError as e:
            self._log.error("Failed to change orient modulation", err=e)
        self._packet_manager.send(f"New feature executed with args: {args}".encode("utf-8"))
