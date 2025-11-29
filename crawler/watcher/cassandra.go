package main

import (
	"fmt"
	"time"

	"github.com/gocql/gocql"
)

// Parser represents a parser record from Cassandra
type Parser struct {
	ParserName string
	CodeText   string
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
