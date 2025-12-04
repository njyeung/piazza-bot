package main

import (
	"strings"
)

// ParseSRT parses SRT transcript text and returns array of Frames.
func ParseSRT(transcriptText string) []Frame {
	//	1									sequence number
	//	00:00:00,000 --> 00:00:01,830		start --> end
	//	I'm happy to						line
	//	have you here today.				line
	//
	//	2
	//	00:00:01,910 --> 00:00:03,610
	//	As I'm sure you're all
	//	aware, there's going

	if transcriptText == "" {
		return []Frame{}
	}

	lines := strings.Split(transcriptText, "\n")
	var frames []Frame
	var currentStartTime string
	var currentEndTime string

	for _, line := range lines {
		line = strings.TrimSpace(line)

		// Skip empty lines
		if line == "" {
			continue
		}

		// Skip sequence numbers
		if isDigitOnly(line) {
			continue
		}

		// timestamp line (start --> end)
		// HH:MM:SS,mmm --> HH:MM:SS,mmm
		if strings.Contains(line, "-->") {
			parts := strings.Split(line, "-->")
			if len(parts) == 2 {
				currentStartTime = strings.TrimSpace(parts[0])
				currentEndTime = strings.TrimSpace(parts[1])
			}
			continue
		}

		// Create frame
		frames = append(frames, Frame{
			Text:      line,
			StartTime: currentStartTime,
			EndTime:   currentEndTime,
		})
	}

	return frames
}

// Merges frames into sentences based on sentence boundaries
// A sentence is text ending with . or ? or !
func ExtractSentencesFromFrames(frames []Frame) []Sentence {
	if len(frames) == 0 {
		return []Sentence{}
	}

	// Merge all frame text together, keeping track of where each starts
	var sentences []Sentence

	var currentSentenceText strings.Builder
	var currentStartTime string
	var isFirstFrame = true

	for _, frame := range frames {
		// Set start time for first frame of this sentence
		if isFirstFrame {
			currentStartTime = frame.StartTime
			isFirstFrame = false
		}

		// Add frame text
		if currentSentenceText.Len() > 0 {
			currentSentenceText.WriteString(" ")
		}
		currentSentenceText.WriteString(frame.Text)

		// Check if this frame ends with . or ? or !
		trimmed := strings.TrimSpace(frame.Text)
		if strings.HasSuffix(trimmed, ".") || strings.HasSuffix(trimmed, "!") || strings.HasSuffix(trimmed, "?") {
			sentenceText := currentSentenceText.String()

			sentences = append(sentences, Sentence{
				Text:       sentenceText,
				StartTime:  currentStartTime,
				Embedding:  nil, // Will be populated by embedding function
				TokenCount: CountTokens(sentenceText),
			})

			currentSentenceText.Reset()
			isFirstFrame = true
		}
	}

	// Add any remaining text as a sentence
	if currentSentenceText.Len() > 0 {
		sentenceText := currentSentenceText.String()
		sentences = append(sentences, Sentence{
			Text:       sentenceText,
			StartTime:  currentStartTime,
			Embedding:  nil,
			TokenCount: CountTokens(sentenceText),
		})
	}

	return sentences
}

// Replaces the averaged chunk embeddings with accurate embeddings
// by running each chunk's text through the embedding model one last time
func FinalizeChunkEmbeddings(chunks []Chunk, embeddingModel *EmbeddingModel) error {
	if len(chunks) == 0 {
		return nil
	}

	// Extract chunk texts
	chunkTexts := make([]string, len(chunks))
	for i, chunk := range chunks {
		chunkTexts[i] = chunk.Text
	}

	// embed with model
	embeddings, err := embeddingModel.EmbedSentences(chunkTexts)
	if err != nil {
		return err
	}

	// update chunk embedding
	for i, embedding := range embeddings {
		chunks[i].Embedding = embedding
	}

	return nil
}

// checks if a string contains only digits
func isDigitOnly(s string) bool {
	for _, r := range s {
		if r < '0' || r > '9' {
			return false
		}
	}
	return len(s) > 0
}
