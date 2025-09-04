package common

import (
	"bytes"
	"encoding/binary"
	"fmt"
	"net"
	"strconv"
	"strings"
	"time"

	"github.com/op/go-logging"
)

var protocolLog = logging.MustGetLogger("protocol")

// Protocol constants
const (
	HeaderSize     = 4    // 4 bytes for message length
	MaxMessageSize = 4096 // Maximum message size in bytes
	ReceiveTimeout = 5 * time.Second
)

type ProtocolError struct {
	Message string
}

func (e *ProtocolError) Error() string {
	return e.Message
}

// LotteryProtocol handles communication protocol for the lottery system
type LotteryProtocol struct{}

// BatchRequest represents a batch of bets to be sent
type BatchRequest struct {
	Bets []Bet
}

// BatchResponse represents the server's response to a batch
type BatchResponse struct {
	Success bool
	Message string
	Count   int
}

func NewLotteryProtocol() *LotteryProtocol {
	return &LotteryProtocol{}
}

// serializeBet serializes bet data using custom binary protocol
func (p *LotteryProtocol) serializeBet(betData map[string]interface{}) ([]byte, error) {
	// Extract fields in fixed order and check if they are of the expected type
	nombre, ok := betData["nombre"].(string)
	if !ok {
		return nil, &ProtocolError{Message: "nombre field missing or invalid"}
	}
	apellido, ok := betData["apellido"].(string)
	if !ok {
		return nil, &ProtocolError{Message: "apellido field missing or invalid"}
	}
	documento, ok := betData["documento"].(string)
	if !ok {
		return nil, &ProtocolError{Message: "documento field missing or invalid"}
	}
	nacimiento, ok := betData["nacimiento"].(string)
	if !ok {
		return nil, &ProtocolError{Message: "nacimiento field missing or invalid"}
	}
	numero, ok := betData["numero"].(int)
	if !ok {
		return nil, &ProtocolError{Message: "numero field missing or invalid"}
	}

	// Convert strings to bytes
	nombreBytes := []byte(nombre)
	apellidoBytes := []byte(apellido)
	documentoBytes := []byte(documento)
	nacimientoBytes := []byte(nacimiento)

	// Build message: each field prefixed with 2-byte length
	messageParts := make([][]byte, 0, 9)

	// Add each string field with length prefix
	for _, fieldData := range [][]byte{nombreBytes, apellidoBytes, documentoBytes, nacimientoBytes} {
		fieldLen := len(fieldData)
		if fieldLen > 65535 { // Max 2-byte length
			return nil, &ProtocolError{Message: fmt.Sprintf("Field too large: %d bytes", fieldLen)}
		}

		// Add 2-byte length prefix
		lenBytes := make([]byte, 2)
		binary.BigEndian.PutUint16(lenBytes, uint16(fieldLen))
		messageParts = append(messageParts, lenBytes)
		messageParts = append(messageParts, fieldData)
	}

	// Add numero as fixed-length 4-byte integer
	numeroBytes := make([]byte, 4)
	binary.BigEndian.PutUint32(numeroBytes, uint32(numero))
	messageParts = append(messageParts, numeroBytes)

	// Combine all parts
	var buf bytes.Buffer
	for _, part := range messageParts {
		buf.Write(part)
	}
	message := buf.Bytes()

	// Check total message size
	if len(message) > MaxMessageSize {
		return nil, &ProtocolError{Message: fmt.Sprintf("Message too large: %d bytes", len(message))}
	}

	// Create header with message length
	header := make([]byte, HeaderSize)
	binary.BigEndian.PutUint32(header, uint32(len(message)))

	// Combine header and message
	return append(header, message...), nil
}

// sendMessage sends the complete message through the socket
func (p *LotteryProtocol) sendMessage(conn net.Conn, message []byte) error {
	totalSent := 0
	for totalSent < len(message) {
		sent, err := conn.Write(message[totalSent:])
		if err != nil {
			return &ProtocolError{Message: fmt.Sprintf("Send failed: %v", err)}
		}
		if sent == 0 {
			return &ProtocolError{Message: "Connection closed by peer"}
		}
		totalSent += sent
		protocolLog.Debugf("Sent %d bytes, total: %d/%d", sent, totalSent, len(message))
	}
	return nil
}

// SendBet sends bet data through socket using the protocol
func (p *LotteryProtocol) SendBet(conn net.Conn, betData map[string]interface{}) error {
	message, err := p.serializeBet(betData)
	if err != nil {
		return err
	}
	return p.sendMessage(conn, message)
}

