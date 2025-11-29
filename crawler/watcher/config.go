package main

import (
	"os"
	"strings"
	"time"
)

// Config holds configuration from environment variables
type Config struct {
	CassandraHosts    []string
	CassandraKeyspace string
	PollInterval      time.Duration
	ParsersDir        string
	RedisHost         string
	RedisPort         string
	RedisQueue        string
	RedisSeenSet      string
}

// LoadConfig loads configuration from environment variables
func LoadConfig() *Config {
	hostsEnv := os.Getenv("CASSANDRA_HOSTS")
	if hostsEnv == "" {
		hostsEnv = "cassandra-1"
	}

	// Split comma-separated hosts
	hosts := strings.Split(hostsEnv, ",")

	keyspace := os.Getenv("CASSANDRA_KEYSPACE")
	if keyspace == "" {
		keyspace = "transcript_db"
	}

	pollInterval := 60 * time.Second

	parsersDir := "./parsers"

	redisHost := os.Getenv("REDIS_HOST")
	if redisHost == "" {
		redisHost = "localhost"
	}

	redisPort := os.Getenv("REDIS_PORT")
	if redisPort == "" {
		redisPort = "6379"
	}

	redisQueue := os.Getenv("REDIS_QUEUE")
	if redisQueue == "" {
		redisQueue = "frontier"
	}

	redisSeenSet := os.Getenv("REDIS_SEEN_SET")
	if redisSeenSet == "" {
		redisSeenSet = "seen"
	}

	return &Config{
		CassandraHosts:    hosts,
		CassandraKeyspace: keyspace,
		PollInterval:      pollInterval,
		ParsersDir:        parsersDir,
		RedisHost:         redisHost,
		RedisPort:         redisPort,
		RedisQueue:        redisQueue,
		RedisSeenSet:      redisSeenSet,
	}
}
