import itertools
from threading import Thread, Lock
from typing import Tuple
from cobs import cobs
from collections import deque
import numpy as np
import scipy
import serial

SAMPLING_RATE = 4000
MAX_HISTORY = 5 * 60 * 4000

def project_xyz(x, y, z):
    return x + y + z

def project_x(x, y, z):
    return x

def project_y(x, y, z):
    return y

def project_z(x, y, z):
    return z

class AccelerometerData:
    def __init__(self) -> None:
       self.data = deque([], MAX_HISTORY)
       self.tmp_data = []

    def set_data(self, data) -> None:
        self.data = deque(data, MAX_HISTORY)
        self.tmp_data = []

    def as_np(self) -> None:
        return np.array(self.data)

    def push_sample(self, sample: Tuple[float, float, float]) -> None:
        self.tmp_data.append(sample)

    def _finish_push_sample(self):
        # Not entirely safe, but...
        x = self.tmp_data
        self.tmp_data = []
        self.data.extend(x)

    def clear(self):
        self.data = deque([], MAX_HISTORY)

    def get_length(self) -> float:
        """
        Return length in seconds
        """
        return len(self.data) / SAMPLING_RATE

    def pull_samples(self):
        self._finish_push_sample()

    def get_sample_count_for_window(self, duration):
        return round(duration * SAMPLING_RATE)

    def get_sample_window(self, from_t, to_t, sample_projection):

        expected_samples = self.get_sample_count_for_window(to_t - from_t)

        start_idx = int(from_t * SAMPLING_RATE)
        if start_idx < 0:
            start_idx = 0
        if start_idx > len(self.data):
            start_idx = len(self.data)

        end_idx = start_idx + expected_samples

        if end_idx > len(self.data):
            end_idx = len(self.data)

        if end_idx - start_idx != expected_samples:
            return np.full((expected_samples,), 0)

        return np.array([sample_projection(x, y, z) for x, y, z in itertools.islice(self.data, start_idx, end_idx)])


    def get_fft(self, from_t, to_t, from_freq, to_freq, sample_projection) -> Tuple[np.array, np.array]:
        source = self.get_sample_window(from_t, to_t, sample_projection)
        assert len(source) != 0

        source = scipy.signal.detrend(source)

        fft = (4 / len(source)) * np.absolute(scipy.fft.rfft(np.hanning(len(source)) * source))
        bins = scipy.fft.rfftfreq(len(source), 1 / SAMPLING_RATE)

        time_low_limit = np.searchsorted(bins, from_freq)
        time_high_limit = np.searchsorted(bins, to_freq)

        return (bins[time_low_limit:time_high_limit], fft[time_low_limit:time_high_limit])

class ThreadPortReadout(Thread):
    def __init__(self, port, report_sample):
        super().__init__()

        self.should_be_running = True
        self.port = port
        self.report_sample = report_sample

    def run(self):
        try:
            with serial.Serial(port=self.port, baudrate=921600) as connection:
                while self.should_be_running:
                    data = self.read_cobs_packet(connection)
                    if not data:
                        continue

                    try:
                        packet = cobs.decode(data)
                    except cobs.DecodeError as e:
                        continue
                    packet_type = packet[0]
                    if packet_type != 1 or len(packet) != 8:
                        continue
                    range_value = packet[1]
                    x = int.from_bytes(packet[2:4], byteorder='little', signed=True)
                    y = int.from_bytes(packet[4:6], byteorder='little', signed=True)
                    z = int.from_bytes(packet[6:8], byteorder='little', signed=True)

                    self.report_sample((
                        self.transform_to_g(x, range_value),
                        self.transform_to_g(y, range_value),
                        self.transform_to_g(z, range_value)))
        except Exception as e:
            print(e)

    def stop(self):
        self.should_be_running = False
        self.join()

    def read_cobs_packet(self, connection: serial.Serial) -> bytearray:
        data = bytearray()
        while True:
            byte = connection.read(1)
            if not byte or byte == b'\x00':
                break
            data += byte
        return data

    def transform_to_g(self, value: int, range: int) -> float:
        return range / 32767 * value
