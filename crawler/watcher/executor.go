package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"log"
	"os/exec"
	"path/filepath"
)

// LectureInfo represents a lecture parsed from a Python parser
type LectureInfo struct {
	ClassName    string `json:"class_name"`
	Professor    string `json:"professor"`
	Semester     string `json:"semester"`
	URL          string `json:"url"`
	LectureTitle string `json:"lecture_title"`
}

// ExecuteParser runs a Python parser and returns the lecture info it outputs
func ExecuteParser(parserName, parsersDir string) ([]LectureInfo, error) {
	parserPath := filepath.Join(parsersDir, parserName+".py")

	log.Printf("  Executing %s...", parserName)

	// Run the Python script
	cmd := exec.Command("python3", parserPath)

	// Capture stdout
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return nil, fmt.Errorf("failed to create stdout pipe: %w", err)
	}

	// Start the command
	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("failed to start parser: %w", err)
	}

	// Read JSON lines from stdout
	var lectures []LectureInfo
	scanner := bufio.NewScanner(stdout)
	for scanner.Scan() {
		line := scanner.Text()
		if line != "" {
			var lecture LectureInfo
			if err := json.Unmarshal([]byte(line), &lecture); err != nil {
				log.Printf("    Warning: failed to parse JSON: %s", line)
				continue
			}
			lectures = append(lectures, lecture)
			log.Printf("    Found: %s - %s", lecture.LectureTitle, lecture.URL)
		}
	}

	if err := scanner.Err(); err != nil {
		return nil, fmt.Errorf("error reading parser output: %w", err)
	}

	// Wait for the command to finish
	if err := cmd.Wait(); err != nil {
		return nil, fmt.Errorf("parser execution failed: %w", err)
	}

	log.Printf("  Completed %s - found %d lecture(s)", parserName, len(lectures))
	return lectures, nil
}