// ReceiveAcknowledgment receives a simple acknowledgment from the server
func (p *LotteryProtocol) ReceiveAcknowledgment(conn net.Conn) (string, int, error) {
	// Set receive timeout
	conn.SetReadDeadline(time.Now().Add(ReceiveTimeout))

	// Read until newline
	buffer := make([]byte, 1024)
	n, err := conn.Read(buffer)
	if err != nil {
		return "", 0, &ProtocolError{Message: fmt.Sprintf("Failed to receive acknowledgment: %v", err)}
	}

	// Parse acknowledgment: "apuesta almacenada | dni: {document} | numero: {number}\n"
	ackStr := string(buffer[:n])
	ackStr = ackStr[:len(ackStr)-1] // Remove newline

	dniStart := strings.Index(ackStr, "dni: ")
	if dniStart == -1 {
		return "", 0, &ProtocolError{Message: "Invalid acknowledgment format: missing dni"}
	}
	dniStart += 5 // Skip "dni: "
	dniEnd := strings.Index(ackStr[dniStart:], " |")
	if dniEnd == -1 {
		return "", 0, &ProtocolError{Message: "Invalid acknowledgment format: missing dni end"}
	}
	document := ackStr[dniStart : dniStart+dniEnd]

	// Extract number
	numeroStart := strings.Index(ackStr, "numero: ")
	if numeroStart == -1 {
		return "", 0, &ProtocolError{Message: "Invalid acknowledgment format: missing numero"}
	}
	numeroStart += 8 // Skip "numero: "
	number, err := strconv.Atoi(ackStr[numeroStart:])
	if err != nil {
		return "", 0, &ProtocolError{Message: fmt.Sprintf("Invalid number in acknowledgment: %v", err)}
	}

	return document, number, nil
}

// serializes a batch of bets (BatchRequest) to be sent to the server
func (p *LotteryProtocol) SerializeBatch(batch *BatchRequest) ([]byte, error) {
	var messageParts [][]byte

	// Add batch size (number of bets)
	batchSizeBytes := make([]byte, 4)
	binary.BigEndian.PutUint32(batchSizeBytes, uint32(len(batch.Bets)))
	messageParts = append(messageParts, batchSizeBytes)

	// Serialize each bet and append to the message parts array
	for _, bet := range batch.Bets {
		betBytes, err := p.serializeBet(bet.ToMap())
		if err != nil {
			return nil, fmt.Errorf("failed to serialize bet: %v", err)
		}
		messageParts = append(messageParts, betBytes)
	}

	// Combine all parts
	var buf bytes.Buffer
	for _, part := range messageParts {
		buf.Write(part)
	}
	message := buf.Bytes()

	// Add header with total message length
	headerBytes := make([]byte, 4)
	binary.BigEndian.PutUint32(headerBytes, uint32(len(message)))

	// Combine header and message
	var finalBuf bytes.Buffer
	finalBuf.Write(headerBytes)
	finalBuf.Write(message)

	return finalBuf.Bytes(), nil
}

// sends a batch of bets to the server
func (p *LotteryProtocol) SendBatch(conn net.Conn, batch *BatchRequest) error {
	data, err := p.SerializeBatch(batch)
	if err != nil {
		return fmt.Errorf("failed to serialize batch: %v", err)
	}

	return p.sendMessage(conn, data)
}

// receives batch response from server and returns a BatchResponse instance with the response data
func (p *LotteryProtocol) ReceiveBatchResponse(conn net.Conn) (*BatchResponse, error) {
	// Set timeout for receiving response
	conn.SetReadDeadline(time.Now().Add(ReceiveTimeout))

	buffer := make([]byte, 1024)
	n, err := conn.Read(buffer)
	if err != nil {
		return nil, fmt.Errorf("Failed to receive batch response: %v", err)
	}

	responseStr := string(buffer[:n])
	responseStr = strings.TrimSpace(responseStr)

	// Parse response: "action: apuesta_recibida | result: success/fail | cantidad: {count}"
	success := strings.Contains(responseStr, "result: success")

	countStart := strings.Index(responseStr, "cantidad: ")
	if countStart == -1 {
		return nil, fmt.Errorf("Invalid batch response format")
	}
	countStart += 10 // Skip "cantidad: "
	countStr := responseStr[countStart:]
	count, err := strconv.Atoi(countStr)
	if err != nil {
		return nil, fmt.Errorf("Invalid count in batch response: %v", err)
	}

	return &BatchResponse{
		Success: success,
		Message: responseStr,
		Count:   count,
	}, nil
}
