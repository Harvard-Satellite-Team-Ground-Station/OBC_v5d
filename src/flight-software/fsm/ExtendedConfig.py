import json
from lib.pysquared.config.config import Config

class ExtendedConfig(Config):
    def __init__(self, config_path: str):
        """
        Config extended to allow for controlling orient of payload.
        CommandDataHandler:
            logger: Logger,
            config: Config or ExtendedConfig,
            packet_manager: PacketManager,
            send_delay: float = 0.2,
        """
        super().__init__(config_path)
        self._observers = []
        # Add new attributes if they don't exist in JSON
        if not hasattr(self, "orient_payload_setting"):
            self.orient_payload_setting = 1
        if not hasattr(self, "orient_payload_periodic_time"):
            self.orient_payload_periodic_time = 24

    def update_config(self, key: str, value, temporary: bool = False):
        for cb in self._observers:
                cb(key, value)
        if key in ["orient_payload_setting", "orient_payload_periodic_time"]:
            setattr(self, key, value)
            if not temporary:
                with open(self.config_file, "r") as f:
                    json_data = json.load(f)
                json_data[key] = value
                with open(self.config_file, "w") as f:
                    f.write(json.dumps(json_data))
        else:
            super().update_config(key, value, temporary)
