import serial
import struct
from enum import Enum, IntEnum

import serial.tools
import serial.tools.list_ports


class MSG(IntEnum):
    """Message types as defined in messages.h"""
    RESET = 0 # Reset Microcontroller (flag)
    START = 1 # Start system (temperature control). Returns Ack/Nack
    STOP = 2  # Stop system (temperature control). Returns Ack/Nack
    ACK = 3   # Acknowledge transmission (flag)
    NACK = 4  # Not acknowledge transmission (flag)

    T_SETPOINT = 5  # Temperature setpoint (float). Returns Ack/Nack
    T_ACTUAL = 6    # Actual temperature (float)
    CURRENT = 7     # Current value (float)

    PID_P = 8       # PID proportional gain (float)
    PID_I = 9       # PID integral gain (float)
    PID_D = 10      # PID derivative gain (float)

    STATUS = 11      # Status LEDs, specified by one byte, transmitted as int: [x, x, x, x, Fault, OC, OT, Active] (MSB first)

    MSG_END = 12     # End of transmission

class MSG_TYPE(IntEnum):
    """Message type identifiers"""
    MSG_FLAG = 0x00     # Flag message with no payload
    MSG_VARIABLE = 0x01 # Variable message with fixed 32-bit payload
    MSG_CUSTOM = 0x02   # Custom message with variable length payload


class RxMessage:
    """Structure to hold received message information"""
    def __init__(self, msg=MSG.MSG_END, msg_type=MSG_TYPE.MSG_FLAG, size=0):
        self.msg = msg
        self.msg_type = msg_type
        self.size = size


