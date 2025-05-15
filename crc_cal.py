def get_crc(buff, length):
    Crc = 0xFFFFFFFF
    for data in buff[0:length]:
        Crc = Crc ^ data
        for i in range(32):
            if (Crc & 0x80000000):
                Crc = (Crc << 1) ^ 0x04C11DB7
            else:
                Crc = (Crc << 1)
    return Crc & 0xFFFFFFFF  # Đảm bảo kết quả là 32-bit

# Dữ liệu đầu vào
buff = [0x10, 0x57, 0x0A, 0x00, 0x00, 0x02, 0x20, 0x55, 0x07, 0x00, 0x08, 0xD1, 0x06]
length = 13

# Tính CRC
crc = get_crc(buff, length)
print(f"CRC: 0x{crc:08X}")