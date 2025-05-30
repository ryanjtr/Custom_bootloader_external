import tkinter as tk
from tkinter import filedialog, ttk
import serial
import serial.tools.list_ports
import os
import time
import threading
import queue

class BootloaderTransmitter:
    def __init__(self, root):
        self.root = root
        self.root.title("STM32 Bootloader Transmitter")
        self.root.geometry("500x300")

        # Biến lưu đường dẫn file và cổng COM
        self.file_path = tk.StringVar()
        self.com_port = tk.StringVar()

        # Giao diện
        self.create_gui()

        # Baudrate cố định
        self.baudrate = 115200

        # Số lần truyền
        self.transmission_count = 0

        # Queue để báo ACK từ luồng nhận
        self.ack_queue = queue.Queue()

    def create_gui(self):
        # Nhãn và ô nhập đường dẫn file
        tk.Label(self.root, text="Binary File Path:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        tk.Entry(self.root, textvariable=self.file_path, width=40).grid(row=0, column=1, padx=5, pady=5)
        tk.Button(self.root, text="Browse", command=self.browse_file).grid(row=0, column=2, padx=5, pady=5)

        # Nhãn và ô chọn cổng COM
        tk.Label(self.root, text="COM Port:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        com_ports = [port.device for port in serial.tools.list_ports.comports()]
        self.com_port.set(com_ports[0] if com_ports else "No COM Port")
        com_menu = ttk.Combobox(self.root, textvariable=self.com_port, values=com_ports, width=37)
        com_menu.grid(row=1, column=1, padx=5, pady=5)

        # Nhãn baudrate (chỉ hiển thị, không thay đổi được)
        tk.Label(self.root, text="Baudrate: 115200").grid(row=2, column=0, padx=5, pady=5, sticky="w")

        # Nút Run
        tk.Button(self.root, text="Run", command=self.start_transmission).grid(row=3, column=1, pady=10, sticky="e")

        # Nút Test Backup
        tk.Button(self.root, text="Test Backup", command=self.start_test_backup).grid(row=3, column=1, pady=10, sticky="w")

        tk.Button(self.root,text="Test NACK",command=self.start_test_nack).grid(row=3, column=3, pady=20, sticky="w")

    def browse_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Binary files", "*.bin"), ("All files", "*.*")])
        if file_path:
            self.file_path.set(file_path)

    def sender_thread(self, ser, binary_data, stop_event, max_frames=None,corrupt_crc=None):
        """Luồng gửi: Gửi frame start_update, sau đó gửi các frame file bin, và frame kết thúc nếu không giới hạn frame"""
        chunk_size = 249
        self.transmission_count = 0
        
        # Gửi frame START_UPDATE (command byte = 0x56, no payload)
        start_frame = self.create_start_frame()
        print(f"Start Frame: {' '.join(hex(b) for b in start_frame)}")
        try:
            ser.write(start_frame)
            print("Sent START_UPDATE frame")
            # Chờ ACK
            if not self.wait_for_ack(timeout=10):
                print("No ACK received for START_UPDATE frame")
                stop_event.set()
                return
            print("Received ACK for START_UPDATE frame")
        except Exception as e:
            print(f"Error: Failed to send START_UPDATE frame: {str(e)}")
            stop_event.set()
            return

        # Gửi các khối dữ liệu
        for i in range(0, len(binary_data), chunk_size):
            if stop_event.is_set():
                break

            self.transmission_count += 1
            # Dừng nếu đã gửi đủ số frame tối đa (nếu có)
            if max_frames is not None and self.transmission_count > max_frames:
                print(f"Reached maximum frame limit ({max_frames})")
                stop_event.set()
                break

            chunk = binary_data[i:i + chunk_size]
            
            # Tạo frame
            if corrupt_crc:
                frame = self.create_frame_wrong_crc(chunk)
            else:
                frame = self.create_frame(chunk)

            # In frame dưới dạng hex
            print(f"Frame {self.transmission_count}: {' '.join(hex(b) for b in frame)}")

            nack_max=5
            nack_count=0
            # Gửi frame
            while 1:
                try:
                    ser.write(frame)
                    print(f"Transmission {self.transmission_count}: Sent {len(frame)} bytes")

                    # Chờ ACK
                    if not self.wait_for_ack(timeout=10):
                        print(f"Transmission {self.transmission_count}: No ACK received within timeout, Retransmission")
                        nack_count+=1
                        if nack_count == nack_max:
                            print(f"Transmission {self.transmission_count}: No ACK received within timeout")
                            stop_event.set()
                            return
                        else:
                            continue
                    else:
                        print(f"Transmission {self.transmission_count}: Received ACK")
                        break

                except Exception as e:
                    print(f"Error: Failed to send data: {str(e)}")
                    stop_event.set()
                    return

        # Gửi frame cuối cùng với payload rỗng (command byte = 0x57), chỉ khi không có giới hạn frame
        if not stop_event.is_set() and max_frames is None:
            self.transmission_count += 1
            empty_payload = bytearray()  # Payload rỗng
            frame = self.create_frame(empty_payload)

            # In frame dưới dạng hex
            print(f"Final Frame {self.transmission_count}: {' '.join(hex(b) for b in frame)}")

            # Gửi frame
            try:
                ser.write(frame)
                print(f"Transmission {self.transmission_count}: Sent {len(frame)} bytes (empty payload)")

                # Chờ ACK
                if not self.wait_for_ack(timeout=10):
                    print(f"Transmission {self.transmission_count}: No ACK received for final frame within timeout")
                    stop_event.set()
                    return
                print(f"Transmission {self.transmission_count}: Received ACK for final frame")

            except Exception as e:
                print(f"Error: Failed to send final frame: {str(e)}")
                stop_event.set()
                return

        # Hoàn thành truyền
        if not stop_event.is_set():
            print("Transmission completed!")
            stop_event.set()

    def wait_for_ack(self, timeout):
        """Chờ ACK từ queue với thời gian timeout (giây)"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                ack_status = self.ack_queue.get_nowait()
                if isinstance(ack_status, str):  # Xử lý lỗi
                    print(f"Error: {ack_status}")
                    return False
                if ack_status:
                    return True
            except queue.Empty:
                time.sleep(0.01)  # Chờ ngắn để thử lại
        return False

    def receiver_thread(self, ser, stop_event):
        """Luồng nhận: Đọc phản hồi từ STM32 và báo ACK qua queue"""
        while not stop_event.is_set():
            try:
                response = ser.read(3)
                print(f"Response: {response}")
                if response:
                    if response[0] == 0xA5:
                        self.ack_queue.put(True)  # Báo ACK
                    else:
                        self.ack_queue.put(f"Invalid response: {response}")
                        stop_event.set()
                        break
                time.sleep(0.01)  # Nghỉ ngắn để tránh CPU overload
            except Exception as e:
                self.ack_queue.put(f"Error: {str(e)}")
                stop_event.set()
                break

    def start_transmission(self):
        # Kiểm tra file và cổng COM
        file_path = self.file_path.get()
        com_port = self.com_port.get()

        if not file_path or not os.path.exists(file_path):
            print("Error: Please select a valid binary file!")
            return

        if not com_port or "No COM Port" in com_port:
            print("Error: Please select a valid COM port!")
            return

        # Đọc toàn bộ file binary
        try:
            with open(file_path, "rb") as f:
                binary_data = f.read()  # Đọc toàn bộ file
        except Exception as e:
            print(f"Error: Failed to read binary file: {str(e)}")
            return

        # Mở cổng COM
        try:
            ser = serial.Serial(com_port, self.baudrate, timeout=0.1)
        except Exception as e:
            print(f"Error: Failed to open COM port: {str(e)}")
            return

        # Tạo sự kiện để dừng luồng
        stop_event = threading.Event()

        # Bắt đầu luồng nhận
        receiver = threading.Thread(target=self.receiver_thread, args=(ser, stop_event))
        receiver.daemon = True
        receiver.start()

        # Bắt đầu luồng gửi (truyền toàn bộ file)
        sender = threading.Thread(target=self.sender_thread, args=(ser, binary_data, stop_event))
        sender.daemon = True
        sender.start()

        # Chờ luồng gửi hoàn thành
        sender.join()
        stop_event.set()  # Đảm bảo dừng luồng nhận
        receiver.join(timeout=1)

        # Đóng cổng COM
        ser.close()

    def start_test_backup(self):
        # Kiểm tra file và cổng COM
        file_path = self.file_path.get()
        com_port = self.com_port.get()

        if not file_path or not os.path.exists(file_path):
            print("Error: Please select a valid binary file!")
            return

        if not com_port or "No COM Port" in com_port:
            print("Error: Please select a valid COM port!")
            return

        # Đọc toàn bộ file binary
        try:
            with open(file_path, "rb") as f:
                binary_data = f.read()  # Đọc toàn bộ file
        except Exception as e:
            print(f"Error: Failed to read binary file: {str(e)}")
            return

        # Mở cổng COM
        try:
            ser = serial.Serial(com_port, self.baudrate, timeout=0.1)
        except Exception as e:
            print(f"Error: Failed to open COM port: {str(e)}")
            return

        # Tạo sự kiện để dừng luồng
        stop_event = threading.Event()

        # Bắt đầu luồng nhận
        receiver = threading.Thread(target=self.receiver_thread, args=(ser, stop_event))
        receiver.daemon = True
        receiver.start()

        # Bắt đầu luồng gửi (chỉ truyền 10 frame dữ liệu)
        sender = threading.Thread(target=self.sender_thread, args=(ser, binary_data, stop_event, 1))
        sender.daemon = True
        sender.start()

        # Chờ luồng gửi hoàn thành
        sender.join()
        stop_event.set()  # Đảm bảo dừng luồng nhận
        receiver.join(timeout=1)

        # Đóng cổng COM
        ser.close()

    def start_test_nack(self):
            # Kiểm tra file và cổng COM
            file_path = self.file_path.get()
            com_port = self.com_port.get()

            if not file_path or not os.path.exists(file_path):
                print("Error: Please select a valid binary file!")
                return

            if not com_port or "No COM Port" in com_port:
                print("Error: Please select a valid COM port!")
                return

            # Đọc toàn bộ file binary
            try:
                with open(file_path, "rb") as f:
                    binary_data = f.read()  # Đọc toàn bộ file
            except Exception as e:
                print(f"Error: Failed to read binary file: {str(e)}")
                return

            # Mở cổng COM
            try:
                ser = serial.Serial(com_port, self.baudrate, timeout=0.1)
            except Exception as e:
                print(f"Error: Failed to open COM port: {str(e)}")
                return

            # Tạo sự kiện để dừng luồng
            stop_event = threading.Event()

            # Bắt đầu luồng nhận
            receiver = threading.Thread(target=self.receiver_thread, args=(ser, stop_event))
            receiver.daemon = True
            receiver.start()

            # Bắt đầu luồng gửi (chỉ truyền 10 frame dữ liệu)
            sender = threading.Thread(target=self.sender_thread, args=(ser, binary_data, stop_event, 10,1))
            sender.daemon = True
            sender.start()

            # Chờ luồng gửi hoàn thành
            sender.join()
            stop_event.set()  # Đảm bảo dừng luồng nhận
            receiver.join(timeout=1)

            # Đóng cổng COM
            ser.close()

    def get_crc(self, buff, length):
        Crc = 0xFFFFFFFF
        for data in buff[0:length]:
            Crc = Crc ^ data
            for i in range(32):
                if (Crc & 0x80000000):
                    Crc = (Crc << 1) ^ 0x04C11DB7
                else:
                    Crc = (Crc << 1)
        return Crc & 0xFFFFFFFF  # Đảm bảo kết quả là 32-bit

    def create_frame(self, payload):
        # Độ dài payload
        payload_len = len(payload)

        # Tạo frame ban đầu (không bao gồm CRC)
        length_to_follow = 1 + 1 + payload_len + 4  # COMMAND_CODE + PAYLOAD_LEN + PAYLOAD + CRC
        frame = bytearray()
        frame.append(length_to_follow)  # LENGTH TO FOLLOW
        frame.append(0x57)             # COMMAND CODE (BL_MEM_WRITE)
        frame.append(payload_len)      # PAYLOAD LENGTH
        frame.extend(payload)          # PAYLOAD

        # Tính CRC32'
        crc = self.get_crc(frame, len(frame))
        frame.extend(crc.to_bytes(4, byteorder='little'))  # CRC32 (4 bytes, little-endian)

        return frame
    
    def create_frame_wrong_crc(self, payload):
        # Độ dài payload
        payload_len = len(payload)

        # Tạo frame ban đầu (không bao gồm CRC)
        length_to_follow = 1 + 1 + payload_len + 4  # COMMAND_CODE + PAYLOAD_LEN + PAYLOAD + CRC
        frame = bytearray()
        frame.append(length_to_follow)  # LENGTH TO FOLLOW
        frame.append(0x57)             # COMMAND CODE (BL_MEM_WRITE)
        frame.append(payload_len)      # PAYLOAD LENGTH
        frame.extend(payload)          # PAYLOAD

        # Tính CRC32
        crc = self.get_crc(frame, len(frame))+1
        frame.extend(crc.to_bytes(4, byteorder='little'))  # CRC32 (4 bytes, little-endian)

        return frame

    def create_start_frame(self):
        # Tạo frame START_UPDATE (command byte = 0x56, no payload)
        frame = bytearray()
        length_to_follow = 1 + 4  # COMMAND_CODE + CRC
        frame.append(length_to_follow)  # LENGTH TO FOLLOW
        frame.append(0x56)             # COMMAND CODE (START_UPDATE)

        # Tính CRC32
        crc = self.get_crc(frame, len(frame))
        frame.extend(crc.to_bytes(4, byteorder='little'))  # CRC32 (4 bytes, little-endian)

        return frame

if __name__ == "__main__":
    root = tk.Tk()
    app = BootloaderTransmitter(root)
    root.mainloop()