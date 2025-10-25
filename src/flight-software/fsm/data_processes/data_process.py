# data_process.py



# ++++++++++++++++++ Imports and Installs ++++++++++++++++++ #
import time
import asyncio
import random
from lib.pysquared.protos.imu import IMUProto
from lib.pysquared.protos.magnetometer import MagnetometerProto
from lib.pysquared.protos.power_monitor import PowerMonitorProto


# ++++++++++++++++++++ Class Definition ++++++++++++++++++++ #
class DataProcess():
    """
    Class with functions to grab all the data that we need
    """

    def __init__(self):
        self.protos_power_monitor = PowerMonitorProto()
        self.protos_magnetometer = MagnetometerProto()
        self.protos_imu = IMUProto()
        self.last_imu_time = time.monotonic()
        self.running = True
        self.data = {
            "data_bp" : 0.0,                            # battery percentage
            "data_imu_av" : [0.0,0.0,0.0],              # imu angular velocity [ax, ay, az] in rad/s²
            "data_imu_av_magnitude" : 0.0,              # imu angular velocity magnitude (Euclidian norm aka length of data_imu_av vector)
            "data_imu_pos" : [0.0,0.0,0.0],             # imu position
            "data_magnetometer_vector" : [0.0,0.0,0.0]  # magnetometer vector
        }

    def start_run_all_data(self):
        """
        This schedules a coroutine (a program that can be paused/resumed infinitely,
        allowing for scheduled concurrency).  Specifically, it schedules the 
        run_all_data function
        """
        try:
            asyncio.create_task(self.run_all_data())
        except RuntimeError as e:
            print("Asyncio loop already running:", e)

    async def run_all_data(self):
        """
        Run all the data-gathering functions in an infinite loop.
        """
        await asyncio.gather(
            self.get_data_bp(),
            self.get_data_imu_av(),
            self.get_data_magnetometer_vector(),
            self.get_data_position(),
        )   

    async def get_data_bp(self):
        """
        Get data_bp
        TODO: Replace with actual battery percentage
        """
        while self.running:
            # determine voltage 
            voltage = 100
            # voltage = self.protos_power_monitor.get_bus_voltage()
            # convert to battery percentage based on online conversion equations
            if voltage is not None:
                battery_percentage = random.randint(10,100)
                # battery_percentage = 100 * (voltage - 35000)/6000 
                self.data["data_bp"] = battery_percentage
            await asyncio.sleep(1)

    async def get_data_imu_av(self):
        """
        Get data_imu_av and data_imu_av_magnitude
        TODO: Replace with actual gyro data
        """
        while self.running:
            # determine change in time
            now = time.monotonic()
            dt = now - self.last_imu_time
            self.last_imu_time = now
            # determine angular velocity data
            # accel = self.protos_imu.get_gyro_data()  
            accel = [random.randint(0,10),random.randint(0,10),random.randint(0,10)]
            if accel is None:
                await asyncio.sleep(1)
                return
            for i in range(3):
                self.data["data_imu_av"][i] += accel[i] * dt
            # compute the magnitude of angular velocity
            ωx, ωy, ωz = self.data["data_imu_av"]
            magnitude = (ωx**2 + ωy**2 + ωz**2) ** 0.5
            self.data["data_imu_av_magnitude"] = magnitude
            await asyncio.sleep(1)

    async def get_data_magnetometer_vector(self):
        """
        Get magnetometer vector
        TODO: Replace with actual gyro data
        """
        while self.running:
            # magnetometer_data = self.protos_magnetometer.get_vector()
            magnetometer_data = [random.randint(0,10),random.randint(0,10),random.randint(0,10)]
            self.data["data_magnetometer_vector"] = magnetometer_data
            await asyncio.sleep(1)

    async def get_data_position(self):
        """
        Get magnetometer vector
        TODO: Replace with actual position data
        """
        while self.running:
            pos = [random.randint(0,10),random.randint(0,10),random.randint(0,10)]
            self.data["data_imu_pos"] = pos
            await asyncio.sleep(1)