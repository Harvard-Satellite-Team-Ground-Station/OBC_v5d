"""This module defines the `VEML7700Manager` class, which provides a high-level interface
for interacting with the VEML7700 light sensor. It handles the initialization of the sensor
and provides methods for reading light levels in various formats.

**Usage:**
```python
logger = Logger()
i2c = busio.I2C(board.SCL, board.SDA)
i2c = initialize_i2c_bus(logger, board.SCL, board.SDA, 100000,)
light_sensor = VEML7700Manager(logger, i2c)
lux_data = light_sensor.get_lux()
```
"""

import time

from adafruit_tca9548a import TCA9548A_Channel
from veml6031 import VEML6031, AMBIENT_LIGHT_DATA_H_REG, AMBIENT_LIGHT_DATA_L_REG, MAX_LUX, IntegrationTime, Gain
from busio import I2C

from ....logger import Logger
from ....protos.light_sensor import LightSensorProto
from ....sensor_reading.error import (
    SensorReadingUnknownError,
    SensorReadingValueError,
)
from ....sensor_reading.light import Light
from ....sensor_reading.lux import Lux
from ...exception import HardwareInitializationError

try:
    from typing import Literal
except ImportError:
    pass


class VEML6031Manager(LightSensorProto):
    """Manages the VEML6031 ambient light sensor."""

    def __init__(
        self,
        logger: Logger,
        i2c: I2C | TCA9548A_Channel,
        integration_time: Literal[0, 1, 2, 3, 4, 5, 6, 7] = 7,
    ) -> None:
        """Initializes the VEML60310Manager.

        https://www.vishay.com/docs/80007/veml6031x00.pdf

        Args:
            logger: The logger to use.
            i2c: The I2C bus connected to the chip.
            integration_time: The integration time for the light sensor (default is 25ms).
                Integration times can be one of the following:
                - 0: 3.125ms
                - 1: 6.25ms
                - 2: 12.5ms
                - 3: 25ms
                - 4: 50ms
                - 5: 100ms
                - 6: 200ms
                - 7: 400ms

        Raises:
            HardwareInitializationError: If the light sensor fails to initialize.
        """
        self._log: Logger = logger
        self._i2c: I2C | TCA9548A_Channel = i2c

        try:
            self._log.debug("Initializing light sensor")
            self._light_sensor: VEML6031 = VEML6031(i2c)
            self._light_sensor.set_integration_time(integration_time)
        except Exception as e:
            raise HardwareInitializationError(
                "Failed to initialize light sensor"
            ) from e

    def get_light(self) -> Light:
        """Gets the light reading of the sensor with default gain and integration time.

        Returns:
            A Light object containing a non-unit-specific light level reading.

        Raises:
            SensorReadingUnknownError: If an unknown error occurs while reading the sensor.
        """
        try:
            count_l = self._light_sensor._read_register(AMBIENT_LIGHT_DATA_L_REG)
            count_h = self._light_sensor._read_register(AMBIENT_LIGHT_DATA_H_REG)
            count = (count_h << 8) | (count_l & 0xFF)
            return Light(count)
        except Exception as e:
            raise SensorReadingUnknownError("Failed to get light reading") from e

    def get_lux(self) -> Lux:
        """Gets the light reading of the sensor with default gain and integration time.

        Returns:
            A Lux object containing the light level in SI lux.

        Raises:
            SensorReadingValueError: If the reading returns an invalid value.
            SensorReadingUnknownError: If an unknown error occurs while reading the sensor.
        """
        try:
            lux = self._light_sensor.read_light(compensate=True) # raw value
        except Exception as e:
            raise SensorReadingUnknownError("Failed to get lux reading") from e

        if self._is_invalid_lux(lux):
            raise SensorReadingValueError("Lux reading is invalid or zero")

        return Lux(lux)

    def get_auto_lux(self) -> Lux:
        """Gets the auto lux reading of the sensor. This runs the sensor in auto mode
        and returns the lux value by searching through the available gain and integration time
        combinations to find the best match.

        Returns:
            A Lux object containing the light level in SI lux.

        Raises:
            SensorReadingValueError: If the reading returns an invalid value.
            SensorReadingUnknownError: If an unknown error occurs while reading the sensor.
        """
        try:
            best_lux = 0
            best_gain = None
            best_it = None

            gains = [Gain.x1_2, Gain.x2_3, Gain.x1, Gain.x2]
            integration_times = [
                IntegrationTime.ms3_125,
                IntegrationTime.ms6_25,
                IntegrationTime.ms12_5,
                IntegrationTime.ms25,
                IntegrationTime.ms50,
                IntegrationTime.ms100,
                IntegrationTime.ms200,
                IntegrationTime.ms400
            ]
            for it in integration_times:
                self._light_sensor.set_integration_time(it)
                for g in gains:
                    self._light_sensor.set_gain(g)
                    lux = self._light_sensor.read_light(compensate=False)  # raw reading
                    # Check if reading is within sensor limits
                    if 0 < lux < MAX_LUX:
                        if lux > best_lux:
                            best_lux = lux
                            best_gain = g
                            best_it = it

            if best_lux == 0:
                raise SensorReadingValueError("Auto lux could not find a valid reading.")
            
            # Set sensor to best combination
            lux = best_lux
            self._light_sensor.set_gain(best_gain)
            self._light_sensor.set_integration_time(best_it)

        except Exception as e:
            raise SensorReadingUnknownError("Failed to get auto lux reading") from e

        if self._is_invalid_lux(lux):
            raise SensorReadingValueError("Lux reading is invalid or zero")

        return Lux(lux)

    @staticmethod
    def _is_invalid_lux(lux: float | None) -> bool:
        """Determines if the given lux reading is invalid or zero.
        Args:
            lux (float | None): The lux reading to validate. It can be a float representing
                the light level in SI lux, or None if no reading is available.
        Returns:
            bool: True if the lux reading is invalid (None or zero), False otherwise.
        """
        return lux is None or lux == 0

    def reset(self) -> None:
        """Resets the light sensor."""
        try:
            self._light_sensor.shutdown()
            time.sleep(0.1)  # Allow time for the sensor to reset
            self._light_sensor.power_on()
            self._log.debug("Light sensor reset successfully")
        except Exception as e:
            self._log.error("Failed to reset light sensor:", e)
