# uPy - ADXL345 - SPI
Library for interacting through the SPI protocol with an 'Analog Devices ADXL345' accelerometer from an ESP32 MCU, flashed with MicroPython.
Methods are optimised for continuos readings at max frequency.

## Wiring
The following wirings refers to the tested setup on an ESP32-WROVER:

ADXL345 Pin name  | ESP32 Pin name (number)
 ---------------- | -----------------------
Vs                | 3v3
GND               | GND
CS                | vspi cs (D5)
SCL/SCLK          | vspi scl (D18)
SDO/ALT ADDRESS   | vspi miso (D19)
SDA/SDI/SDO       | vspi mosi (D23)

## Examples
``` python
""" read one x, y, z """
from ADXL345_spi import ADXL345 as Accelerometer
accelerometer = Accelerometer(cs_pin=5, scl_pin=18, sda_pin=23, sdo_pin=19, spi_freq=5000000)
accelerometer.set_sampling_rate(1.56)   # Hz
accelerometer.set_g_range(2)            # pm 2g
accelerometer.set_fifo_mode('bypass')
accelerometer.set_power_mode('measure')
buf, T = accelerometer.read_many_xyz(n=1)
accelerometer.set_power_mode('standby')
x, y, z = accelerometer.xyzbytes2g(buf)  # g units
del accelerometer  # this is necessary, otherwise if another SPI is initialized it won't work
```

``` python
""" read many x, y, z """
from ADXL345_spi import ADXL345 as Accelerometer
accelerometer = Accelerometer()                     # assumes accelerometer is connected to ESP32 vspi default Pins
accelerometer.set_sampling_rate(3200)
accelerometer.set_g_range(2)
accelerometer.set_fifo_mode('bypass')
accelerometer.set_power_mode('measure')
buf, T = accelerometer.read_many_xyz(n=10)
accelerometer.set_power_mode('standby')
x, y, z = accelerometer.xyzbytes2g(buf)
del accelerometer
```

``` python
""" read continuosly when data is ready """
from ADXL345_spi import ADXL345 as Accelerometer
accelerometer = Accelerometer()
accelerometer.set_sampling_rate(3200)
accelerometer.set_g_range(2)
accelerometer.set_fifo_mode('bypass')
accelerometer.set_power_mode('measure')
buf, T = accelerometer.read_continuos_xyz(acquisition_time=1.5)
accelerometer.set_power_mode('standby')
x, y, z = accelerometer.xyzbytes2g(buf)
del accelerometer
```

``` python
""" read continuosly from fifo """
from ADXL345_spi import ADXL345 as Accelerometer
accelerometer = Accelerometer()
accelerometer.set_sampling_rate(3200)
accelerometer.set_g_range(2)
accelerometer.set_fifo_mode('stream')
accelerometer.set_power_mode('measure')
buf, T = accelerometer.read_continuos_xyz_fromfifo(acquisition_time=1.5)
accelerometer.set_power_mode('standby')
x, y, z = accelerometer.xyzbytes2g(buf)
del accelerometer
```
