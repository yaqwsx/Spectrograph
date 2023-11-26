#include <Arduino.h>
#include <atomic>
#include "bsp.hpp"
#include <esp_task_wdt.h>

std::atomic<bool> new_data(false);
int samples_count = 0;
uint32_t start_time = 0;

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

void setup() {
    bsp::initialize_acc();
    bsp::io_channel.begin(921600);

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
        packet_buffer[1] = 2; // Range, for the moment fixed
        memcpy(packet_buffer + 2, &x, 2);
        memcpy(packet_buffer + 4, &y, 2);
        memcpy(packet_buffer + 6, &z, 2);

        bsp::io_channel.send(packet_buffer, sizeof(packet_buffer));
    }
    bsp::io_channel.update();
    esp_task_wdt_reset();
}
