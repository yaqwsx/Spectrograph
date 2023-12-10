#include "bsp.hpp"
#include <SPI.h>
#include <Arduino.h>
#include <cstdint>
#include <memory>
#include <cstring>

MPU6500 bsp::accelerometer(&SPI, pinout::acc_cs, true);
PacketSerial bsp::io_channel;

void bsp::trap(const char* reason) {
    bsp::report_error(reason);
    delay(500);
    ESP.restart();
    // Unreachable
    while (true)
        delay(1);
}

void bsp::initialize_acc() {
    SPI.begin();
    if(!accelerometer.init())
        bsp::trap("Failed to initialize accelerometer");
    accelerometer.setAccRange(MPU6500_ACC_RANGE_2G);
    accelerometer.enableAccAxes(MPU9250_ENABLE_XYZ);
    accelerometer.enableAccDLPF(false);
    accelerometer.setIntPinPolarity(MPU9250_ACT_HIGH);
    accelerometer.enableIntLatch(false);
    accelerometer.enableInterrupt(MPU9250_DATA_READY);
    accelerometer.setSampleRateDivider(1);
}

void bsp::report_error(const char *msg) {
    int len = strlen(msg);
    std::unique_ptr<uint8_t[]> buffer(new uint8_t[1 + len]);
    buffer[0] = MessageId::Error;
    memcpy(&buffer[1], msg, len);

    bsp::io_channel.send(buffer.get(), len + 1);
}
