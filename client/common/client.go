package common

import (
	"bufio"
	"fmt"
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
}

// Client Entity that encapsulates how
type Client struct {
	config            ClientConfig
	conn              net.Conn
	shutdownRequested bool
	shutdownMutex     sync.RWMutex
}

// NewClient Initializes a new client receiving the configuration
// as a parameter
func NewClient(config ClientConfig) *Client {
	client := &Client{
		config:            config,
		shutdownRequested: false,
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

// StartClientLoop Send messages to the client until some time threshold is met
func (c *Client) StartClientLoop() {
	defer c.cleanup()

	// There is an autoincremental msgID to identify every message sent
	// Messages if the message amount threshold has not been surpassed
	for msgID := 1; msgID <= c.config.LoopAmount && !c.isShutdownRequested(); msgID++ {
		// Create the connection the server in every loop iteration. Send an
		if err := c.createClientSocket(); err != nil {
			log.Errorf("action: create_socket | result: fail | client_id: %v | error: %v",
				c.config.ID, err)
			return
		}

		// TODO: Modify the send to avoid short-write
		fmt.Fprintf(
			c.conn,
			"[CLIENT %v] Message N°%v\n",
			c.config.ID,
			msgID,
		)
		msg, err := bufio.NewReader(c.conn).ReadString('\n')
		c.conn.Close()

		if err != nil {
			log.Errorf("action: receive_message | result: fail | client_id: %v | error: %v",
				c.config.ID,
				err,
			)
			return
		}

		log.Infof("action: receive_message | result: success | client_id: %v | msg: %v",
			c.config.ID,
			msg,
		)

		// Wait a time between sending one message and the next one
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
