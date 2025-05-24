package models

// TranscriptionData represents the structure of transcription data.
type TranscriptionData struct {
	Text     string              `json:"text"`
	Segments []TranscriptSegment `json:"segments"`
}

// TranscriptSegment represents a single segment of a transcription.
type TranscriptSegment struct {
	Text      string  `json:"text"`
	StartTime float64 `json:"start_time"`
	EndTime   float64 `json:"end_time"`
}

// HighlightData represents the structure of highlight data.
type HighlightData struct {
	Highlights []Highlight `json:"highlights"`
}

// Highlight represents a single highlight segment.
type Highlight struct {
	Text      string  `json:"text"`
	StartTime float64 `json:"start_time"`
	EndTime   float64 `json:"end_time"`
	Score     float32 `json:"score"`
}
