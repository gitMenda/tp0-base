import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ProtocolError(Exception):
    """Custom exception for protocol-related errors"""
    pass

class LotteryProtocol:
    """
    Communication protocol for lottery system.
    Handles serialization, deserialization, and socket communication.
    """
    
    HEADER_SIZE = 4  # 4 bytes for message length header
    MAX_MESSAGE_SIZE = 4096  # Maximum message size in bytes
    
    @staticmethod
    def deserialize_bet(data: bytes) -> Dict[str, Any]:
        """
        Deserialize bet data from bytes using custom binary protocol.

        Protocol format:
        - Header: 4 bytes (indicates message length, excluding the header itself)
        - Fields: Each field prefixed with 2 bytes for the length, then the data
        - Field order: nombre, apellido, documento, nacimiento, numero

        | Len. Header (LH) |      Field 1     |      Field 2     |      Field 3     |      Field 4     | Field 5 (Numero) |
        |------------------|------------------|------------------|------------------|------------------|------------------|
        |    4 bytes       | LH |    Data     | LH |    Data     | LH |    Data     | LH |    Data     |    4 bytes       | LH = 2 bytes
        """
        try:
            if len(data) < LotteryProtocol.HEADER_SIZE:
                raise ProtocolError("Incomplete header")
            
            # Extract message length from header
            header_bytes = data[:LotteryProtocol.HEADER_SIZE]
            message_length = int.from_bytes(header_bytes, byteorder='big')
            
            if message_length > LotteryProtocol.MAX_MESSAGE_SIZE:
                raise ProtocolError(f"Message too large: {message_length} bytes")
            
            # Extract message data
            message_data = data[LotteryProtocol.HEADER_SIZE:LotteryProtocol.HEADER_SIZE + message_length]
            
            if len(message_data) != message_length:
                raise ProtocolError("Incomplete message")
            
            # Parse fields in fixed order: nombre, apellido, documento, nacimiento, numero
            offset = 0
            fields = []
            
            # Parse first 4 string fields (each prefixed with 2-byte length)
            for _ in range(4):
                if offset + 2 > len(message_data):
                    raise ProtocolError("Incomplete field length")
                
                # 2-byte big-endian decoding using from_bytes
                field_len = int.from_bytes(message_data[offset:offset+2], byteorder='big')
                offset += 2
                
                if offset + field_len > len(message_data):
                    raise ProtocolError("Incomplete field data")
                
                field_data = message_data[offset:offset+field_len]
                fields.append(field_data.decode('utf-8'))
                offset += field_len
            
            # Parse numero as 4-byte integer
            if offset + 4 > len(message_data):
                raise ProtocolError("Incomplete numero field")
            
            # 4-byte big-endian decoding using from_bytes
            numero = int.from_bytes(message_data[offset:offset+4], byteorder='big')
            
            # Check if we consumed all data
            if offset + 4 != len(message_data):
                raise ProtocolError("Extra data in message")
            
            return {
                'nombre': fields[0],
                'apellido': fields[1],
                'documento': fields[2],
                'nacimiento': fields[3],
                'numero': numero
            }
            
        except (IndexError, UnicodeDecodeError) as e:
            raise ProtocolError(f"Deserialization failed: {e}")
    
    @staticmethod
    def receive_message(socket) -> bytes:
        """
        Receive a complete message from socket. Returns the complete message (header + data)
        
        """
        try:
            # First, receive the header
            header_data = b''
            while len(header_data) < LotteryProtocol.HEADER_SIZE:
                chunk = socket.recv(LotteryProtocol.HEADER_SIZE - len(header_data))
                if not chunk:
                    raise ProtocolError("Connection closed by peer")
                header_data += chunk
            
            # Extract message length using from_bytes instead of struct
            message_length = int.from_bytes(header_data, byteorder='big')
            
            if message_length > LotteryProtocol.MAX_MESSAGE_SIZE:
                raise ProtocolError(f"Message too large: {message_length} bytes")
            
            # Receive the complete message
            message_data = b''
            while len(message_data) < message_length:
                chunk = socket.recv(message_length - len(message_data))
                if not chunk:
                    raise ProtocolError("Connection closed by peer")
                message_data += chunk
            
            return header_data + message_data
            
        except OSError as e:
            raise ProtocolError(f"Receive failed: {e}")
    

    @staticmethod
    def receive_bet(socket) -> Dict[str, Any]:
        """
        Receive bet data from socket using the protocol.
        """
        message = LotteryProtocol.receive_message(socket)
        return LotteryProtocol.deserialize_bet(message)
    
    @staticmethod
    def acknowledge_bet(socket, document: str, number: int) -> None:
        """
        Acknowledge the client that the bet has been received and stored.
        """
        try:
            acknowledgment = f"Received and stored bet: {document},{number}\n"
            socket.send(acknowledgment.encode('utf-8'))
        except OSError as e:
            raise ProtocolError(f"Acknowledgment send failed: {e}")