class Comm:
    """Serial communication class for sending and receiving messages"""
    
    BUF_SIZE = 128
    
    def __init__(self, port=None, baud_rate=115200, timeout=0.1, write_timeout = 1):
        """Initialize the serial communication with the specified baud rate"""
        self.ser = serial.Serial(port=port, baudrate=baud_rate, timeout=timeout, write_timeout=write_timeout)
        
        self.tx_buf = bytearray(self.BUF_SIZE)  # Transmit buffer
        self.tx_buf_pos = 0                     # Current position in transmit buffer
        self.rxm = RxMessage()                  # Current received message info
    
    def available_ports(self):
        return serial.tools.list_ports.comports()

    def connect(self, port):
        # Close port if already open
        if(self.ser.is_open):
            self.ser.close()

        self.ser.port = port

        # Open serial port and flush buffers
        try:
            self.ser.open()
        except:
            raise Exception("Could not open serial port")
            print("That did absolutely not work at all never ever")
        else:
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

    def disconnect(self):
        self.ser.close()

    def add_flag_token(self, identifier):
        """Add a flag message with no payload to the transmit buffer"""
        prefix = (MSG_TYPE.MSG_FLAG << 6) | identifier
        return self.append_token(bytes([prefix]), 1)
    
    def add_variable_token(self, data, identifier):
        """Add a variable message with a 32-bit payload to the transmit buffer"""
        # Ensure data fits in a 32-bit value
        data_bytes = None
        if isinstance(data, int):
            data_bytes = struct.pack('<i', data)  # 32-bit int
        elif isinstance(data, float):
            data_bytes = struct.pack('<f', data)  # 32-bit float
        else:
            raise TypeError("Variable tokens must be int or float")
        
        size = len(data_bytes)
        if size > 255:
            return False
            
        # Prepare token prefix
        prefix = (MSG_TYPE.MSG_VARIABLE << 6) | identifier
        
        # Create token
        token = bytes([prefix]) + data_bytes
        
        return self.append_token(token, len(token))
    
    def add_custom_token(self, data, identifier, size):
        """Add a custom message with a variable length payload to the transmit buffer"""
        if size > 255:
            return False
            
        # Convert data to bytes if it's not already
        if isinstance(data, bytes):
            data_bytes = data
        elif isinstance(data, bytearray):
            data_bytes = bytes(data)
        elif isinstance(data, (int, float, str, list, tuple)):
            if isinstance(data, str):
                data_bytes = data.encode('utf-8')
            elif isinstance(data, (int, float)):
                data_bytes = struct.pack('<f', float(data))
            elif isinstance(data, (list, tuple)):
                if all(isinstance(item, int) for item in data):
                    data_bytes = struct.pack(f'<{len(data)}i', *data)
                elif all(isinstance(item, float) for item in data):
                    data_bytes = struct.pack(f'<{len(data)}f', *data)
                else:
                    raise TypeError("List must contain only ints or only floats")
        else:
            raise TypeError("Unsupported data type for custom token")
        
        # Ensure the data matches the specified size
        if len(data_bytes) != size:
            data_bytes = data_bytes[:size].ljust(size, b'\x00')
            
        # Prepare token
        prefix = (MSG_TYPE.MSG_CUSTOM << 6) | identifier
        token = bytes([prefix, size]) + data_bytes
        
        return self.append_token(token, len(token))
    
    def append_token(self, token, length):
        """Add a token to the transmit buffer"""
        # Check that token fits into tx buffer, while leaving space for END Token
        if self.tx_buf_pos + length >= self.BUF_SIZE:
            return False
            
        # Append token at end of tx buffer
        self.tx_buf[self.tx_buf_pos:self.tx_buf_pos + length] = token
        self.tx_buf_pos += length
        
        return True
    
    def transmit(self):
        """Transmit the contents of the transmit buffer"""
        if self.tx_buf_pos > 0:
            # Terminate message
            self.tx_buf[self.tx_buf_pos] = MSG.MSG_END
            
            # Send over Serial
            try:
                self.ser.write(self.tx_buf[:self.tx_buf_pos + 1])
            except:
                raise Exception("Failed to write data to serial port")
            
            # Clear transmit buffer
            self.tx_buf = bytearray(self.BUF_SIZE)
            self.tx_buf_pos = 0
    
    def msg_available(self):
        return self.ser.in_waiting != 0

    def clear_input_buffer(self):
        self.ser.reset_input_buffer()

    def get_next_msg(self):
        """Get the next message from the serial port"""
        # Check if data is available
        if self.ser.in_waiting == 0:
            self.rxm = RxMessage()
            return self.rxm
            
        # Read prefix byte
        prefix_bytes = self.ser.read(1)
        if not prefix_bytes:
            self.rxm = RxMessage()
            return self.rxm
            
        prefix = prefix_bytes[0]
        
        # Extract message type and identifier
        msg_type = (prefix >> 6) & 0b11
        msg = prefix & 0b00111111
        
        # Update rx_message structure
        self.rxm.msg = msg
        self.rxm.msg_type = msg_type
        
        # Handle different message types
        if msg_type == MSG_TYPE.MSG_FLAG:
            self.rxm.size = 0
        elif msg_type == MSG_TYPE.MSG_VARIABLE:
            self.rxm.size = 4  # 32-bit value
        elif msg_type == MSG_TYPE.MSG_CUSTOM:
            size_bytes = self.ser.read(1)
            if size_bytes:
                self.rxm.size = size_bytes[0]
            else:
                self.rxm.size = 0
        
        return self.rxm
    
    def get_payload(self, expected_type=None):
        """Read and return the payload for the current message"""
        if self.rxm.msg_type == MSG_TYPE.MSG_FLAG or self.rxm.size == 0:
            return None
            
        # Read the payload data
        data = self.ser.read(self.rxm.size)
        
        # For variable messages, interpret as either int or float
        if self.rxm.msg_type == MSG_TYPE.MSG_VARIABLE:
            if expected_type == int:
                return struct.unpack('<i', data)[0]
            elif expected_type == float:
                return struct.unpack('<f', data)[0]
            else:
                # Default to float for variable messages
                return struct.unpack('<f', data)[0]
        
        # For custom messages, return bytes by default
        if expected_type == int and self.rxm.size == 4:
            return struct.unpack('<i', data)[0]
        elif expected_type == float and self.rxm.size == 4:
            return struct.unpack('<f', data)[0]
        elif expected_type == str:
            try:
                return data.decode('utf-8')
            except UnicodeDecodeError:
                return data
        
        # Return raw bytes for custom messages with no expected type
        return data
    
    def close(self):
        """Close the serial connection"""
        if self.ser and self.ser.is_open:
            self.ser.close()