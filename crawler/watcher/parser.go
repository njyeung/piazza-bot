package main

import (
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"
)

// WriteParsersToDisk writes parser code to the parsers directory
func WriteParsersToDisk(parsers []Parser, parsersDir string) error {
	// Create parsers directory if it doesn't exist
	if err := os.MkdirAll(parsersDir, 0755); err != nil {
		return fmt.Errorf("failed to create parsers directory: %w", err)
	}

	for _, parser := range parsers {
		filename := filepath.Join(parsersDir, parser.ParserName+".py")

		if err := os.WriteFile(filename, []byte(parser.CodeText), 0644); err != nil {
			log.Printf("Error writing parser %s: %v", parser.ParserName, err)
			continue
		}

		log.Printf("  Wrote %s", filename)
	}

	return nil
}

// CleanupDeletedParsers removes parser files that are no longer in Cassandra
func CleanupDeletedParsers(parsers []Parser, parsersDir string) error {
	// Build a set of valid parser names from Cassandra
	validParsers := make(map[string]bool)
	for _, parser := range parsers {
		validParsers[parser.ParserName] = true
	}

	// Read all .py files in parsers directory
	entries, err := os.ReadDir(parsersDir)
	if err != nil {
		// If directory doesn't exist, nothing to clean up
		if os.IsNotExist(err) {
			return nil
		}
		return fmt.Errorf("failed to read parsers directory: %w", err)
	}

	// Check each .py file
	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}

		filename := entry.Name()
		if !strings.HasSuffix(filename, ".py") {
			continue
		}

		// Extract parser name (remove .py extension)
		parserName := strings.TrimSuffix(filename, ".py")

		// If this parser is not in Cassandra, delete it
		if !validParsers[parserName] {
			filePath := filepath.Join(parsersDir, filename)
			if err := os.Remove(filePath); err != nil {
				log.Printf("Error deleting parser %s: %v", filename, err)
			} else {
				log.Printf("  Deleted %s (no longer in Cassandra)", filename)
			}
		}
	}

	return nil
}
