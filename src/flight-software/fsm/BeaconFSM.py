from __future__ import annotations
from collections import OrderedDict
from lib.pysquared.beacon import Beacon

class BeaconFSM(Beacon):
    """Beacon that also includes FSM state in the beacon data."""

    def __init__(self, fsm_obj=None, *args, **kwargs):
        """
        Args:
            fsm_obj: The FSM object whose state we want to include.
            *args, **kwargs: All args to pass to the base Beacon class.
        """
        super().__init__(*args, **kwargs)
        self.fsm_obj = fsm_obj

    def _build_state(self) -> OrderedDict[str, object]:
        """Build the state and add FSM info."""
        state = super()._build_state()
        if self.fsm_obj is not None:
            state["FSM"] = {
            "fsm_state": str(self.fsm_obj.curr_state_name),
            "fsm_payload_deployed_already": str(self.fsm_obj.payload_deployed_already),
            "fsm_antennas_deployed_already": str(self.fsm_obj.antennas_deployed_already)
            }
        else:
            state["FSM"] = {}
        return state