#include "accelerometer.hpp"
#include <PacketSerial.h>
#include "messages.hpp"

namespace pinout {

constexpr int acc_int  = 27;
constexpr int acc_cs   = 26;
constexpr int acc_mosi = 23;
constexpr int acc_miso = 19;
constexpr int acc_sck  = 18;

} // namespace pinout

namespace config {
    constexpr int wdt_timeout_s = 1;
}

namespace bsp {
    extern MPU6500 accelerometer;
    extern PacketSerial io_channel;

    void trap(const char* reason);
    void initialize_acc();
    void report_error(const char* msg);
} // namespace bsp
