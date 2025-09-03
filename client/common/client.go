package common

import (
	"net"
	"os"
	"os/signal"
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
			log.Errorf("action: cleanup | result: fail | client_id: %v | resource: connection | error: %v",
				c.config.ID, err)
		} else {
			log.Infof("action: cleanup | result: success | client_id: %v | resource: connection", c.config.ID)
		}
	}

	log.Infof("action: cleanup | result: success | client_id: %v | message: all_resources_closed", c.config.ID)
}

// StartClientLoop Send lottery bets to the server until some time threshold is met
func (c *Client) StartClientLoop() {
	defer c.cleanup()

	// Create bet from configuration
	bet, err := NewBet(c.config.Nombre, c.config.Apellido, c.config.Documento, c.config.Nacimiento, c.config.Numero)
	if err != nil {
		log.Errorf("action: create_bet | result: fail | client_id: %v | error: %v", c.config.ID, err)
		return
	}

	// Send bets until loop amount is reached or shutdown is requested
	for msgID := 1; msgID <= c.config.LoopAmount && !c.isShutdownRequested(); msgID++ {
		// Create connection to server
		if err := c.createClientSocket(); err != nil {
			log.Errorf("action: create_socket | result: fail | client_id: %v | error: %v",
				c.config.ID, err)
			return
		}

		// Send bet using protocol
		if err := c.sendBet(bet); err != nil {
			log.Errorf("action: send_bet | result: fail | client_id: %v | error: %v",
				c.config.ID, err)
			c.conn.Close()
			return
		}

		// Receive acknowledgment from server
		document, number, err := c.protocol.ReceiveAcknowledgment(c.conn)
		c.conn.Close()

		if err != nil {
			log.Errorf("action: receive_acknowledgment | result: fail | client_id: %v | error: %v",
				c.config.ID, err)
			return
		}

		// Log bet result
		log.Infof("action: apuesta_enviada | result: success | dni: %v | numero: %v",
			document, number)

		// Wait a time between sending one bet and the next one
		// We adjust sleep logic to sleep in "chunks" of 100ms so that even with a long LoopPeriod, the client will stop upon receiving a SIGTERM within at most 100ms.
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

	if c.isShutdownRequested() {
		log.Infof("action: loop_interrupted | result: success | client_id: %v | reason: shutdown_requested", c.config.ID)
	} else {
		log.Infof("action: loop_finished | result: success | client_id: %v", c.config.ID)
	}
}

// sendBet sends a bet to the server using the protocol
func (c *Client) sendBet(bet *Bet) error {
	betData := bet.ToMap()
	return c.protocol.SendBet(c.conn, betData)
}
