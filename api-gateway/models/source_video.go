package models

import (
	"encoding/json"
	"time"

	"github.com/google/uuid"
)

// SourceVideo represents the structure of a source video in the database.
type SourceVideo struct {
	ID                  uuid.UUID       `json:"id"`
	ProjectID           *uuid.UUID      `json:"project_id,omitempty"` // Nullable foreign key
	Title               string          `json:"title"`
	Description         *string         `json:"description,omitempty"`
	StoragePath         string          `json:"storage_path"`
	Duration            *int            `json:"duration,omitempty"`         // Nullable INTEGER
	FileSize            *int64          `json:"file_size,omitempty"`        // Nullable BIGINT
	Width               *int            `json:"width,omitempty"`            // Nullable INTEGER
	Height              *int            `json:"height,omitempty"`           // Nullable INTEGER
	Format              *string         `json:"format,omitempty"`
	Status              string          `json:"status"`
	ErrorMessage        *string         `json:"error_message,omitempty"`
	TranscriptionStatus *string         `json:"transcription_status,omitempty"`
	Transcription       json.RawMessage `json:"transcription,omitempty"`    // Nullable JSONB
	HighlightMarkers    json.RawMessage `json:"highlight_markers,omitempty"` // Nullable JSONB
	Metadata            json.RawMessage `json:"metadata,omitempty"`          // Nullable JSONB
	CreatedAt           time.Time       `json:"created_at"`
	UpdatedAt           time.Time       `json:"updated_at"`
}
