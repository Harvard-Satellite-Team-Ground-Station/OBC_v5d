"""
`hucsat_veml6031x00`
================================================================================

CircuitPython driver for VEML6031X00 high precision I2C ambient light sensor.


* Author(s): Christopher Prainito, Madison Davis

Implementation Notes
--------------------

**Hardware:**

* `Vishay VEML6031X00 Lux Sensor - I2C Light Sensor
  <https://www.vishay.com/en/product/80007/>`_

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://circuitpython.org/downloads

* Adafruit's Bus Device library:
  https://github.com/adafruit/Adafruit_CircuitPython_BusDevice

* Adafruit's Register library:
  https://github.com/adafruit/Adafruit_CircuitPython_Register
"""

from micropython import const
import adafruit_bus_device.i2c_device as i2cdevice
from adafruit_register.i2c_struct import ROUnaryStruct
from adafruit_register.i2c_bits import RWBits
from adafruit_register.i2c_bit import RWBit

try:
    import typing  # pylint: disable=unused-import
    from busio import I2C
except ImportError:
    pass

__version__ = "1.0.0"
__repo__ = "https://github.com/Harvard-Satellite-Team-Ground-Station/OBC_v5d"


class VEML6031X00:
    """Driver for the VEML6031X00 ambient light sensor.

    :param ~busio.I2C i2c_bus: The I2C bus the device is connected to
    :param int address: The I2C device address. Defaults to :const:`0x29`

    """

    # Ambient light sensor gain settings
    ALS_GAIN_1 = const(0x0)
    ALS_GAIN_2 = const(0x1)
    ALS_GAIN_2_3 = const(0x2)
    ALS_GAIN_1_2 = const(0x3)

    # Ambient light integration time settings
    ALS_3_125MS = const(0x0)
    ALS_6_25MS = const(0x1)
    ALS_12_5MS = const(0x2)
    ALS_25MS = const(0x3)
    ALS_50MS = const(0x4)
    ALS_100MS = const(0x5)
    ALS_200MS = const(0x6)
    ALS_400MS = const(0x7)

    # Gain value integers
    gain_values = {
        ALS_GAIN_2: 2,
        ALS_GAIN_1: 1,
        ALS_GAIN_2_3: 0.66,
        ALS_GAIN_1_2: 0.5,
    }

    # Integration time value integers
    integration_time_values = {
        ALS_3_125MS: 3.125,
        ALS_6_25MS: 6.25,
        ALS_12_5MS: 12.5,
        ALS_25MS: 25,
        ALS_50MS: 50,
        ALS_100MS: 100,
        ALS_200MS: 200,
        ALS_400MS: 400,
    }

    # ALS - Ambient light sensor high resolution output data
    light = ROUnaryStruct(0x04, "<H")
    """Ambient light data.

    This example prints the ambient light data. Cover the sensor to see the values change.

    .. code-block:: python

        import time
        import board
        import hucsat_veml6031x00

        i2c = board.I2C()  # uses board.SCL and board.SDA
        veml6031 = hucsat_veml6031x00.VEML6031X00(i2c)

        while True:
            print("Ambient light:", veml6031.light)
            time.sleep(0.1)
    """

    # WHITE - White channel output data
    white = ROUnaryStruct(0x05, "<H")
    """White light data.

    This example prints the white light data. Cover the sensor to see the values change.

    .. code-block:: python

        import time
        import board
        import hucsat_veml6031x00

        i2c = board.I2C()  # uses board.SCL and board.SDA
        veml6031 = hucsat_veml6031x00.VEML6031X00(i2c)

        while True:
            print("White light:", veml6031.white)
            time.sleep(0.1)
    """

    # ALS_CONF_0 - ALS gain, integration time, shutdown.
    light_shutdown = RWBit(0x00, 0, register_width=2)
    """Ambient light sensor shutdown. When ``True``, ambient light sensor is disabled."""
    light_gain = RWBits(2, 0x00, 11, register_width=2)
    """Ambient light gain setting. Gain settings are 2, 1, 2/3 and 1/2. Settings options are:
    ALS_GAIN_2, ALS_GAIN_1, ALS_GAIN_2_3, ALS_GAIN_1_2.

    This example sets the ambient light gain to 2 and prints the ambient light sensor data.

    .. code-block:: python

        import time
        import board
        import hucsat_veml6031x00

        i2c = board.I2C()  # uses board.SCL and board.SDA
        veml6031 = hucsat_veml6031x00.VEML6031X00(i2c)

        veml6031.light_gain = veml6031.ALS_GAIN_2

        while True:
            print("Ambient light:", veml6031.light)
            time.sleep(0.1)

    """
    light_integration_time = RWBits(4, 0x00, 6, register_width=2)
    """Ambient light integration time setting. Longer time has higher sensitivity. Can be:
    ALS_3_125MS, ALS_6_25MS, ALS_12_5MS, ALS_25MS, ALS_50MS, ALS_100MS, ALS_200MS, ALS_400MS.

    This example sets the ambient light integration time to 400ms and prints the ambient light
    sensor data.

    .. code-block:: python

        import time
        import board
        import hucsat_veml6031x00

        i2c = board.I2C()  # uses board.SCL and board.SDA
        veml6031 = hucsat_veml6031x00.VEML6031X00(i2c)

        veml6031.light_integration_time = veml6031.ALS_400MS

        while True:
            print("Ambient light:", veml6031.light)
            time.sleep(0.1)

    """

    def __init__(self, i2c_bus: I2C, address: int = 0x29) -> None:
        self.i2c_device = i2cdevice.I2CDevice(i2c_bus, address)
        for _ in range(3):
            try:
                # Set lowest gain to keep from overflow on init if bright light
                self.light_gain = self.ALS_GAIN_1_2
                #
                self.light_shutdown = False  # Enable the ambient light sensor
                break
            except OSError:
                pass
        else:
            raise RuntimeError("Unable to enable VEML6031X00 device")

    def integration_time_value(self) -> int:
        """Integration time value in integer form. Used for calculating :meth:`resolution`."""
        integration_time = self.light_integration_time
        return self.integration_time_values[integration_time]

    def gain_value(self) -> float:
        """Gain value in integer form. Used for calculating :meth:`resolution`."""
        gain = self.light_gain
        return self.gain_values[gain]

    def resolution(self) -> float:
        """Calculate the :meth:`resolution`` necessary to calculate lux. Based on
        integration time and gain settings."""
        resolution_at_max = 0.0034
        gain_max = 2
        integration_time_max = 400

        if (
            self.gain_value() == gain_max
            and self.integration_time_value() == integration_time_max
        ):
            return resolution_at_max
        return (
            resolution_at_max
            * (integration_time_max / self.integration_time_value())
            * (gain_max / self.gain_value())
        )

    @property
    def lux(self) -> float:
        """Light value in lux.

        This example prints the light data in lux. Cover the sensor to see the values change.

        .. code-block:: python

            import time
            import board
            import hucsat_veml6031x00

            i2c = board.I2C()  # uses board.SCL and board.SDA
            veml6031 = hucsat_veml6031x00.VEML6031X00(i2c)

            while True:
                print("Lux:", veml6031.lux)
                time.sleep(0.1)
        """
        return self.resolution() * self.light

    @property
    def autolux(self) -> float:
        """Lux value with auto-gain and auto-integration time.
        
        This method automatically adjusts the gain and integration time to find
        the optimal settings for the current lighting conditions, then returns
        the lux value.
        
        Returns:
            float: The calculated lux value with optimal settings.
        """
        # Store original settings
        original_gain = self.light_gain
        original_integration = self.light_integration_time
        
        # Test different gain and integration time combinations
        # Start with highest sensitivity (gain 2, 400ms)
        test_configs = [
            (self.ALS_GAIN_2, self.ALS_400MS),
            (self.ALS_GAIN_1, self.ALS_400MS),
            (self.ALS_GAIN_2_3, self.ALS_200MS),
            (self.ALS_GAIN_1_2, self.ALS_100MS),
        ]
        
        best_lux = None
        for gain, integration in test_configs:
            self.light_gain = gain
            self.light_integration_time = integration
            # Small delay for sensor to settle
            import time
            time.sleep(0.05)
            
            # Check if reading is within valid range
            reading = self.light
            if 100 < reading < 60000:  # Avoid saturation and too low readings
                best_lux = self.lux
                break
        
        # If no good reading found, use the last configuration
        if best_lux is None:
            best_lux = self.lux
        
        # Restore original settings
        self.light_gain = original_gain
        self.light_integration_time = original_integration
        
        return best_lux
