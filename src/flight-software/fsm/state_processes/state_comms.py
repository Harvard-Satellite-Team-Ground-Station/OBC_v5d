# state_comms.py



# ++++++++++++++ Imports/Installs ++++++++++++++ #
import asyncio
from fsm.ExtendedBeacon import ExtendedBeacon
from lib.pysquared.hardware.radio.packetizer.packet_manager import PacketManager


# ++++++++++++++ Functions: Helper ++++++++++++++ #
class StateComms:
    def __init__(self, dp_obj, logger, beacon_fsm, uhf_packet_manager):
        self.dp_obj = dp_obj
        self.logger = logger
        self.running = False
        self.done = True
        self.beacon_fsm:ExtendedBeacon = beacon_fsm
        self.uhf_packet_manager:PacketManager = uhf_packet_manager
    
    async def run(self):
        self._running = True
        # TODO: uncomment
        # self.uhf_packet_manager.send("Beginning comms.".encode("utf-8"))  
        while self._running:
            await asyncio.sleep(5)  
            # TODO: uncomment
            # self.beacon.send() # send additional data besides just the radio string
            self.done = True

    def stop(self):
        """
        Used by FSM to manually stop run()
        """
        self.running = False

    def is_done(self):
        """
        Checked by FSM to see if the run() completed on its own
        If it did complete, it shuts down the async task run()
        """
        return self.done