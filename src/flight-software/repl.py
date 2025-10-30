import json
import os
import time

import board
import asyncio
import digitalio
from lib.adafruit_mcp230xx.mcp23017 import MCP23017
from lib.adafruit_tca9548a import TCA9548A
from lib.pysquared.beacon import Beacon
from lib.pysquared.cdh import CommandDataHandler
from lib.pysquared.config.config import Config
from lib.pysquared.config.jokes_config import JokesConfig
from lib.pysquared.file_validation.manager.file_validation import FileValidationManager
from lib.pysquared.hardware.burnwire.manager.burnwire import BurnwireManager
from lib.pysquared.hardware.busio import _spi_init, initialize_i2c_bus
from lib.pysquared.hardware.digitalio import initialize_pin
from lib.pysquared.hardware.imu.manager.lsm6dsox import LSM6DSOXManager
from lib.pysquared.hardware.light_sensor.manager.veml7700 import VEML7700Manager
from lib.pysquared.hardware.load_switch.manager.loadswitch_manager import (
    LoadSwitchManager,
)
from lib.pysquared.hardware.magnetometer.manager.lis2mdl import LIS2MDLManager
from lib.pysquared.hardware.power_monitor.manager.ina219 import INA219Manager
from lib.pysquared.hardware.radio.manager.rfm9x import RFM9xManager
from lib.pysquared.hardware.radio.manager.sx1280 import SX1280Manager
from lib.pysquared.hardware.radio.packetizer.packet_manager import PacketManager
from lib.pysquared.hardware.temperature_sensor.manager.mcp9808 import MCP9808Manager
from lib.pysquared.logger import Logger
from lib.pysquared.nvm.counter import Counter
from lib.pysquared.protos.power_monitor import PowerMonitorProto
from lib.pysquared.rtc.manager.microcontroller import MicrocontrollerManager
from lib.pysquared.watchdog import Watchdog
from version import __version__
from fsm.data_processes.data_process import DataProcess
from fsm.fsm import FSM


# ----- Initializations ----- #
rtc = MicrocontrollerManager()

logger: Logger = Logger(
    error_counter=Counter(0),
    colorized=False,
)

i2c0 = initialize_i2c_bus(
    logger,
    board.SCL0,
    board.SDA0,
    100000,
)

i2c1 = initialize_i2c_bus(
    logger,
    board.SCL1,
    board.SDA1,
    100000,
)

magnetometer = LIS2MDLManager(logger, i2c1)

imu = LSM6DSOXManager(logger, i2c1, 0x6B)

battery_power_monitor: PowerMonitorProto = INA219Manager(logger, i2c0, 0x40)


# ----- Test Functions ----- #
def test_dm_obj_initialization():
    dm_obj = DataProcess(magnetometer=magnetometer,
                        imu=imu,
                        battery_power_monitor=battery_power_monitor)
    try:
        res = dm_obj.data
        if res is not None:
            print("\033[92mPASSED\033[0m [dm_obj test]")
    except Exception as e:
            print("\033[91mFAILED:\033[0m [dm_obj test]", e) 

async def test_dm_obj_magnetorquer():
    dm_obj = DataProcess(magnetometer=magnetometer,
                         imu=imu,
                         battery_power_monitor=battery_power_monitor)
    dm_obj.running = True       
    dm_obj.start_run_all_data()
    print("Monitor magnetoruqer for 10 seconds.  Move/don't move around FC to see if the value changes.")
    await asyncio.sleep(1)
    for _ in range(100):
        print(dm_obj.data["data_magnetometer_vector"])
        await asyncio.sleep(0.1)
    return input("Is this acceptable? (Y/N): ").strip().upper()

async def test_dm_obj_imu():
    dm_obj = DataProcess(magnetometer=magnetometer,
                         imu=imu,
                         battery_power_monitor=battery_power_monitor)
    dm_obj.running = True
    dm_obj.start_run_all_data()
    # imu av
    print("Monitor imu av for 10 seconds.  Move/don't move around FC to see if the value changes.")
    await asyncio.sleep(1)
    for _ in range(100):
        print(dm_obj.data["data_imu_av"])
        await asyncio.sleep(0.1)
    input("Is the av acceptable? (Y/N): ").strip().upper()
    # imu acc
    print("Monitor imu acc for 10 seconds.  Move/don't move around FC to see if the value changes.")
    await asyncio.sleep(1)
    for _ in range(100):
        print(dm_obj.data["data_imu_acc"])
        await asyncio.sleep(0.1)
    return input("Is the acc acceptable? (Y/N): ").strip().upper()

async def test_dm_obj_battery():
    dm_obj = DataProcess(magnetometer=magnetometer,
                         imu=imu,
                         battery_power_monitor=battery_power_monitor)
    dm_obj.running = True
    dm_obj.start_run_all_data()
    input("Please plug in the batteries and press Enter when done.")
    print("Voltage with batteries:", dm_obj.data["data_batt_volt"])
    print("Percentage with batteries:", dm_obj.data["data_batt_perc"])
    input("Please unplug the batteries and press Enter when done.")
    print("Voltage without batteries:", dm_obj.data["data_batt_volt"])
    print("Percentage without batteries:", dm_obj.data["data_batt_perc"])
    return input("Did the voltage drop by >= 4V? (Y/N): ").strip().upper()

