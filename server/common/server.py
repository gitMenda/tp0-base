import socket
import logging
import signal
import sys
from .protocol import LotteryProtocol, ProtocolError
from .utils import store_bets, Bet


class Server:
    def __init__(self, port, listen_backlog):
        # Initialize server socket
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.bind(('', port))
        self._server_socket.listen(listen_backlog)
        self._shutdown_requested = False
        
        # Set up signal handler for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """
        Signal handler for graceful shutdown
        """
        logging.info(f'action: signal_received | result: success | signal: {signum}')
        self._shutdown_requested = True

    def run(self):
        """
        Server loop with graceful shutdown support

        Server that accept a new connections and establishes a
        communication with a client. After client with communucation
        finishes, servers starts to accept new connections again
        """
        try:
            while not self._shutdown_requested:
                client_sock = self.__accept_new_connection()
                self.__handle_client_connection(client_sock)
        except Exception as e:
            if "Shutdown requested" in str(e):
                logging.info('action: server_loop | result: success | reason: graceful_shutdown')
            else:
                logging.error(f'action: server_loop | result: fail | error: {e}')
        finally:
            self._cleanup()

    def __handle_client_connection(self, client_sock):
        """
        Handle lottery bet from a client using the protocol.

        If a problem arises in the communication with the client, the
        client socket will also be closed
        """
        try:
            addr = client_sock.getpeername()
            logging.info(f'action: receive_bet | result: in_progress | ip: {addr[0]}')
            
            # Receive bet data using protocol
            bet_data = LotteryProtocol.receive_bet(client_sock)
            
            # Create bet object from received data using utils.Bet class
            bet = Bet(
                agency="1",  # Default agency for now
                first_name=bet_data['nombre'],
                last_name=bet_data['apellido'],
                document=bet_data['documento'],
                birthdate=bet_data['nacimiento'],
                number=str(bet_data['numero'])
            )
            
            # Store the bet using the provided function
            store_bets([bet])  # Pass as a list
            success = True  # store_bets doesn't return a value, assume success
            
            if success:
                # Log successful storage
                logging.info(f'action: apuesta_almacenada | result: success | dni: {bet.document} | numero: {bet.number}')
                # Send acknowledgment to client
                LotteryProtocol.acknowledge_bet(client_sock, bet.document, bet.number)
            else:
                # Log storage failure
                logging.error(f'action: apuesta_almacenada | result: fail | dni: {bet.document} | numero: {bet.number}')
            
        except ProtocolError as e:
            logging.error(f'action: receive_bet | result: fail | error: {e}')
        except (ValueError, KeyError) as e:
            logging.error(f'action: receive_bet | result: fail | error: Invalid bet data: {e}')
        except OSError as e:
            logging.error(f'action: receive_bet | result: fail | error: {e}')
        finally:
            client_sock.close()

    def _cleanup(self):
        """
        Clean up resources and close file descriptors
        """
        logging.info('action: cleanup | result: in_progress')
        
        if self._server_socket:
            try:
                self._server_socket.close()
                logging.info('action: cleanup | result: success | resource: server_socket')
            except Exception as e:
                logging.error(f'action: cleanup | result: fail | resource: server_socket | error: {e}')
        
        logging.info('action: cleanup | result: success | message: all_resources_closed')

    def __accept_new_connection(self):
        """
        Accept new connections with timeout to allow graceful shutdown

        Function blocks until a connection to a client is made or timeout occurs.
        Then connection created is printed and returned
        """

        # Connection arrived
        logging.info('action: accept_connections | result: in_progress')
        
        # Set socket to non-blocking mode with timeout
        self._server_socket.settimeout(1.0)  # 1 second timeout
        
        while not self._shutdown_requested:
            try:
                c, addr = self._server_socket.accept()
                logging.info(f'action: accept_connections | result: success | ip: {addr[0]}')
                return c
            except socket.timeout:
                # Timeout occurred, continue loop to check shutdown flag
                continue
        
        # If we get here, shutdown was requested
        raise Exception("Shutdown requested during accept timeout")
