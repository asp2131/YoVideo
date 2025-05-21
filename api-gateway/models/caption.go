package models

import (
	"time"

	"github.com/google/uuid"
)

// Caption represents the structure of a caption for a clip in the database.
type Caption struct {
	ID         uuid.UUID `json:"id"`
	ClipID     uuid.UUID `json:"clip_id"`
	StartTime  float64   `json:"start_time"`
	EndTime    float64   `json:"end_time"`
	Text       string    `json:"text"`
	Speaker    *string   `json:"speaker,omitempty"`    // Nullable TEXT
	IsEdited   *bool     `json:"is_edited,omitempty"`  // Nullable BOOLEAN
	CreatedAt  time.Time `json:"created_at"`
	UpdatedAt  time.Time `json:"updated_at"`
}
