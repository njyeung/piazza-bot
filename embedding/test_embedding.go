package main

import (
	"fmt"
	"log"
	"path/filepath"

	ort "github.com/ivansuteja96/go-onnxruntime"
	tokenizer "github.com/sugarme/tokenizer"
	"github.com/sugarme/tokenizer/pretrained"
)

func main() {
	// Load tokenizer
	fmt.Println("Loading tokenizer...")
	tokenizerPath := filepath.Join(".", "tokenizer.json")
	tok, err := pretrained.FromFile(tokenizerPath)
	if err != nil {
		log.Fatalf("Failed to load tokenizer: %v", err)
	}
	fmt.Println("✓ Tokenizer loaded successfully")

	// Initialize ONNX Runtime environment
	fmt.Println("Initializing ONNX Runtime...")
	env := ort.NewORTEnv(ort.ORT_LOGGING_LEVEL_WARNING, "gte-large")
	defer env.Close()
	fmt.Println("✓ ONNX Runtime environment initialized")

	// Create session options
	opts := ort.NewORTSessionOptions()
	defer opts.Close()

	// Load ONNX model
	fmt.Println("Loading ONNX model...")
	modelPath := filepath.Join(".", "model.onnx")
	session, err := ort.NewORTSession(env, modelPath, opts)
	if err != nil {
		log.Fatalf("Failed to load ONNX model: %v", err)
	}
	defer session.Close()
	fmt.Println("✓ ONNX model loaded successfully")

	// --- (Optional but VERY helpful) ---
	// In your real code, you can add a helper in the C wrapper to expose
	// input names / counts. For now we trust the gte-large export:
	// 3 inputs: input_ids, attention_mask, token_type_ids

	// Test tokenization
	fmt.Println("\nTesting tokenization...")
	testTexts := []string{
		"Hello world",
		"This is a test sentence",
	}

	inputs := make([]tokenizer.EncodeInput, len(testTexts))
	for i, t := range testTexts {
		inputs[i] = tokenizer.NewSingleEncodeInput(tokenizer.NewInputSequence(t))
	}

	encodings, err := tok.EncodeBatch(inputs, true)
	if err != nil {
		log.Fatalf("Tokenization failed: %v", err)
	}
	fmt.Printf("✓ Tokenized %d texts\n", len(encodings))

	// Find max sequence length
	maxLen := 0
	for _, enc := range encodings {
		if l := len(enc.GetIds()); l > maxLen {
			maxLen = l
		}
	}
	fmt.Printf("  Max sequence length: %d\n", maxLen)

	// Prepare input tensors
	fmt.Println("\nPreparing input tensors...")
	batchSize := len(encodings)

	ids := make([][]int64, batchSize)
	attn := make([][]int64, batchSize)

	// all zeros, not sure why we need this but will break if we remove it
	toks := make([][]int64, batchSize)

	for i, enc := range encodings {
		tid := enc.GetIds()
		am := enc.GetAttentionMask()

		paddedIds := make([]int64, maxLen)
		paddedAttn := make([]int64, maxLen)
		paddedTok := make([]int64, maxLen)

		for j, v := range tid {
			paddedIds[j] = int64(v)
		}
		for j, v := range am {
			paddedAttn[j] = int64(v)
		}
		// paddedTok stays zeros

		ids[i] = paddedIds
		attn[i] = paddedAttn
		toks[i] = paddedTok
	}
	fmt.Println("✓ Input tensors prepared")

	// Flatten and run inference
	fmt.Println("\nRunning ONNX inference...")
	idsFlat := flatten2D(ids)
	attnFlat := flatten2D(attn)
	toksFlat := flatten2D(toks)

	inputs2 := []ort.TensorValue{
		{
			Value: idsFlat,
			Shape: []int64{int64(batchSize), int64(maxLen)},
		},
		{
			Value: attnFlat,
			Shape: []int64{int64(batchSize), int64(maxLen)},
		},
		{
			Value: toksFlat,
			Shape: []int64{int64(batchSize), int64(maxLen)},
		},
	}

	outputs, err := session.Predict(inputs2)
	if err != nil {
		log.Fatalf("Inference failed: %v", err)
	}
	fmt.Println("✓ Inference completed successfully")

	if len(outputs) == 0 {
		log.Fatalf("No outputs from model")
	}

	out := outputs[0]
	fmt.Printf("Output shape: %v\n", out.Shape)

	// Extract embeddings
	fmt.Println("\nExtracting embeddings...")
	raw, ok := out.Value.([]float32)
	if !ok {
		if raw64, ok := out.Value.([]float64); ok {
			raw = make([]float32, len(raw64))
			for i, v := range raw64 {
				raw[i] = float32(v)
			}
		} else {
			log.Fatalf("Unexpected output type: %T", out.Value)
		}
	}

	// Handle both [batch, hidden] and [batch, seq_len, hidden]
	vecCount := int(out.Shape[0])
	vecDim := 1
	for i := 1; i < len(out.Shape); i++ {
		vecDim *= int(out.Shape[i])
	}

	if len(raw) != vecCount*vecDim {
		log.Fatalf("Output size mismatch: len(raw)=%d, expected=%d", len(raw), vecCount*vecDim)
	}

	fmt.Printf("✓ Output vectors: %d, flattened dim per item: %d\n", vecCount, vecDim)

	fmt.Println("\nSample embeddings (first 10 values of first item):")
	if vecCount > 0 {
		first := raw[:vecDim]
		for j := 0; j < 10 && j < len(first); j++ {
			fmt.Printf("%.4f ", first[j])
		}
		fmt.Println("...")
	}

	fmt.Println("\n✅ All tests passed!")
}

func flatten2D(arr [][]int64) []int64 {
	if len(arr) == 0 {
		return []int64{}
	}
	flat := make([]int64, 0, len(arr)*len(arr[0]))
	for _, row := range arr {
		flat = append(flat, row...)
	}
	return flat
}