async def test_dm_obj_get_data_updates():
    dm_obj = DataProcess(magnetometer=magnetometer,
                         imu=imu,
                         battery_power_monitor=battery_power_monitor)
    try:
        # [:] allows for a shallow copy
        battery_voltage_before = dm_obj.data["data_batt_volt"]
        imu_av_before = dm_obj.data["data_imu_av"][:]
        imu_av_mag_before = dm_obj.data["data_imu_av_magnitude"]
        imu_acc_before = dm_obj.data["data_imu_acc"][:]
        mag_vector_before = dm_obj.data["data_magnetometer_vector"][:]
        # enable the loop once
        dm_obj.running = True       
        dm_obj.start_run_all_data()  
        await asyncio.sleep(1.1)
        # stop the infinite loop
        # let tasks exit cleanly
        dm_obj.running = False
        await asyncio.sleep(0.1) 
        # check if data was updated
        battery_voltage_after = dm_obj.data["data_batt_volt"]
        imu_av_after = dm_obj.data["data_imu_av"][:]
        imu_av_mag_after = dm_obj.data["data_imu_av_magnitude"]
        imu_acc_after = dm_obj.data["data_imu_acc"][:]
        mag_vector_after = dm_obj.data["data_magnetometer_vector"][:]
        if battery_voltage_before != battery_voltage_after:
            print("\033[92mPASSED\033[0m [test_dm_obj_get_data_updates data_batt_volt]")
        else:
            print("\033[91mFAILED\033[0m [test_dm_obj_get_data_updates data_batt_volt]")
        if imu_av_before != imu_av_after:
            print("\033[92mPASSED\033[0m [test_dm_obj_get_data_updates imu_av]")
        else:
            print("\033[91mFAILED\033[0m [test_dm_obj_get_data_updates imu_av]")
        if imu_av_mag_before != imu_av_mag_after:
            print("\033[92mPASSED\033[0m [test_dm_obj_get_data_updates imu_av_mag]")
        else:
            print("\033[91mFAILED\033[0m [test_dm_obj_get_data_updates imu_av_mag]")
        if imu_acc_before != imu_acc_after:
            print("\033[92mPASSED\033[0m [test_dm_obj_get_data_updates imu_acc]")
        else:
            print("\033[91mFAILED\033[0m [test_dm_obj_get_data_updates imu_acc]")
        if mag_vector_before != mag_vector_after:
            print("\033[92mPASSED\033[0m [test_dm_obj_get_data_updates mag_vector]")
        else:
            print("\033[91mFAILED\033[0m [test_dm_obj_get_data_updates mag_vector]")
    except Exception as e:
        print("\033[91mFAILED\033[0m [test_dm_obj_get_data_updates Exception]", e)

def test_fsm_transitions():
        dm_obj = DataProcess(magnetometer=magnetometer,
                         imu=imu,
                         battery_power_monitor=battery_power_monitor)
        fsm_obj = FSM(dm_obj, logger, radio=None)

        # Initially, FSM should be in bootup
        assert(fsm_obj.curr_state_name == "bootup")

        # Simulate bootup done
        fsm_obj.curr_state_object.done = True
        fsm_obj.execute_fsm_step()
        assert fsm_obj.curr_state_name == "detumble", "\033[91mFAILED\033[0m [test_fsm_transitions bootup -> detumble]"

        # Simulate detumble done
        fsm_obj.curr_state_object.done = True
        fsm_obj.execute_fsm_step()
        assert fsm_obj.curr_state_name == "antennas", "\033[91mFAILED\033[0m [test_fsm_transitions detumble -> antennas]"

        # Simulate antennas done
        fsm_obj.curr_state_object.done = True
        fsm_obj.execute_fsm_step()
        assert fsm_obj.curr_state_name == "comms", "\033[91mFAILED\033[0m [test_fsm_transitions antennas -> comms]"

        # Simulate comms done → deploy
        fsm_obj.curr_state_object.done = True
        fsm_obj.execute_fsm_step()
        assert fsm_obj.curr_state_name == "deploy", "\033[91mFAILED\033[0m [test_fsm_transitions comms -> deploy]"

        # Simulate deploy done → orient
        fsm_obj.curr_state_object.done = True
        fsm_obj.execute_fsm_step()
        assert fsm_obj.curr_state_name == "orient", "\033[91mFAILED\033[0m [test_fsm_transitions deploy -> orient]"

        # Simulate orient done → comms
        fsm_obj.curr_state_object.done = True
        fsm_obj.execute_fsm_step()
        assert fsm_obj.curr_state_name == "comms", "\033[91mFAILED\033[0m [test_fsm_transitions orient -> comms]"

        # Simulate comms done → orient
        fsm_obj.curr_state_object.done = True
        fsm_obj.execute_fsm_step()
        assert fsm_obj.curr_state_name == "orient", "\033[91mFAILED\033[0m [test_fsm_transitions comms -> orient]"
        
        print("\033[92mPASSED\033[0m [test_fsm_transitions]")

# ========== MAIN FUNCTION ========== #

def test_all():
    # comment out tests you don't want to run
    test_fsm_transitions()
    test_dm_obj_initialization()
    asyncio.run(test_dm_obj_get_data_updates())
    asyncio.run(test_dm_obj_magnetorquer())
    asyncio.run(test_dm_obj_imu())
    asyncio.run(test_dm_obj_battery())