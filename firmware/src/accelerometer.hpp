#include <MPU6500_WE.h>
#include <tuple>

class MPU6500: public MPU6500_WE {
public:
    using MPU6500_WE::MPU6500_WE;

    std::tuple<int16_t, int16_t, int16_t> getAccelRawValuesInt() {
        uint8_t rawData[6];
        readMPU9250Register3x16(REGISTER_ACCEL_OUT, rawData);
        int16_t const xRaw = static_cast<int16_t>((rawData[0] << 8) | rawData[1]);
        int16_t const yRaw = static_cast<int16_t>((rawData[2] << 8) | rawData[3]);
        int16_t const zRaw = static_cast<int16_t>((rawData[4] << 8) | rawData[5]);
        return {xRaw, yRaw, zRaw};
    }
};
