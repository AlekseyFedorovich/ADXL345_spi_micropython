# uPy - ADXL345 - SPI
Library for controlling through the SPI protocol an 'Analog Devices ADXL345' accelerometer from an MCU flashed with MicroPython (in particular this was tested with a **ESP32-WROVER** (4MB RAM)).

Methods are optimised for being as fast as possible, trying to reach max available sampling rate (3.2kHz) for this device.

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

## RAM and MemoryErrors
Consider that at high sampling rates the MCU collects 3_axes x sampling_rate floats per second. This may result in ending the available RAM of MCUs very quickly: set your acquisition time accordingly and clear data arrays when you are done with them. 

## Examples
### read one x, y, z
``` python
from ADXL345_spi import ADXL345 as Accelerometer
accelerometer = Accelerometer(cs_pin=5, scl_pin=18, sda_pin=23, sdo_pin=19, spi_freq=5000000)
accelerometer.init_spi()
accelerometer.set_sampling_rate(1.56)   # Hz
accelerometer.set_g_range(2)            # max measurable acceleration pm 2g
accelerometer.set_fifo_mode('bypass')
accelerometer.set_power_mode('measure')
buf, T = accelerometer.read_many_xyz(n=1)
accelerometer.set_power_mode('standby')
x, y, z = accelerometer.xyzbytes2g(buf)  # convert bytearray in 3 acceleration arrays (x, y, z) in g units
accelerometer.deinit_spi()  # this is necessary, otherwise if another SPI is initialized it won't work
```

### read many x, y, z
``` python
from ADXL345_spi import ADXL345 as Accelerometer
accelerometer = Accelerometer()                     # assumes accelerometer is connected to MCU spi default Pins
accelerometer.init_spi()
accelerometer.set_sampling_rate(3200)
accelerometer.set_g_range(2)
accelerometer.set_fifo_mode('bypass')
accelerometer.set_power_mode('measure')
buf, T = accelerometer.read_many_xyz(n=10)  # reads ten samples for each axis at the requested sampling rate
accelerometer.set_power_mode('standby')
x, y, z = accelerometer.xyzbytes2g(buf)     # arrays of length 10, to be associated with the T array that holds the times of the measure of each sample
accelerometer.deinit_spi()
```

### read continuosly when data is ready
``` python
from ADXL345_spi import ADXL345 as Accelerometer
accelerometer = Accelerometer()
accelerometer.init_spi()
accelerometer.set_sampling_rate(3200)
accelerometer.set_g_range(2)
accelerometer.set_fifo_mode('bypass')
accelerometer.set_power_mode('measure')
buf, T = accelerometer.read_continuos_xyz(acquisition_time=1.5)  # reads samples for 1.5 seconds from each axis at the requested sampling rate
accelerometer.set_power_mode('standby')
x, y, z = accelerometer.xyzbytes2g(buf)  # arrays (in principle) of length acquisition_time * sampling_rate 
accelerometer.deinit_spi()
```

### read continuosly from fifo
The method for reading from fifo is implemented even though with this device I wasn't able to read more than one row of the fifo in one transaction (resulting in reading following registers instead of other rows of the fifo)
``` python
from ADXL345_spi import ADXL345 as Accelerometer
accelerometer = Accelerometer()
accelerometer.init_spi()
accelerometer.set_sampling_rate(3200)
accelerometer.set_g_range(2)
accelerometer.set_fifo_mode('stream')
accelerometer.set_power_mode('measure')
buf, T = accelerometer.read_continuos_xyz_fromfifo(acquisition_time=1.5)
accelerometer.set_power_mode('standby')
x, y, z = accelerometer.xyzbytes2g(buf)
accelerometer.deinit_spi()
```
