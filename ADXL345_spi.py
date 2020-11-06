from micropython import const
import time
from math import floor, ceil
import ustruct
import gc
from machine import SPI, Pin

# TODO: const also on non bytes?

class ADXL345:
  
  def __init__(self, cs_pin=5, scl_pin=18, sda_pin=23, sdo_pin=19, spi_freq=5000000):
    """
    Class for fast SPI comunications between an ESP32 flashed with MicroPython and an Analog Devices ADXL345
      accelerometer
    :param cs_pin: MCU pin number at which accelerometer's CS wire is connected
    :param scl_pin: MCU pin number at which accelerometer's SCL wire is connected (SCK)
    :param sda_pin: MCU pin number at which accelerometer's SDA wire is connected (MOSI)
    :param sdo_pin: MCU pin number at which accelerometer's SDO wire is connected (MISO)
    :param spi_freq: frequency of SPI comunications
    """

    # constants
    self.standard_g         = 9.80665  # m/s2
    self.read_mask          = const(0x80)
    self.multibyte_mask     = const(0x40)
    self.nmaxvalues_infifo  = 32
    self.bytes_per_3axes    = 6  # 2 bytes * 3 axes
    self.device_id          = 0xE5

    # register addresses
    self.addr_device        = const(0x53)
    self.regaddr_devid      = const(0x00)
    self.regaddr_acc        = const(0x32)
    self.regaddr_freq       = const(0x2C)
    self.regaddr_pwr        = const(0x2D)
    self.regaddr_intsource  = const(0x30)
    self.regaddr_grange     = const(0x31)
    self.regaddr_fifoctl    = const(0x38)
    self.regaddr_fifostatus = const(0x39)

    # SPI pins
    self.cs_pin = cs_pin
    self.scl_pin = scl_pin
    self.sdo_pin = sdo_pin
    self.sda_pin = sda_pin
    self.spi_freq = spi_freq

    # allowed values
    self.power_modes = {'standby': 0x00, 'measure': 0x08}
    self.g_ranges = {2: 0x00, 4: 0x01, 8: 0x10, 16: 0x11}
    self.device_sampling_rates = {
      1.56: 0x04, 3.13: 0x05, 6.25: 0x06, 12.5: 0x07, 25: 0x08, 50: 0x09, 100: 0x0a, 200: 0x0b, 400: 0x0c, 800: 0x0d,
      1600: 0x0e, 3200: 0x0f
    }

  def __del__(self):
    self.spi.deinit()

  # == general purpose ==
  def init_spi(self):
    self.spi = SPI(
      2, sck=Pin(self.scl_pin, Pin.OUT), mosi=Pin(self.sda_pin, Pin.OUT), miso=Pin(self.sdo_pin),
      baudrate=self.spi_freq, polarity=1, phase=1, bits=8, firstbit=SPI.MSB
    )
    time.sleep(0.2)
    self.cs = Pin(self.cs_pin, Pin.OUT, value=1)
    time.sleep(0.2)
    if not self.is_spi_communcation_working():
      print(
        'SPI communication is not working: '
        '\n\t* wrong wiring?'
        '\n\t* reinitialised SPI?'
        '\n\t* broken sensor (test I2C to be sure)'
      )
    return self

  def deinit_spi(self):
    self.spi.deinit()
    return self

  def write(self, regaddr:int, the_byte:int):
    """
    write byte into register address
    :param regaddr: register address to write
    :param bt: byte to write
    """
    self.cs.value(0)
    self.spi.write(bytearray((regaddr, the_byte)))
    self.cs.value(1)
    return self

  @micropython.native
  def read(self, regaddr: int, nbytes: int) -> bytearray or int:
    """
    read bytes from register
    :param regaddr: register address to read
    :param nbytes: number of bytes to read
    :return: byte or bytes read
    """
    wbyte = regaddr | self.read_mask
    if nbytes > 1:
      wbyte = wbyte | self.multibyte_mask
    self.cs.value(0)
    value = self.spi.read(nbytes + 1, wbyte)[1:]
    self.cs.value(1)
    return value

  @micropython.native
  def read_into(self, buf: bytearray, regaddr: int) -> bytearray:
    """
    read bytes from register into an existing bytearray, generally faster than normal read
    :param rbuf: bytearray where read values will be assigned to
    :param regaddr: register address to read
    :return: modified input bytearray
    """
    wbyte = regaddr | self.read_mask | self.multibyte_mask
    self.cs.value(0)
    self.spi.readinto(buf, wbyte)
    self.cs.value(1)
    return buf

  @micropython.native
  def remove_first_bytes_from_bytearray_of_many_transactions(self, buf:bytearray) -> bytearray:
    """
    remove first byte of SPI transaction (which is irrelevant) from a buffer read through spi.readinto
    :param buf: bytearray of size multiple of (self.bytes_per_3axes + 1)
    :return: bytearray of size multiple of self.bytes_per_3axes
    """
    bytes_per_3axes = self.bytes_per_3axes
    return bytearray([b for i, b in enumerate(buf) if i % (bytes_per_3axes + 1) != 0])

  # == settings ==
  def set_power_mode(self, mode:str):
    """
    set the power mode of the accelerometer
    :param mode: {'measure', 'standby'}
    """
    print('set power mode to %s' % (mode))
    self.write(self.regaddr_pwr, self.power_modes[mode])
    self.power_mode = mode
    return self

  def set_g_range(self, grange:int):
    """
    set the scale of output acceleration data
    :param grange: {2, 4, 8, 16}
    """
    print('set range to pm %s' % (grange))
    self.write(self.regaddr_grange, self.g_ranges[grange])
    self.g_range = grange
    return self

  def set_sampling_rate(self, sr:int):
    """
    :param sr: sampling rate of the accelerometer can be {1.56, 3.13, 6.25, 12.5, 25, 50, 100, 200, 400, 800, 1600, 3200}
    """
    print('set sampling rate to %s' % (sr))
    self.write(self.regaddr_freq, self.device_sampling_rates[sr])
    self.sampling_rate = sr
    return self

  def set_fifo_mode(self, mode:str, watermark_level:int=16):
    """
    :param mode: in 'stream' mode the fifo is on, in 'bypass' mode the fifo is off
    :param watermark_level: see set_watermark_level method
    """
    self.fifo_mode = mode
    self.watermark_level = watermark_level
    if mode == 'bypass':
      b = 0x00
      print("set fifo in bypass mode")
    else:  # stream mode
      stream_bstr = '100'
      wm_bstr = bin(watermark_level).split('b')[1]
      bstr = '0b' + stream_bstr + '{:>5}'.format(wm_bstr).replace(' ', '0')
      b = int(bstr, 2)
      print("set fifo in stream mode")
    self.write(self.regaddr_fifoctl, b)
    return self

  def set_watermark_level(self, nrows:int=16):
    """
    set the number of new measures (xyz counts 1) after which the watermark is triggered
    """
    print('set watermark to %s rows' % (nrows))
    self.fifo_mode = 'stream'
    self.watermark_level = nrows
    stream_bstr = '100'
    wm_bstr = bin(nrows).split('b')[1]
    bstr = '0b' + stream_bstr + '{:>5}'.format(wm_bstr).replace(' ', '0')
    b = int(bstr, 2)
    self.write(self.regaddr_fifoctl, b)
    return self

  # == readings ==
  def is_spi_communcation_working(self) -> bool:
    if self.read(self.regaddr_devid, 1)[0] == self.device_id:
      return True
    else:
      print(self.read(self.regaddr_devid, 1))
      return False

  def clear_fifo(self):
    """
    Clears all values in fifo: usefull to start reading FIFO when expected, otherwise the first values were
    recorded before actually starting the measure
    """
    self.set_fifo_mode('bypass')
    self.set_fifo_mode('stream')

  def clear_isdataready(self):
    _ = self.read(self.regaddr_acc, 6)

  @micropython.native
  def is_watermark_reached(self) -> bool:
    """
    :return: 1 if watermark level of measures was reached since last reading, 0 otherwise
    """
    return self.read(self.regaddr_intsource, 1)[0] >> 1 & 1  # second bit

  @micropython.native
  def is_data_ready(self) -> bool:
    """
    :return: 1 if a new measure has arrived since last reading, 0 otherwise
    """
    return self.read(self.regaddr_intsource, 1)[0] >> 7 & 1  # eighth bit

  @micropython.native
  def get_nvalues_in_fifo(self) -> int:
    """
    :return: number of measures (xyz counts 1) in the fifo since last reading
    """
    return self.read(self.regaddr_fifostatus, 1)[0] & 0x3f  # first six bits to int

  @micropython.native
  def read_many_xyz(self, n:int) -> tuple:
    """
    :param n: number of xyz accelerations to read from the accelerometer
    :return: bytearray containing (n * bytes_per_3axes)
    """
    # local variables and functions are MUCH faster
    regaddr_acc = self.regaddr_acc | self.read_mask | self.multibyte_mask
    spi_readinto = self.spi.readinto
    cs = self.cs
    ticks_us = time.ticks_us
    read = self.spi.read
    regaddr_intsource = self.regaddr_intsource | self.read_mask
    bytes_per_3axes = self.bytes_per_3axes
    # definitions
    n_exp_bytes = (self.bytes_per_3axes + 1) * n
    T = [0] * (int(n * 1.5))
    buf = bytearray(n_exp_bytes)
    m = memoryview(buf)
    # measure
    n_act_meas = 0
    self.clear_isdataready()
    t_start = time.ticks_us()
    while n_act_meas < n:
      cs.value(0)
      is_data_ready = read(2, regaddr_intsource)[1] >> 7 & 1
      cs.value(1)
      if not is_data_ready:
        continue
      cs.value(0)
      spi_readinto(m[n_act_meas * (bytes_per_3axes + 1):n_act_meas * (bytes_per_3axes + 1) + (bytes_per_3axes + 1)], regaddr_acc)
      cs.value(1)
      T[n_act_meas] = ticks_us()
      n_act_meas += 1
    t_stop = time.ticks_us()
    # final corrections
    buf = self.remove_first_bytes_from_bytearray_of_many_transactions(buf)
    T = T[:n]
    # debug
    actual_acq_time = (t_stop - t_start) / 1000000
    print('measured for %s seconds, expected %s seconds' % (actual_acq_time, n / self.sampling_rate))
    print('actual sampling rate = ' + str(n_act_meas / actual_acq_time) + ' Hz')
    return buf, T

  @micropython.native
  def read_many_xyz_fromfifo(self, n: int) -> bytearray:
    """
    read many measures of accaleration on the 3 axes from the fifo register
    :param n: number of measures to read (xyz counts 1)
    :return: bytearray containing 2 bytes for each of the 3 axes, for nrows (6 * nrows bytes)
    """
    # local variables and functions are MUCH faster
    regaddr_acc = self.regaddr_acc | self.read_mask | self.multibyte_mask
    spi_readinto = self.spi.readinto
    cs = self.cs
    # definitions
    buf = bytearray((self.bytes_per_3axes+1) * n)
    m = memoryview(buf)
    # measure
    n_act_meas = 0
    t_start = time.ticks_us()
    while n_act_meas < n:  # it is impossible to read all fifo values in a single transmission
      cs.value(0)
      spi_readinto(m[n_act_meas*(self.bytes_per_3axes+1): n_act_meas*(self.bytes_per_3axes+1) + (self.bytes_per_3axes+1)], regaddr_acc)
      cs.value(1)
      n_act_meas += 1
    t_stop = time.ticks_us()
    # final corrections
    buf = self.remove_first_bytes_from_bytearray_of_many_transactions(buf)
    # debug
    actual_acq_time = (t_stop - t_start) / 1000000
    print('measured for %s seconds, expected %s seconds' % (actual_acq_time, n/self.sampling_rate))
    print('actual sampling rate = ' + str(n_act_meas / actual_acq_time) + ' Hz')
    return buf

  # == continuos readings able to reach 3.2 kHz ==
  @micropython.native
  def read_continuos_xyz(self, acquisition_time:int) -> tuple:
    """
    read for the provided amount of time from the acceleration register, saving the value only if a new measure is
    available since last reading
    :param acquisition_time: seconds the acquisition should last
    :return: (
        bytearray containing 2 bytes for each of the 3 axes multiplied by the fractions of the sampling rate contained in the acquisition time,
        array of times at which each sample was recorded in microseconds
    )
    """
    print("Measuring for %s seconds at %s Hz, range %sg" % (acquisition_time, self.sampling_rate, self.g_range))
    # local variables and functions are MUCH faster
    regaddr_acc = self.regaddr_acc | self.read_mask | self.multibyte_mask
    regaddr_intsource = self.regaddr_intsource | self.read_mask
    spi_readinto = self.spi.readinto
    cs = self.cs
    ticks_us = time.ticks_us
    bytes_per_3axes = self.bytes_per_3axes
    read = self.spi.read
    # definitions
    n_exp_meas = int(acquisition_time * self.sampling_rate)
    n_exp_bytes = (self.bytes_per_3axes + 1) * n_exp_meas
    T = [0] * (int(n_exp_meas * 1.5))
    buf = bytearray(int(n_exp_bytes * 1.5))
    m = memoryview(buf)
    # set up device
    self.set_fifo_mode('bypass')
    gc.collect()
    # measure
    n_act_meas = 0
    self.set_power_mode('measure')
    while n_act_meas < n_exp_meas:
      start_index = n_act_meas * (bytes_per_3axes + 1)
      stop_index = n_act_meas * (bytes_per_3axes + 1) + (bytes_per_3axes + 1)
      cs.value(0)
      is_data_ready = read(2, regaddr_intsource)[1] >> 7 & 1
      cs.value(1)
      if not is_data_ready:
        continue
      cs.value(0)
      spi_readinto(m[start_index : stop_index], regaddr_acc)
      cs.value(1)
      T[n_act_meas] = ticks_us()
      n_act_meas += 1
    self.set_power_mode('standby')
    # final corrections
    buf = self.remove_first_bytes_from_bytearray_of_many_transactions(buf)
    buf = buf[:n_exp_meas*bytes_per_3axes]  # remove exceeding values
    T = T[:n_act_meas]  # remove exceeding values
    # debug
    actual_acq_time = (T[-1] - T[0]) / 1000000
    print('measured for %s seconds, expected %s seconds' % (actual_acq_time, acquisition_time))
    print('avg sampling rate = ' + str(n_act_meas / actual_acq_time) + ' Hz')
    # TODO: send error to webapp when actual acquisition time is different from expected
    gc.collect()
    return buf, T

  @micropython.native
  def read_continuos_xyz_fromfifo(self, acquisition_time: int) -> tuple:
    """
    read for the provided amount of time all the values contained in the fifo register (if any)
    :param acquisition_time:
    :return: (
        bytearray containing 2 bytes for each of the 3 axes multiplied by the fractions of the sampling rate contained in the acquisition time,
        array of times at which each sample was recorded in microseconds
    )
    """
    print("Measuring for %s seconds at %s Hz, range %sg" % (acquisition_time, self.sampling_rate, self.g_range))
    # local variables and functions are MUCH faster
    regaddr_acc = self.regaddr_acc | self.read_mask | self.multibyte_mask
    spi_readinto = self.spi.readinto
    cs = self.cs
    get_nvalues_in_fifo = self.get_nvalues_in_fifo
    bytes_per_3axes = self.bytes_per_3axes
    # definitions
    n_exp_meas = int(acquisition_time * self.sampling_rate)
    n_exp_bytes = (bytes_per_3axes + 1) * n_exp_meas
    buf = bytearray(int(n_exp_bytes * 1.5))
    m = memoryview(buf)
    # set up device
    self.set_fifo_mode('stream')
    gc.collect()
    # measure
    n_act_meas = 0
    self.set_power_mode('measure')
    self.clear_fifo()
    t_start = time.ticks_us()
    while n_act_meas < n_exp_meas:
      nvalues_infifo = get_nvalues_in_fifo()
      for _ in range(nvalues_infifo):
        cs.value(0)
        spi_readinto(m[n_act_meas*(bytes_per_3axes+1) : n_act_meas*(bytes_per_3axes+1) + (bytes_per_3axes+1)], regaddr_acc)
        cs.value(1)
        n_act_meas += 1
    t_stop = time.ticks_us()
    self.set_power_mode('standby')
    # final corrections
    buf = self.remove_first_bytes_from_bytearray_of_many_transactions(buf)
    buf = buf[:n_exp_meas*bytes_per_3axes]                                  # remove exceeding values
    T = [i / self.sampling_rate for i in range(n_exp_meas)]                 # remove exceeding values
    # debug
    actual_acq_time = (t_stop - t_start) / 1000000
    print('measured for %s seconds, expected %s seconds' % (actual_acq_time, acquisition_time))
    print('actual sampling rate = ' + str(n_act_meas/actual_acq_time) + ' Hz')
    # TODO: send error to webapp when actual acquisition time is different from expected
    gc.collect()
    return buf, T

  # == conversions ==
  def xyzbytes2g(self, buf:bytearray) -> tuple:
    """
    convert a bytearray of measures on the three axes xyz in three lists where the acceleration is in units of
        gravity on the sealevel (g)
    :param buf: bytearray of 2 bytes * 3 axes * nvalues
    :return: 3 lists of ints corresponding to x, y, z values of acceleration in units of g
    """
    gc.collect()
    n_act_meas = int(len(buf)/self.bytes_per_3axes)
    acc_x, acc_y, acc_z = zip(*[ustruct.unpack('<HHH', buf[i:i + self.bytes_per_3axes]) for i in range(n_act_meas) if i % self.bytes_per_3axes == 0])
    # negative values rule
    acc_x = [x if x <= 32767 else x - 65536 for x in acc_x]
    acc_y = [y if y <= 32767 else y - 65536 for y in acc_y]
    acc_z = [z if z <= 32767 else z - 65536 for z in acc_z]
    gc.collect()
    return acc_x, acc_y, acc_z
