package common

import (
	"math"
	"net"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/op/go-logging"
)

var log = logging.MustGetLogger("log")

// ClientConfig Configuration used by the client
type ClientConfig struct {
	ID            string
	ServerAddress string
	LoopAmount    int
	LoopPeriod    time.Duration
	// Lottery bet data
	Nombre     string
	Apellido   string
	Documento  string
	Nacimiento string
	Numero     string
	// Batch processing
	BatchMaxAmount int
}

// Client Entity that encapsulates how
type Client struct {
	config            ClientConfig
	conn              net.Conn
	shutdownRequested bool
	shutdownMutex     sync.RWMutex
	protocol          *LotteryProtocol
}

// NewClient Initializes a new client receiving the configuration
// as a parameter
func NewClient(config ClientConfig) *Client {
	client := &Client{
		config:            config,
		shutdownRequested: false,
		protocol:          NewLotteryProtocol(),
	}

	// Set up signal handler for graceful shutdown
	client.setupSignalHandler()

	return client
}

// CreateClientSocket Initializes client socket. In case of
// failure, error is printed in stdout/stderr and exit 1
// is returned
func (c *Client) createClientSocket() error {
	conn, err := net.Dial("tcp", c.config.ServerAddress)
	if err != nil {
		log.Criticalf(
			"action: connect | result: fail | client_id: %v | error: %v",
			c.config.ID,
			err,
		)
	}
	c.conn = conn
	return nil
}

// setupSignalHandler sets up signal handlers for graceful shutdown
func (c *Client) setupSignalHandler() {
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGTERM) // This makes the incoming signals redirect to the sigChan channel

	go func() { // This is a goroutine that will run in the background and listen for signals
		sig := <-sigChan // This will block until a signal is received in the sigChan channel and then assign it to the sig variable
		log.Infof("action: signal_received | result: success | signal: %v", sig)
		c.shutdownMutex.Lock()
		c.shutdownRequested = true
		c.shutdownMutex.Unlock()
	}()
}

// isShutdownRequested checks if shutdown has been requested
func (c *Client) isShutdownRequested() bool {
	c.shutdownMutex.RLock()
	defer c.shutdownMutex.RUnlock()
	return c.shutdownRequested
}

// cleanup closes all resources and logs the cleanup process
func (c *Client) cleanup() {
	log.Infof("action: cleanup | result: in_progress | client_id: %v", c.config.ID)

	if c.conn != nil {
		if err := c.conn.Close(); err != nil {
			// Check if it's just a "use of closed network connection" error
			if strings.Contains(err.Error(), "use of closed network connection") ||
				strings.Contains(err.Error(), "connection reset by peer") {
				log.Infof("action: cleanup | result: success | client_id: %v | resource: connection | note: already_closed", c.config.ID)
			} else {
				log.Errorf("action: cleanup | result: fail | client_id: %v | resource: connection | error: %v",
					c.config.ID, err)
			}
		} else {
			log.Infof("action: cleanup | result: success | client_id: %v | resource: connection", c.config.ID)
		}
	}

	log.Infof("action: cleanup | result: success | client_id: %v | message: all_resources_closed", c.config.ID)
}

