import socket
import logging
import signal
import sys
import threading
from .protocol import LotteryProtocol, ProtocolError
from .utils import store_bets, Bet, load_bets, has_won


class Server:
    def __init__(self, port, listen_backlog, expected_clients=5):
        # Initialize server socket
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.bind(('', port))
        self._server_socket.listen(listen_backlog)
        self._shutdown_requested = False
        
        # Lottery state tracking
        self._completed_agencies = set()  # Track which agencies have completed
        self._lottery_conducted = False   # Track if lottery has been conducted
        self._winners_by_agency = {}      # Store winners for each agency
        self._lottery_lock = threading.Lock()  # Thread safety for lottery state
        self._expected_clients = expected_clients  # Number of clients expected
        
        # Set up signal handler for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """
        Signal handler for graceful shutdown
        """
        logging.info(f'action: signal_received | result: success | signal: {signum}')
        self._shutdown_requested = True

    def _conduct_lottery(self):
        """
        Conduct the lottery draw and determine winners for each agency.
        NOTE: This method should only be called while holding self._lottery_lock
        """
        try:
            logging.info('action: conduct_lottery | result: in_progress')
            if self._lottery_conducted:
                logging.info('action: conduct_lottery | result: success')
                return  # Lottery already conducted
            
            logging.info('action: sorteo | result: success')
            self._lottery_conducted = True
            
            # Load all bets and check for winners
            logging.info('action: loading_bets | result: in_progress')
            try:
                all_bets = list(load_bets())
                logging.info(f'action: loading_bets | result: success | total_bets: {len(all_bets)}')
            except FileNotFoundError:
                logging.warning('action: loading_bets | result: fail | using_empty_list')
                all_bets = []
            except Exception as e:
                logging.error(f'action: loading_bets | result: fail | error: {e} | using_empty_list')
                all_bets = []
            
            winners_by_agency = {}
            
            logging.info('action: checking_winners | result: in_progress')
            for bet in all_bets:
                if has_won(bet):
                    agency_id = str(bet.agency)
                    if agency_id not in winners_by_agency:
                        winners_by_agency[agency_id] = []
                    winners_by_agency[agency_id].append(bet.document)
            
            self._winners_by_agency = winners_by_agency
            logging.info(f'action: lottery_completed | result: success | total_winners: {sum(len(winners) for winners in winners_by_agency.values())}')
            logging.info('action: conduct_lottery | result: success')
        except Exception as e:
            logging.error(f'action: conduct_lottery | result: fail | error: {e}')

    def _check_and_conduct_lottery(self, client_id):
        """
        Check if all agencies have completed and conduct lottery if ready.
        """
        with self._lottery_lock:
            self._completed_agencies.add(client_id)
            logging.info(f'action: agency_completed | result: success | client_id: {client_id} | total_completed: {len(self._completed_agencies)}')
            
            if len(self._completed_agencies) >= self._expected_clients and not self._lottery_conducted:
                # All agencies have completed, conduct lottery
                logging.info(f'action: lottery_trigger | result: success | completed_agencies: {len(self._completed_agencies)}')
                self._conduct_lottery()
            else:
                logging.info(f'action: lottery_wait | result: success | completed: {len(self._completed_agencies)}/{self._expected_clients} | already_conducted: {self._lottery_conducted}')

    def _send_winners_response(self, client_sock, winners):
        """
        Send the list of winner DNIs to the client.
        """
        try:
            # Create winner response message with status
            if self._lottery_conducted:
                winners_str = ",".join(winners) if winners else ""
                response = f"WINNERS:READY:{len(winners)}:{winners_str}"
            else:
                response = f"WINNERS:PENDING:0:"
            
            # Send using protocol format
            LotteryProtocol.send_winners_response(client_sock, response)
        except Exception as e:
            logging.error(f'action: send_winners | result: fail | error: {e}')

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
                logging.info('action: connection_accepted | result: success ')
                self.__handle_client_connection(client_sock)
                logging.info('action: handled_client | result: success ')
        except Exception as e:
            if "Shutdown requested" in str(e):
                logging.info('action: server_loop | result: success | reason: graceful_shutdown')
            else:
                logging.error(f'action: server_loop | result: fail | error: {e}')
        finally:
            self._cleanup()

    def __handle_client_connection(self, client_sock):
        """
        Handle multiple lottery batches from a client using the protocol.
        Handle multiple batches over the same persistent connection.

        If a problem arises in the communication with the client, the
        client socket will also be closed
        """
        try:
            addr = client_sock.getpeername()
            logging.info(f'action: client_connected | result: success | ip: {addr[0]}')
            
            # Handle multiple batches over the same connection
            batch_count = 0
            while True:
                try:
                    logging.info(f'action: receive_message | result: in_progress | ip: {addr[0]}')
                    
                    # Receive message with type information
                    message_type, message_data = LotteryProtocol.receive_message_with_type(client_sock)
                    
                    if message_type == LotteryProtocol.MESSAGE_TYPE_BATCH:
                        # Handle batch message
                        batch_count += 1
                        logging.info(f'action: batch_received | result: success | ip: {addr[0]} | batch_num: {batch_count}')
                        
                        # Deserialize batch data
                        try:
                            batch_data = LotteryProtocol.deserialize_batch_data(message_data)
                            logging.info(f'action: deserialize_batch | result: success | ip: {addr[0]} | bets_count: {len(batch_data)}')
                        except Exception as e:
                            logging.error(f'action: deserialize_batch | result: fail | ip: {addr[0]} | error: {e} | data_length: {len(message_data)}')
                            raise
                        
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
                            logging.error(f'action: apuesta_recibida | result: fail | cantidad: {len(batch_data)}')
                    
                    elif message_type == LotteryProtocol.MESSAGE_TYPE_COMPLETION:
                        # Handle completion notification
                        message = message_data.decode('utf-8').strip()
                        if message.startswith('FINISH:'):
                            client_id = message.split(':')[1]
                            logging.info(f'action: completion_received | result: success | client_id: {client_id}')
                            
                            # Check if all agencies completed and conduct lottery if needed
                            self._check_and_conduct_lottery(client_id)
                            
                            # Client will disconnect and reconnect for winner query
                            break  # Close this connection, client will reconnect for winner query
                        else:
                            logging.error(f'action: completion_received | result: fail | invalid_message: {message}')
                            break
                    
                    elif message_type == LotteryProtocol.MESSAGE_TYPE_WINNER_QUERY:
                        # Handle winner query
                        message = message_data.decode('utf-8').strip()
                        if message.startswith('QUERY_WINNERS:'):
                            client_id = message.split(':')[1]
                            logging.info(f'action: winner_query_received | result: success | client_id: {client_id}')
                            
                            # Check if lottery has been conducted
                            if not self._lottery_conducted:
                                agency_winners = []  # Return empty if lottery not conducted yet
                            else:
                                agency_winners = self._winners_by_agency.get(client_id, [])
                            
                            # Send winners for this agency
                            self._send_winners_response(client_sock, agency_winners)
                            logging.info(f'action: winners_sent | result: success | client_id: {client_id} | count: {len(agency_winners)}')
                            break  # Client received winners, connection done
                        else:
                            logging.error(f'action: winner_query | result: fail | invalid_message: {message}')
                            break
                    
                    else:
                        # Unknown message type
                        logging.error(f'action: receive_message | result: fail | unknown_message_type: {message_type}')
                        break
                
                except (ProtocolError, OSError) as e:
                    logging.info(f'action: client_disconnected | result: success | ip: {addr[0]} | batches_processed: {batch_count} | reason: {type(e).__name__}')
                    break
                except Exception as e:
                    logging.error(f'action: handle_message | result: fail | ip: {addr[0]} | error: {e}')
                    break
            
        except Exception as e:
            logging.error(f'action: handle_client | result: fail | error: {e}')
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
        logging.info('action: cleanup | result: in_progress | resource: all')
        
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
