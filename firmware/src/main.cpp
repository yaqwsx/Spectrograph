#include <Arduino.h>
#include <atomic>
#include "bsp.hpp"
#include <esp_task_wdt.h>

std::atomic<bool> new_data(false);
int samples_count = 0;
uint32_t start_time = 0;
MPU9250_ACC_RANGE g_range = MPU9250_ACC_RANGE_2G;

int range_to_number(MPU9250_ACC_RANGE range) {
    switch(range) {
        case MPU9250_ACC_RANGE_2G:
            return 2;
        case MPU9250_ACC_RANGE_4G:
            return 4;
        case MPU9250_ACC_RANGE_8G:
            return 8;
        case MPU9250_ACC_RANGE_16G:
            return 16;
    }
    bsp::trap("Unknown range");
}

MPU9250_ACC_RANGE number_to_range(int range) {
    switch (range) {
        case 2:
            return MPU9250_ACC_RANGE_2G;
        case 4:
            return MPU9250_ACC_RANGE_4G;
        case 8:
            return MPU9250_ACC_RANGE_8G;
        case 16:
            return MPU9250_ACC_RANGE_16G;
    }
    bsp::trap("Unknown range");
}

void IRAM_ATTR on_new_data() {
    static bool active = false;
    active = !active;
    if (!active)
        return;

    new_data = true;
    if (samples_count == 0) {
        start_time = micros();
    }
    samples_count++;
}

void on_new_packet(const uint8_t* buffer, size_t size) {
    if (size == 0)
        return;
    switch (buffer[0]) {
        case MessageId::SetAccRange: {
            auto range = number_to_range(buffer[1]);
            bsp::accelerometer.setAccRange(range);
            g_range = range;
        }
        break;
    }
}

void setup() {
    bsp::initialize_acc();
    bsp::io_channel.begin(921600);
    bsp::io_channel.setPacketHandler(&on_new_packet);

    attachInterrupt(pinout::acc_int, on_new_data, RISING);

    esp_task_wdt_init(config::wdt_timeout_s, true);
    esp_task_wdt_add(nullptr);
}

void loop() {
    if (new_data) {
        new_data = false;
        auto [x, y, z] = bsp::accelerometer.getAccelRawValuesInt();

        uint8_t packet_buffer[2 + 3 * 2];
        packet_buffer[0] = MessageId::AccData;
        packet_buffer[1] = range_to_number(g_range);
        memcpy(packet_buffer + 2, &x, 2);
        memcpy(packet_buffer + 4, &y, 2);
        memcpy(packet_buffer + 6, &z, 2);

        bsp::io_channel.send(packet_buffer, sizeof(packet_buffer));
    }
    bsp::io_channel.update();
    esp_task_wdt_reset();
}
