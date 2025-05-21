package models

import (
	"time"

	"github.com/google/uuid"
)

// BRoll represents the structure of a B-roll clip in the database.
type BRoll struct {
	ID          uuid.UUID `json:"id"`
	ClipID      uuid.UUID `json:"clip_id"`
	StartTime   float64   `json:"start_time"`
	EndTime     float64   `json:"end_time"`
	StoragePath string    `json:"storage_path"`
	SourceType  string    `json:"source_type"`
	Keyword     *string   `json:"keyword,omitempty"`   // Nullable TEXT
	IsActive    *bool     `json:"is_active,omitempty"` // Nullable BOOLEAN
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
}
