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
            logging.info(f'action: receive_batch | result: in_progress | ip: {addr[0]}')
            
            # Receive batch data using protocol
            batch_data = LotteryProtocol.receive_batch(client_sock)
            
            # Process all bets in the batch
            bets = []
            all_success = True
            
            for bet_data in batch_data:
                try:
                    # Create bet object from received data using utils.Bet class
                    bet = Bet(
                        agency="1",  # Default agency for now
                        first_name=bet_data['nombre'],
                        last_name=bet_data['apellido'],
                        document=bet_data['documento'],
                        birthdate=bet_data['nacimiento'],
                        number=str(bet_data['numero'])
                    )
                    bets.append(bet)
                except (ValueError, KeyError) as e:
                    logging.error(f'action: create_bet | result: fail | error: Invalid bet data: {e}')
                    all_success = False
                    break
            
            # Store all bets if all were valid
            if all_success and bets:
                try:
                    store_bets(bets)
                    
                    # Send batch acknowledgment to client
                    LotteryProtocol.acknowledge_batch(client_sock, True, len(bets))
                    logging.info(f'action: apuesta_recibida | result: success | cantidad: {len(bets)}')
                except Exception as e:
                    logging.error(f'action: store_batch | result: fail | error: {e}')
                    LotteryProtocol.acknowledge_batch(client_sock, False, len(bets))
                    logging.error(f'action: apuesta_recibida | result: fail | cantidad: {len(bets)}')
            else:
                # Send failure acknowledgment
                LotteryProtocol.acknowledge_batch(client_sock, False, len(batch_data))
            
        except ProtocolError as e:
            logging.error(f'action: receive_batch | result: fail | error: {e}')
        except OSError as e:
            logging.error(f'action: receive_batch | result: fail | error: {e}')
        finally:
            try:
                client_sock.close()
                logging.info(f'action: cleanup | result: success | resource: client_socket')
            except Exception as e:
                logging.error(f'action: cleanup | result: fail | resource: client_socket | error: {e}')

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
