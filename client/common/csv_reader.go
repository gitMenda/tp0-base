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

// reads a total of batchSize bets from the CSV file
func (r *CSVReader) ReadBets(batchSize int) ([]BetData, error) {
	file, err := os.Open(r.filePath)
	if err != nil {
		return nil, fmt.Errorf("failed to open CSV file %s: %v", r.filePath, err)
	}
	defer file.Close()

	reader := csv.NewReader(file)
	records, err := reader.ReadAll()
	if err != nil {
		return nil, fmt.Errorf("failed to read CSV file: %v", err)
	}

	// Skip header if present and limit to batch size (might not be needed but won't hurt to check)
	startIndex := 0
	if len(records) > 0 && strings.Contains(strings.ToLower(records[0][0]), "nombre") {
		startIndex = 1
	}

	var bets []BetData
	maxRecords := startIndex + batchSize
	if maxRecords > len(records) {
		maxRecords = len(records)
	}

	// read bets one by one until a total of batchSize bets are read from the CSV file and save them in the bets array
	for i := startIndex; i < maxRecords; i++ {
		if len(records[i]) < 5 {
			continue // Skip incomplete records
		}

		numero, err := strconv.Atoi(records[i][4])
		if err != nil {
			continue // Skip records with invalid numbers
		}

		bet := BetData{
			Nombre:     strings.TrimSpace(records[i][0]),
			Apellido:   strings.TrimSpace(records[i][1]),
			Documento:  strings.TrimSpace(records[i][2]),
			Nacimiento: strings.TrimSpace(records[i][3]),
			Numero:     numero,
		}

		bets = append(bets, bet)
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
	records, err := reader.ReadAll()
	if err != nil {
		return 0, fmt.Errorf("failed to read CSV file: %v", err)
	}

	// Skip header if present
	if len(records) > 0 && strings.Contains(strings.ToLower(records[0][0]), "nombre") {
		return len(records) - 1, nil
	}

	return len(records), nil
}
