import logging
import socket
from typing import Dict, Any, Optional, List

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
    MAX_MESSAGE_SIZE = 8092  # Maximum message size in bytes
    
    # Message types
    MESSAGE_TYPE_BATCH = 1      # Batch of bets
    MESSAGE_TYPE_COMPLETION = 2 # Completion notification
    
    @staticmethod
    def deserialize_bet(data: bytes) -> Dict[str, Any]:
        """
        Deserialize a single bet data from bytes using custom binary protocol.

        Protocol format (one bet):
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
            #logger.debug(f"data: {data}")

            # Extract message length from header
            header_bytes = data[:LotteryProtocol.HEADER_SIZE]
            message_length = int.from_bytes(header_bytes, byteorder='big')
            
            if message_length > LotteryProtocol.MAX_MESSAGE_SIZE:
                raise ProtocolError(f"Message too large: {message_length} bytes")
            
            # Extract message data
            message_data = data[LotteryProtocol.HEADER_SIZE:LotteryProtocol.HEADER_SIZE + message_length]
            #logger.debug(f"message_data: {message_data}")
            #logger.debug(f"Actual message data length: {len(message_data)}, message_length: {message_length}")

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

                #logger.debug(f"field_len: {field_len}, offset: {offset}, len(message_data): {len(message_data)}")
                
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
    def deserialize_bet_data(data: bytes) -> Dict[str, Any]:
        """
        Deserialize a single bet from raw data (without header).
        
        Protocol format (bet data only):
        - Fields: Each field prefixed with 2 bytes for the length, then the data
        - Field order: nombre, apellido, documento, nacimiento, numero
        """
        try:
            offset = 0
            fields = []
            
            # Extract first 4 fields (nombre, apellido, documento, nacimiento)
            for i in range(4):
                if offset + 2 > len(data):
                    raise ProtocolError(f"Incomplete field length for field {i}")
                
                field_length = int.from_bytes(data[offset:offset+2], byteorder='big')
                offset += 2
                
                if offset + field_length > len(data):
                    raise ProtocolError(f"Incomplete field data for field {i}")
                
                field_data = data[offset:offset+field_length].decode('utf-8')
                fields.append(field_data)
                offset += field_length
            
            # Extract numero field (4 bytes, no length prefix)
            if offset + 4 > len(data):
                raise ProtocolError("Incomplete numero field")
            
            numero = int.from_bytes(data[offset:offset+4], byteorder='big')
            
            return {
                'nombre': fields[0],
                'apellido': fields[1], 
                'documento': fields[2],
                'nacimiento': fields[3],
                'numero': numero
            }
            
        except (IndexError, UnicodeDecodeError) as e:
            raise ProtocolError(f"Bet data deserialization failed: {e}")
    
    @staticmethod
    def receive_message_with_type(socket):
        """
        Receive a message and return both the message type and data.
        Returns tuple: (message_type, message_data)
        """
        try:
            # First, receive the header (4 bytes for message length)
            header_data = b''
            while len(header_data) < LotteryProtocol.HEADER_SIZE:
                chunk = socket.recv(LotteryProtocol.HEADER_SIZE - len(header_data))
                if not chunk:
                    raise ProtocolError("Connection closed while receiving header")
                header_data += chunk
            
            # Extract message length from header
            message_length = int.from_bytes(header_data, 'big')
            
            if message_length > LotteryProtocol.MAX_MESSAGE_SIZE:
                raise ProtocolError(f"Message too large: {message_length} bytes")
            
            # Receive the complete message (type + data)
            message_data = b''
            while len(message_data) < message_length:
                chunk = socket.recv(message_length - len(message_data))
                if not chunk:
                    raise ProtocolError("Connection closed while receiving message")
                message_data += chunk
            
            # Extract message type (first byte)
            if len(message_data) < 1:
                raise ProtocolError("Message too short to contain type")
            
            message_type = message_data[0]
            actual_data = message_data[1:]  # Rest of the message after type byte
            
            return message_type, actual_data
            
        except socket.timeout:
            raise ProtocolError("Timeout while receiving message")
        except Exception as e:
            raise ProtocolError(f"Failed to receive message: {e}")
    
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
    def receive_batch(socket) -> List[Dict[str, Any]]:
        """
        Receive batch of bets from socket using the protocol.
        """
        message_type, message_data = LotteryProtocol.receive_message_with_type(socket)
        
        # Verify this is a batch message
        if message_type != LotteryProtocol.MESSAGE_TYPE_BATCH:
            raise ProtocolError(f"Expected batch message (type {LotteryProtocol.MESSAGE_TYPE_BATCH}), got type {message_type}")
        
        # Deserialize the batch data (without the type byte, since it's already removed)
        return LotteryProtocol.deserialize_batch_data(message_data)
    
    @staticmethod
    def deserialize_batch_data(data: bytes) -> List[Dict[str, Any]]:
        """
        Deserialize batch of bets from message data (without header and type).
        
        Protocol format (batch data only):
        - Batch size: 4 bytes (number of bets in batch)
        - For each bet: same format as individual bet
        """
        try:
            offset = 0
            
            # Read batch size (number of bets)
            if len(data) < 4:
                raise ProtocolError("Incomplete batch data: missing batch size")
            
            batch_size = int.from_bytes(data[offset:offset+4], byteorder='big')
            offset += 4
            
            bets = []
            for i in range(batch_size):
                # Read bet length header
                if offset + 4 > len(data):
                    raise ProtocolError(f"Incomplete bet data: missing length header for bet {i}")
                
                bet_length = int.from_bytes(data[offset:offset+4], byteorder='big')
                offset += 4
                
                # Read bet data
                if offset + bet_length > len(data):
                    raise ProtocolError(f"Incomplete bet data: expected {bet_length} bytes for bet {i}")
                
                bet_data = data[offset:offset+bet_length]
                offset += bet_length
                
                # Deserialize individual bet (without header)
                bet = LotteryProtocol.deserialize_bet_data(bet_data)
                bets.append(bet)
            
            return bets
            
        except (IndexError, UnicodeDecodeError) as e:
            raise ProtocolError(f"Batch deserialization failed: {e}")
    
    @staticmethod
    def deserialize_batch(data: bytes) -> List[Dict[str, Any]]:
        """
        Deserialize batch of bets from bytes using custom binary protocol.
        
        Protocol format (batch of bets):
        - Header: 4 bytes (indicates message length, excluding the header itself)
        - Batch size: 4 bytes (number of bets in batch)
        - For each bet: same format as individual bet

        | Len. Header (LH) |    Batch size    |      Bet 1       |      Bet 2       |       ...        |  Bet batch_size  |
        |------------------|------------------|------------------|------------------|------------------|------------------|
        |     4 bytes      |     4 bytes      | LH |    Data     | LH |    Data     | LH |    Data     | LH |    Data     | LH = 4 bytes

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
                raise ProtocolError("Incomplete message or wrong message length")
            
            # Extract batch size (4 bytes)
            if len(message_data) < 4:
                raise ProtocolError("Incomplete batch size")
            batch_size = int.from_bytes(message_data[:4], byteorder='big')

            offset = 4
            
            bets = []
            for i in range(batch_size):
                if offset + 4 > len(message_data):
                    raise ProtocolError("Incomplete bet header")

                bet_length = int.from_bytes(message_data[offset:offset+4], byteorder="big")
                bet_end = offset + 4 + bet_length  # 4 for header + bet_length for body

                if bet_end > len(message_data):
                    raise ProtocolError("Incomplete bet data")

                bet_data = message_data[offset:bet_end]
                #logger.debug(f"bet_data: {bet_data}")
                #logger.debug(f"Actual bet data length: {len(bet_data)}, bet_end: {bet_end}")

                bet = LotteryProtocol.deserialize_bet(bet_data)
                bets.append(bet)

                offset = bet_end
            
            return bets
            
        except Exception as e:
            raise ProtocolError(f"Batch deserialization failed: {e}")
    
    @staticmethod
    def acknowledge_batch(socket, success: bool, count: int) -> None:
        """
        Acknowledge the client that the batch has been received and processed.
        """
        try:
            if success:
                acknowledgment = f"action: apuesta_recibida | result: success | cantidad: {count}\n"
            else:
                acknowledgment = f"action: apuesta_recibida | result: fail | cantidad: {count}\n"
            socket.send(acknowledgment.encode('utf-8'))
        except OSError as e:
            raise ProtocolError(f"Batch acknowledgment send failed: {e}")
    
    @staticmethod
    def receive_completion_notification(socket):
        """
        Receive completion notification from client using protocol format.
        Returns the client ID that sent the completion notification.
        """
        try:
            message_type, message_data = LotteryProtocol.receive_message_with_type(socket)
            
            # Verify this is a completion message
            if message_type != LotteryProtocol.MESSAGE_TYPE_COMPLETION:
                raise ProtocolError(f"Expected completion message (type {LotteryProtocol.MESSAGE_TYPE_COMPLETION}), got type {message_type}")
            
            # Decode the completion message
            message = message_data.decode('utf-8').strip()
            
            if message.startswith('FINISH:'):
                client_id = message.split(':')[1]
                return client_id
            else:
                raise ProtocolError(f"Invalid completion message: {message}")
                
        except Exception as e:
            raise ProtocolError(f"Failed to receive completion notification: {e}")
    
    @staticmethod
    def acknowledge_bet(socket, document: str, number: int) -> None:
        """
        Acknowledge the client that the bet has been received and stored.
        """
        try:
            acknowledgment = f"apuesta almacenada | dni: {document} | numero: {number}\n"
            socket.send(acknowledgment.encode('utf-8'))
        except OSError as e:
            raise ProtocolError(f"Acknowledgment send failed: {e}")
