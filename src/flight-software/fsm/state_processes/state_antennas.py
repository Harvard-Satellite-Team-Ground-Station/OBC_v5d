# state_antennas.py



# ++++++++++++++ Imports/Installs ++++++++++++++ #
import asyncio


# ++++++++++++++ Functions: Helper ++++++++++++++ #
class StateAntennas:
    def __init__(self, dp_obj, logger, antenna_deployment):
        """
        Initialize the class object
        """
        self.dp_obj = dp_obj
        self.logger = logger
        self.antenna_deployment = antenna_deployment
        self.burn_duration = 5
        self.finished_burn = False
        self.running = False
        self.done = False
    
    async def run(self):
        """
        Run the deployment sequence asynchronously
        """
        self.running = True
        while self.running:
            await asyncio.sleep(1)
            # Burn the wire if not already done to release the antennas
            if not self.finished_burn:
                self.antenna_deployment.burn(5)
                await asyncio.sleep(4)
                self.finished_burn = True
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