// StartClientLoop Send lottery bets to the server in batches until some time threshold is met
func (c *Client) StartClientLoop() {
	defer c.cleanup()

	// Create CSV reader for this client's agency
	csvReader := NewCSVReader(c.config.ID)

	// Get total number of bets available
	totalBets, err := csvReader.GetTotalBets()
	if err != nil {
		log.Errorf("action: get_total_bets | result: fail | client_id: %v | error: %v",
			c.config.ID, err)
		return
	}

	log.Infof("action: csv_loaded | result: success | client_id: %v | total_bets: %v",
		c.config.ID, totalBets)

	// Calculate total number of batches needed
	totalBatches := int(math.Ceil(float64(totalBets) / float64(c.config.BatchMaxAmount)))
	log.Infof("action: batch_calculation | result: success | client_id: %v | total_bets: %v | batch_size: %v | total_batches: %v",
		c.config.ID, totalBets, c.config.BatchMaxAmount, totalBatches)

	// Create single persistent connection to server for all batches
	if err := c.createClientSocket(); err != nil {
		log.Errorf("action: create_socket | result: fail | client_id: %v | error: %v",
			c.config.ID, err)
		return
	}
	log.Infof("action: connection_established | result: success | client_id: %v", c.config.ID)

	// Send bets in batches over the same connection
	batchCount := 0
	betsProcessed := 0

	for batchCount < totalBatches && !c.isShutdownRequested() {
		log.Infof("action: batch_iteration | result: in_progress | client_id: %v | batch: %v/%v",
			c.config.ID, batchCount+1, totalBatches)

		// Read batch of bets from CSV with offset
		bets, err := csvReader.ReadBets(c.config.BatchMaxAmount, betsProcessed)
		if err != nil {
			log.Errorf("action: read_batch | result: fail | client_id: %v | error: %v",
				c.config.ID, err)
			return
		}

		log.Infof("action: read_batch | result: success | client_id: %v | bets_read: %v | offset: %v",
			c.config.ID, len(bets), betsProcessed)

		if len(bets) == 0 {
			log.Infof("action: no_more_bets | result: success | client_id: %v", c.config.ID)
			break
		}

		// Convert BetData to Bet objects
		var betObjects []Bet
		for _, betData := range bets {
			bet, err := NewBet(betData.Nombre, betData.Apellido, betData.Documento,
				betData.Nacimiento, strconv.Itoa(betData.Numero))
			if err != nil {
				log.Errorf("action: create_bet | result: fail | client_id: %v | error: %v",
					c.config.ID, err)
				continue
			}
			betObjects = append(betObjects, *bet)
		}

		if len(betObjects) == 0 {
			log.Errorf("action: no_valid_bets | result: fail | client_id: %v", c.config.ID)
			return
		}

		// Send batch using protocol
		batch := &BatchRequest{Bets: betObjects}
		if err := c.protocol.SendBatch(c.conn, batch); err != nil {
			log.Errorf("action: send_batch | result: fail | client_id: %v | error: %v",
				c.config.ID, err)
			return
		}

		// Receive batch response from server
		response, err := c.protocol.ReceiveBatchResponse(c.conn)
		if err != nil {
			log.Errorf("action: receive_batch_response | result: fail | client_id: %v | error: %v",
				c.config.ID, err)
			return
		}

		// Log batch result
		if response.Success {
			log.Infof("action: batch_enviado | result: success | client_id: %v | cantidad: %v",
				c.config.ID, response.Count)
		} else {
			log.Errorf("action: batch_enviado | result: fail | client_id: %v | cantidad: %v",
				c.config.ID, response.Count)
		}

		batchCount++
		betsProcessed += len(betObjects)

		// Wait between batches
		if batchCount < totalBatches && !c.isShutdownRequested() {
			sleepDuration := c.config.LoopPeriod
			sleepInterval := 100 * time.Millisecond

			for sleepDuration > 0 && !c.isShutdownRequested() {
				if sleepDuration < sleepInterval {
					sleepInterval = sleepDuration
				}
				time.Sleep(sleepInterval)
				sleepDuration -= sleepInterval
			}
		}
	}

	if c.isShutdownRequested() {
		log.Infof("action: loop_interrupted | result: success | client_id: %v | reason: shutdown_requested", c.config.ID)
	} else {
		log.Infof("action: loop_finished | result: success | client_id: %v | batches_sent: %v | bets_processed: %v",
			c.config.ID, batchCount, betsProcessed)

		// Send completion notification to server
		if err := c.protocol.SendCompletionNotification(c.conn, c.config.ID); err != nil {
			log.Errorf("action: send_completion | result: fail | client_id: %v | error: %v", c.config.ID, err)
		} else {
			log.Infof("action: send_completion | result: success | client_id: %v", c.config.ID)
		}

		// Close connection to allow other clients to connect and complete
		c.conn.Close()
		log.Infof("action: disconnected_after_completion | result: success | client_id: %v", c.config.ID)

		// Wait a bit for other clients to complete, then start querying for winners
		initialWait := 5 * time.Second
		log.Infof("action: waiting_for_other_clients | result: in_progress | client_id: %v | wait_time: %v", c.config.ID, initialWait)
		time.Sleep(initialWait)

		// Query for winners with retry logic (reconnecting each time)
		maxRetries := 10
		retryDelay := 2 * time.Second

		for retry := 0; retry < maxRetries; retry++ {
			// Reconnect for each winner query attempt
			if err := c.createClientSocket(); err != nil {
				log.Errorf("action: reconnect_for_winner_query | result: fail | client_id: %v | error: %v", c.config.ID, err)
				break
			}

			if err := c.protocol.SendWinnerQuery(c.conn, c.config.ID); err != nil {
				log.Errorf("action: send_winner_query | result: fail | client_id: %v | error: %v", c.config.ID, err)
				c.conn.Close()
				break
			}

			log.Infof("action: send_winner_query | result: success | client_id: %v | attempt: %v", c.config.ID, retry+1)

			// Receive winners response
			winnerCount, isReady, err := c.protocol.ReceiveWinnersResponse(c.conn)
			c.conn.Close() // Always close after receiving response

			if err != nil {
				log.Errorf("action: receive_winners | result: fail | client_id: %v | error: %v", c.config.ID, err)
				break
			}

			if isReady {
				// Lottery is ready, log final result
				log.Infof("action: consulta_ganadores | result: success | cant_ganadores: %v", winnerCount)
				break
			} else {
				// Lottery not ready yet, retry after delay
				log.Infof("action: lottery_pending | result: in_progress | client_id: %v | attempt: %v | retrying_in: %v", c.config.ID, retry+1, retryDelay)

				if retry < maxRetries-1 { // Don't sleep on last attempt
					time.Sleep(retryDelay)
				}
			}
		}
	}
}
