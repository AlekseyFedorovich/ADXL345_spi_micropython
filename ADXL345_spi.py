from micropython import const
import time
import ustruct
import gc
from machine import SPI, Pin

# commented out micropython.native decorator as it is not supported in some ports
class ADXL345:
  def __init__(self, spi_bus=1, cs_pin=5, scl_pin=18, sda_pin=23, sdo_pin=19, spi_freq=5000000, debug=False):
    """
    Class for fast SPI comunications between a MCU flashed with MicroPython and an Analog Devices ADXL345 accelerometer
    :param spi_bus: SPI bus number at which accelerometer is connected
    :param cs_pin: MCU pin number at which accelerometer's CS wire is connected
    :param scl_pin: MCU pin number at which accelerometer's SCL wire is connected (SCK)
    :param sda_pin: MCU pin number at which accelerometer's SDA wire is connected (MOSI)
    :param sdo_pin: MCU pin number at which accelerometer's SDO wire is connected (MISO)
    :param spi_freq: frequency of SPI comunications
    """

    # Sanity check
    if spi_freq > 5000000:
      spi_freq = 5000000
      print('max spi clock frequency for adxl345 is 5Mhz')
    
    # Constants
    
    self.standard_g         = const(9.80665)  # m/s2
    self.read_mask          = const(0x80)
    self.multibyte_mask     = const(0x40)
    self.nmaxvalues_infifo  = const(32)
    self.bytes_per_3axes    = const(6)  # 2 bytes * 3 axes
    self.device_id          = const(0xE5)

    # register addresses
    self.addr_device        = const(0x53)
    self.regaddr_devid      = const(0x00)
    self.regaddr_acc        = const(0x32)
    self.regaddr_freq       = const(0x2C)
    self.regaddr_pwr        = const(0x2D)
    self.regaddr_int_enable = const(0x2E)
    self.regaddr_int_map    = const(0x2F)
    self.regaddr_intsource  = const(0x30)
    self.regaddr_grange     = const(0x31)
    self.regaddr_fifoctl    = const(0x38)
    self.regaddr_fifostatus = const(0x39)
    
    # allowed values
    self.power_modes = {'standby': 0x00, 'measure': 0x08}
    self.g_ranges = {2: 0x00, 4: 0x01, 8: 0x10, 16: 0x11}
    self.device_sampling_rates = {1.56: 0x04, 3.13: 0x05, 6.25: 0x06, 12.5: 0x07, 25: 0x08, 50: 0x09, 100: 0x0a, 200: 0x0b, 400: 0x0c, 800: 0x0d, 1600: 0x0e, 3200: 0x0f}
    
    # SPI pins
    self.spi_bus = spi_bus
    self.cs_pin = cs_pin
    self.scl_pin = scl_pin
    self.sdo_pin = sdo_pin
    self.sda_pin = sda_pin
    self.spi_freq = spi_freq
    
    # Debugging
    self.debug = debug
  
  # == General Purpose ==
  def init_spi(self):
    self.spi = SPI(self.spi_bus, sck=Pin(self.scl_pin, Pin.OUT), mosi=Pin(self.sda_pin, Pin.OUT), miso=Pin(self.sdo_pin), baudrate=self.spi_freq, polarity=1, phase=1, bits=8, firstbit=SPI.MSB)
    time.sleep(0.2)
    self.cs = Pin(self.cs_pin, Pin.OUT, value=1)
    time.sleep(0.2)
    self.check_spi()    
    return self

  def deinit_spi(self):
    self.spi.deinit()
    return self
  
  def __del__(self): # might not be called due to limitations of MicroPython. See https://docs.micropython.org/en/latest/genrst/core_language.html#special-method-del-not-implemented-for-user-defined-classes
    self.deinit_spi()

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

  #@micropython.native
  def read(self, regaddr: int, nbytes: int) -> bytearray or int: # type: ignore
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

  #@micropython.native
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

  #@micropython.native
  def remove_first_bytes_from_bytearray_of_many_transactions(self, buf:bytearray) -> bytearray:
    """
    remove first byte of SPI transaction (which is irrelevant) from a buffer read through spi.readinto
    :param buf: bytearray of size multiple of (self.bytes_per_3axes + 1)
    :return: bytearray of size multiple of self.bytes_per_3axes
    """
    bytes_per_3axes = self.bytes_per_3axes
    return bytearray([b for i, b in enumerate(buf) if i % (bytes_per_3axes + 1) != 0])

  # == Settings ==
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
  
  def enable_interrupts(self, data_ready:bool=False, single_tap:bool=False, double_tap:bool=False, activity:bool=False, inactivity:bool=False, free_fall:bool=False, watermark:bool=False, overrun:bool=False):
    """
    Enable interrupts on the accelerometer. All enabled interrupts are ORed together before outputing to corresponding INT pin set by set_int_map method.
    
    :param data_ready: interrupt when a new measure is available
    :param single_tap: interrupt when a single tap is detected
    :param double_tap: interrupt when a double tap is detected
    :param activity: interrupt when the activity detection is triggered
    :param inactivity: interrupt when the inactivity detection is triggered
    :param free_fall: interrupt when a free fall is detected
    :param watermark: interrupt when the watermark level is reached
    :param overrun: interrupt when the fifo overrun is detected
    """
    mode = (
      (data_ready << 7) |
      (single_tap << 6) |
      (double_tap << 5) |
      (activity << 4) |
      (inactivity << 3) |
      (free_fall << 2) |
      (watermark << 1) |
      overrun
    )
    self.write(self.regaddr_int_enable, mode)
    return self

  def set_int_map(self, data_ready:bool=False, single_tap:bool=False, double_tap:bool=False, activity:bool=False, inactivity:bool=False, free_fall:bool=False, watermark:bool=False, overrun:bool=False):
    """
    Set the bit to False to output interrupt on INT1 pin, True to output interrupt on INT2 pin.
    
    :param data_ready: True to output data_ready interrupt on INT1 pin, False to output on INT2 pin
    :param single_tap: True to output single_tap interrupt on INT1 pin, False to output on INT2 pin
    :param double_tap: True to output double_tap interrupt on INT1 pin, False to output on INT2 pin
    :param activity: True to output activity interrupt on INT1 pin, False to output on INT2 pin
    :param inactivity: True to output inactivity interrupt on INT1 pin, False to output on INT2 pin
    :param free_fall: True to output free_fall interrupt on INT1 pin, False to output on INT2 pin
    :param watermark: True to output watermark interrupt on INT1 pin, False to output on INT2 pin
    :param overrun: True to output overrun interrupt on INT1 pin, False to output on INT2 pin
    """
    mapping = (
      (data_ready << 7) |
      (single_tap << 6) |
      (double_tap << 5) |
      (activity << 4) |
      (inactivity << 3) |
      (free_fall << 2) |
      (watermark << 1) |
      overrun
    )
    self.write(self.regaddr_int_map, mapping)
    return self
    
  # == Readings ==
  def check_spi(self) -> bool:    
    read = self.read(self.regaddr_devid, 1)[0]
    if read == self.device_id:
      return True
    else:
      if self.debug:
        print(
          'SPI communication between MCU and ADXL345 is not working.\n'
          'Please check the following:\n'
          '\t* wrong wiring?\n'
          '\t* reinitialised SPI?\n'
          '\t* broken sensor (test I2C to be sure)'
        )
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

  #@micropython.native
  def get_interrupts(self) -> dict[bool]:
    """
    Get the status of each interrupt from SPI.
    
    :return: dict with the status of each interrupt.
    :return['data_ready']: True if a new measure is available
    :return['single_tap']: True if a single tap is detected
    :return['double_tap']: True if a double tap is detected
    :return['activity']: True if the activity detection is triggered
    :return['inactivity']: True if the inactivity detection is triggered
    :return['free_fall']: True if a free fall is detected
    :return['watermark']: True if the watermark level is reached
    :return['overrun']: True if the fifo overrun is detected
    """
    int_status = self.read(self.regaddr_intsource, 1)[0]
    return {
      'data_ready': int_status >> 7 & 1,
      'single_tap': int_status >> 6 & 1,
      'double_tap': int_status >> 5 & 1,
      'activity': int_status >> 4 & 1,
      'inactivity': int_status >> 3 & 1,
      'free_fall': int_status >> 2 & 1,
      'watermark': int_status >> 1 & 1,
      'overrun': int_status & 1
    }

  #@micropython.native
  def get_nvalues_in_fifo(self) -> int:
    """
    :return: number of measures (xyz counts 1) in the fifo since last reading
    """
    return self.read(self.regaddr_fifostatus, 1)[0] & 0x3f  # first six bits to int

  # == Continuos readings able to reach 3.2 kHz ==
  #@micropython.native
  def read_many_xyz(self, n: int=1) -> tuple:
    """
    :param n: number of xyz accelerations to read from the accelerometer
    return: (
        bytearray containing 2 bytes for each of the 3 axes multiplied by the fractions of the sampling rate contained in the acquisition time,
        array of times at which each sample was recorded in microseconds
    )
    """
    if self.debug:
      print(f"Measuring {n} samples at {self.sampling_rate} Hz, range {self.g_range}g")
    # local variables and functions are MUCH faster, so copy them inside the function
    regaddr_acc = self.regaddr_acc | self.read_mask | self.multibyte_mask
    regaddr_intsource = self.regaddr_intsource | self.read_mask
    spi_readinto = self.spi.readinto
    cs = self.cs
    ticks_us = time.ticks_us
    bytes_per_3axes = self.bytes_per_3axes
    read = self.spi.read
    # definitions
    n_exp_meas = n
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
      spi_readinto(m[start_index: stop_index], regaddr_acc)
      cs.value(1)
      T[n_act_meas] = ticks_us()
      n_act_meas += 1
    self.set_power_mode('standby')
    # tail data cleaning
    buf = self.remove_first_bytes_from_bytearray_of_many_transactions(buf)
    buf = buf[:n_exp_meas * bytes_per_3axes]  # remove exceeding values
    T = T[:n_exp_meas]  # remove exceeding values
    if self.debug:
      actual_acq_time = (T[-1] - T[0]) / 1000000
      print(f"measured for {actual_acq_time} seconds, expected {n_exp_meas/self.sampling_rate} seconds")
      print(f"average sampling rate = {n_act_meas / actual_acq_time} Hz" if actual_acq_time != 0 else "cannot compute avg sampling rate since acquisition time is 0; aboarting")
    gc.collect()
    return buf, T

  #@micropython.native
  def read_many_xyz_fromfifo(self, n: int = 1) -> tuple:
    """
    read many measures of accaleration on the 3 axes from the fifo register
    :param n: number of measures to read (xyz counts 1)
    return: (
        bytearray containing 2 bytes for each of the 3 axes multiplied by the fractions of the sampling rate contained in the acquisition time,
        array of times at which each sample was recorded in microseconds
    )
    """
    if self.debug:
      print(f"Measuring {n} samples at {self.sampling_rate} Hz, range {self.g_range}g")
    # local variables and functions are MUCH faster so copy them inside the function
    regaddr_acc = self.regaddr_acc | self.read_mask | self.multibyte_mask
    spi_readinto = self.spi.readinto
    cs = self.cs
    get_nvalues_in_fifo = self.get_nvalues_in_fifo
    bytes_per_3axes = self.bytes_per_3axes
    # definitions
    n_exp_meas = n
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
      for _ in range(nvalues_infifo):  # it is impossible to read a block of measures from fifo
        cs.value(0)
        spi_readinto(m[n_act_meas * (bytes_per_3axes + 1): n_act_meas * (bytes_per_3axes + 1) + (bytes_per_3axes + 1)], regaddr_acc)
        cs.value(1)
        n_act_meas += 1
    t_stop = time.ticks_us()
    self.set_power_mode('standby')
    # tail data cleaning
    buf = self.remove_first_bytes_from_bytearray_of_many_transactions(buf)
    buf = buf[:n_exp_meas * bytes_per_3axes]  # remove exceeding values
    actual_acq_time = (t_stop - t_start) / 1000000
    actual_sampling_rate = n_act_meas / actual_acq_time
    T = [(i+1) / actual_sampling_rate for i in range(n_exp_meas)]
    if self.debug:
      print(f"measured for {actual_acq_time} seconds, expected {n_exp_meas/self.sampling_rate} seconds")
      print(f"actual sampling rate = {actual_sampling_rate} Hz" if actual_acq_time != 0 else "cannot compute actual sampling rate since acquisition time is 0; aboarting")
    gc.collect()
    return buf, T

  #@micropython.native
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
    n_exp_meas = int(acquisition_time * self.sampling_rate)
    buf, T = self.read_many_xyz(n_exp_meas)
    return buf, T

  #@micropython.native
  def read_continuos_xyz_fromfifo(self, acquisition_time: int) -> tuple:
    """
    read for the provided amount of time all the values contained in the fifo register (if any)
    :param acquisition_time:
    :return: (
        bytearray containing 2 bytes for each of the 3 axes multiplied by the fractions of the sampling rate contained in the acquisition time,
        array of times at which each sample was recorded in microseconds
    )
    """
    n_exp_meas = int(acquisition_time * self.sampling_rate)
    buf, T = self.read_many_xyz_fromfifo(n_exp_meas)
    return buf, T

  # == conversions ==
  def xyzbytes2g(self, buf: bytearray) -> tuple:
    """
    convert a bytearray of measures on the three axes xyz in three lists where the acceleration is in units of
        gravity on the sealevel (g)
    :param buf: bytearray of 2 bytes * 3 axes * nvalues
    :return: 3 lists of ints corresponding to x, y, z values of acceleration in units of g
    """
    gc.collect()
    acc_x, acc_y, acc_z = zip(*[ustruct.unpack('<HHH', buf[i:i + self.bytes_per_3axes]) for i in range(0,len(buf),self.bytes_per_3axes)])
    # negative values rule
    acc_x = [x if x <= 32767 else x - 65536 for x in acc_x]
    acc_y = [y if y <= 32767 else y - 65536 for y in acc_y]
    acc_z = [z if z <= 32767 else z - 65536 for z in acc_z]
    gc.collect()
    return acc_x, acc_y, acc_z
