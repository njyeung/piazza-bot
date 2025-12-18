package main

import (
	"fmt"
	"regexp"
	"strings"
	"time"

	"github.com/gocql/gocql"
)

// Parser represents a parser record from Cassandra
type Parser struct {
	ParserName string
	CodeText   string
}

// PiazzaConfig represents Piazza configuration extracted from parser comments
type PiazzaConfig struct {
	NetworkID string
	ClassName string
	Professor string
	Semester  string
	Email     string
	Password  string
}

// ConnectCassandra establishes a connection to Cassandra
func ConnectCassandra(config *Config) (*gocql.Session, error) {
	cluster := gocql.NewCluster(config.CassandraHosts...)
	cluster.Keyspace = config.CassandraKeyspace
	cluster.Consistency = gocql.Quorum
	cluster.Timeout = 10 * time.Second
	cluster.ConnectTimeout = 10 * time.Second

	session, err := cluster.CreateSession()
	if err != nil {
		return nil, fmt.Errorf("failed to connect to Cassandra: %w", err)
	}

	return session, nil
}

// FetchParsers retrieves all parsers from Cassandra
func FetchParsers(session *gocql.Session) ([]Parser, error) {
	query := `SELECT parser_name, code_text FROM parsers`

	iter := session.Query(query).Iter()
	defer iter.Close()

	var parsers []Parser
	var p Parser

	for iter.Scan(&p.ParserName, &p.CodeText) {
		parsers = append(parsers, p)
		p = Parser{} // Reset for next iteration
	}

	if err := iter.Close(); err != nil {
		return nil, fmt.Errorf("error fetching parsers: %w", err)
	}

	return parsers, nil
}

// ExtractPiazzaConfig extracts Piazza configuration from parser comment headers
func ExtractPiazzaConfig(codeText string) (*PiazzaConfig, error) {
	// Extract values using regex
	extractField := func(pattern string) string {
		re := regexp.MustCompile(pattern)
		match := re.FindStringSubmatch(codeText)
		if len(match) > 1 {
			return strings.TrimSpace(match[1])
		}
		return ""
	}

	config := &PiazzaConfig{
		ClassName: extractField(`#\s*CLASS_NAME:\s*(.+)`),
		Professor: extractField(`#\s*PROFESSOR:\s*(.+)`),
		Semester:  extractField(`#\s*SEMESTER:\s*(.+)`),
		NetworkID: extractField(`#\s*PIAZZA_NETWORK_ID:\s*(.+)`),
		Email:     extractField(`#\s*PIAZZA_EMAIL:\s*(.+)`),
		Password:  extractField(`#\s*PIAZZA_PASSWORD:\s*(.+)`),
	}

	// Check if we have the minimum required fields
	if config.NetworkID == "" || config.ClassName == "" || config.Professor == "" || config.Semester == "" {
		return nil, fmt.Errorf("missing required Piazza config fields")
	}

	return config, nil
}

// UpsertPiazzaConfig inserts or updates Piazza configuration in Cassandra
func UpsertPiazzaConfig(session *gocql.Session, config *PiazzaConfig) error {
	query := `INSERT INTO piazza_config (network_id, class_name, professor, semester, email, password)
	          VALUES (?, ?, ?, ?, ?, ?)`

	if err := session.Query(query,
		config.NetworkID,
		config.ClassName,
		config.Professor,
		config.Semester,
		config.Email,
		config.Password,
	).Exec(); err != nil {
		return fmt.Errorf("failed to upsert Piazza config: %w", err)
	}

	return nil
}

// DeletePiazzaConfig deletes Piazza configuration from Cassandra
func DeletePiazzaConfig(session *gocql.Session, networkID string) error {
	query := `DELETE FROM piazza_config WHERE network_id = ?`

	if err := session.Query(query, networkID).Exec(); err != nil {
		return fmt.Errorf("failed to delete Piazza config: %w", err)
	}

	return nil
}
