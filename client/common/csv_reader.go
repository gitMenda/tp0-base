package common

import (
	"encoding/csv"
	"fmt"
	"os"
	"strconv"
	"strings"
)

// represents a single bet from a CSV file
type BetData struct {
	Nombre     string
	Apellido   string
	Documento  string
	Nacimiento string
	Numero     int
}

// handles reading bet data from CSV files
type CSVReader struct {
	filePath string
}

// creates a new CSV reader for the given agency file
func NewCSVReader(agencyID string) *CSVReader {
	return &CSVReader{
		filePath: fmt.Sprintf("/data/agency-%s.csv", agencyID),
	}
}

// reads a total of batchSize bets from the CSV file starting at offset
// without loading the entire file into memory at once
func (r *CSVReader) ReadBets(batchSize int, offset int) ([]BetData, error) {
	file, err := os.Open(r.filePath)
	if err != nil {
		return nil, fmt.Errorf("failed to open CSV file %s: %v", r.filePath, err)
	}
	defer file.Close()

	reader := csv.NewReader(file)

	var bets []BetData
	recordIndex := 0
	hasHeader := false
	targetStart := offset
	targetEnd := offset + batchSize

	for {
		record, err := reader.Read()
		if err != nil {
			// Check if we reached EOF
			if err.Error() == "EOF" {
				break
			}
			return nil, fmt.Errorf("failed to read CSV record: %v", err)
		}

		// Check if first record is a header (eg. column labels: nombre, apellido, documento, nacimiento, numero)
		if recordIndex == 0 && strings.Contains(strings.ToLower(record[0]), "nombre") {
			hasHeader = true
			recordIndex++
			continue
		}

		// Calculate the data record index (excluding header)
		dataIndex := recordIndex
		if hasHeader {
			dataIndex = recordIndex - 1
		}

		// Skip records before our target offset
		if dataIndex < targetStart {
			recordIndex++
			continue
		}

		// Stop if we've read enough records
		if dataIndex >= targetEnd {
			break
		}

		// Process the record if it has enough fields
		if len(record) < 5 {
			recordIndex++
			continue // Skip incomplete/invalid records
		}

		numero, err := strconv.Atoi(record[4])
		if err != nil {
			recordIndex++
			continue // Skip records with invalid numbers
		}

		bet := BetData{
			Nombre:     strings.TrimSpace(record[0]),
			Apellido:   strings.TrimSpace(record[1]),
			Documento:  strings.TrimSpace(record[2]),
			Nacimiento: strings.TrimSpace(record[3]),
			Numero:     numero,
		}

		bets = append(bets, bet)
		recordIndex++
	}

	return bets, nil
}

// returns the total number of bets in the CSV file
func (r *CSVReader) GetTotalBets() (int, error) {
	file, err := os.Open(r.filePath)
	if err != nil {
		return 0, fmt.Errorf("failed to open CSV file %s: %v", r.filePath, err)
	}
	defer file.Close()

	reader := csv.NewReader(file)
	count := 0
	hasHeader := false

	for {
		record, err := reader.Read()
		if err != nil {
			// Check if we reached EOF
			if err.Error() == "EOF" {
				break
			}
			return 0, fmt.Errorf("failed to read CSV record: %v", err)
		}

		// Check if first record is a header
		if count == 0 && strings.Contains(strings.ToLower(record[0]), "nombre") {
			hasHeader = true
		}

		count++
	}

	// Subtract 1 if there's a header
	if hasHeader {
		count--
	}

	return count, nil
}
