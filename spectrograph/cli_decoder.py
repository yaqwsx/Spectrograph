from cobs import cobs
import serial
import sys

def read_cobs_packet(connection: serial.Serial) -> bytearray:
    data = bytearray()
    while True:
        byte = connection.read(1)
        if not byte or byte == b'\x00':
            break
        data += byte
    return data

def transform_to_g(value: int, range: int) -> float:
    return range / 32767 * value

def run(port: str) -> None:
    counter = 0
    with serial.Serial(port=port, baudrate=921600) as connection:
        while True:
            data = read_cobs_packet(connection)
            if not data:
                continue

            packet = cobs.decode(data)
            packet_type = packet[0]
            if packet_type != 1 or len(packet) != 8:
                continue
            range_value = packet[1]
            x = int.from_bytes(packet[2:4], byteorder='little', signed=True)
            y = int.from_bytes(packet[4:6], byteorder='little', signed=True)
            z = int.from_bytes(packet[6:8], byteorder='little', signed=True)

            counter += 1
            if counter == 1000:
                counter = 0
                print(f"{transform_to_g(x, range_value)}, {transform_to_g(y, range_value)}, {transform_to_g(z, range_value)}")


if __name__ == "__main__":
    run(sys.argv[1])
