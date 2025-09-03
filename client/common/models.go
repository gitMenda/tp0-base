package common

import (
	"fmt"
	"strconv"
)

// Bet represents a lottery bet
type Bet struct {
	Nombre     string
	Apellido   string
	Documento  string
	Nacimiento string
	Numero     int
}

// NewBet creates a new bet from environment variables
func NewBet(nombre, apellido, documento, nacimiento, numeroStr string) (*Bet, error) {
	// Parse numero to int
	numero, err := strconv.Atoi(numeroStr)
	if err != nil {
		return nil, fmt.Errorf("invalid numero: %v", err)
	}

	// Validate required fields
	if nombre == "" {
		return nil, fmt.Errorf("nombre is required")
	}
	if apellido == "" {
		return nil, fmt.Errorf("apellido is required")
	}
	if documento == "" {
		return nil, fmt.Errorf("documento is required")
	}
	if nacimiento == "" {
		return nil, fmt.Errorf("nacimiento is required")
	}
	if numero < 0 {
		return nil, fmt.Errorf("numero must be positive")
	}

	return &Bet{
		Nombre:     nombre,
		Apellido:   apellido,
		Documento:  documento,
		Nacimiento: nacimiento,
		Numero:     numero,
	}, nil
}

// ToMap converts bet to map for serialization
func (b *Bet) ToMap() map[string]interface{} {
	return map[string]interface{}{
		"nombre":     b.Nombre,
		"apellido":   b.Apellido,
		"documento":  b.Documento,
		"nacimiento": b.Nacimiento,
		"numero":     b.Numero,
	}
}
