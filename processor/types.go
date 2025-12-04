package main

// Frame: a single line from the SRT transcript
type Frame struct {
	Text      string
	StartTime string // HH:MM:SS.mmm format
	EndTime   string
}

// Sentence: a single complete sentence
type Sentence struct {
	Text       string
	StartTime  string // From first frame that contributed to this sentence
	Embedding  []float32
	TokenCount int
}

// Chunk: semantically grouped sentences, formed by merging sentences based on embedding similarity
type Chunk struct {
	Text               string
	StartTime          string
	Embedding          []float32
	NumSentences       int
	TokenCount         int
	ChunkIndex         int
	SentenceEmbeddings [][]float32 // Individual sentence embeddings
}

// Transcript holds metadata about a lecture transcript
type Transcript struct {
	ClassName      string
	Professor      string
	Semester       string
	URL            string
	LectureTitle   string
	LectureNumber  int
	TranscriptText string
}

// EmbeddingsRow: a row to insert into the embeddings table
type EmbeddingsRow struct {
	ClassName        string
	Professor        string
	Semester         string
	URL              string
	ChunkIndex       int
	ChunkText        string
	Embedding        []float32
	TokenCount       int
	LectureTitle     string
	LectureTimestamp string
}
