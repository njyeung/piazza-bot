package main

import (
	"regexp"
	"strings"
)

// ParseSRT parses SRT transcript text and returns array of Frames.
func ParseSRT(transcriptText string) []Frame {
	//	1
	//	00:00:00,000 --> 00:00:01,830
	//	I'm happy to
	//	have you here today.
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

// isDigitOnly checks if a string contains only digits
func isDigitOnly(s string) bool {
	for _, r := range s {
		if r < '0' || r > '9' {
			return false
		}
	}
	return len(s) > 0
}

// ExtractSentencesFromFrames merges frames into sentences based on sentence boundaries
// A sentence is text ending with . or ?
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

		// Check if this frame ends with . or ?
		trimmed := strings.TrimSpace(frame.Text)
		if strings.HasSuffix(trimmed, ".") || strings.HasSuffix(trimmed, "!") || strings.HasSuffix(trimmed, "?") {
			// Complete sentence found
			sentences = append(sentences, Sentence{
				Text:       currentSentenceText.String(),
				StartTime:  currentStartTime,
				Embedding:  nil, // Will be populated by embedding function
				TokenCount: 0,   // Will be populated by tokenizer
			})

			currentSentenceText.Reset()
			isFirstFrame = true
		}
	}

	// Add any remaining text as a sentence
	if currentSentenceText.Len() > 0 {
		sentences = append(sentences, Sentence{
			Text:       currentSentenceText.String(),
			StartTime:  currentStartTime,
			Embedding:  nil,
			TokenCount: 0,
		})
	}

	return sentences
}

// CleanSRTText removes SRT formatting (timestamps, sequence numbers) but keeps text
// Returns plain text suitable for processing
func CleanSRTText(transcriptText string) string {
	lines := strings.Split(transcriptText, "\n")
	var cleanedLines []string

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

		// Skip timestamp lines
		if strings.Contains(line, "-->") {
			continue
		}

		// Keep text
		cleanedLines = append(cleanedLines, line)
	}

	text := strings.Join(cleanedLines, " ")
	// Clean up multiple spaces
	re := regexp.MustCompile(`\s+`)
	text = re.ReplaceAllString(text, " ")

	return strings.TrimSpace(text)
}
