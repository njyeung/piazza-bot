package main

import (
	"fmt"
	"time"

	"github.com/gocql/gocql"
)

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

// FetchTranscript retrieves a single transcript from Cassandra
func FetchTranscript(session *gocql.Session, className, professor, semester string, limit int) (*Transcript, error) {
	query := `
		SELECT class_name, professor, semester, url, lecture_number, lecture_title, transcript_text
		FROM transcripts
		WHERE class_name = ? AND professor = ? AND semester = ?
		LIMIT ?
	`

	iter := session.Query(query, className, professor, semester, limit).Iter()
	defer iter.Close()

	var transcript Transcript
	if iter.Scan(&transcript.ClassName, &transcript.Professor, &transcript.Semester,
		&transcript.URL, &transcript.LectureNumber, &transcript.LectureTitle, &transcript.TranscriptText) {
		return &transcript, nil
	}

	if err := iter.Close(); err != nil {
		return nil, fmt.Errorf("error fetching transcript: %w", err)
	}

	return nil, fmt.Errorf("no transcript found")
}

// FetchFirstTranscript retrieves the first available transcript with non-null transcript_text
func FetchFirstTranscript(session *gocql.Session) (*Transcript, error) {
	query := `
		SELECT class_name, professor, semester, url, lecture_number, lecture_title, transcript_text
		FROM transcripts
		LIMIT 50
	`

	iter := session.Query(query).Iter()
	defer iter.Close()

	var transcript Transcript
	for iter.Scan(&transcript.ClassName, &transcript.Professor, &transcript.Semester,
		&transcript.URL, &transcript.LectureNumber, &transcript.LectureTitle, &transcript.TranscriptText) {
		// Skip if transcript_text is empty
		if transcript.TranscriptText != "" {
			return &transcript, nil
		}
		transcript = Transcript{} // Reset for next iteration
	}

	if err := iter.Close(); err != nil {
		return nil, fmt.Errorf("error fetching transcript: %w", err)
	}

	return nil, fmt.Errorf("no transcripts with text found")
}

// InsertEmbedding inserts a processed chunk into the embeddings table
func InsertEmbedding(session *gocql.Session, row *EmbeddingsRow) error {
	query := `
		INSERT INTO embeddings (
			class_name, professor, semester, url, chunk_index,
			chunk_text, embedding, token_count, lecture_title, lecture_timestamp, created_at
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`

	return session.Query(query,
		row.ClassName, row.Professor, row.Semester, row.URL, row.ChunkIndex,
		row.ChunkText, row.Embedding, row.TokenCount, row.LectureTitle, row.LectureTimestamp, time.Now(),
	).Exec()
}
