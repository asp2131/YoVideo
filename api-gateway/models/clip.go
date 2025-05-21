package models

import (
	"time"

	"github.com/google/uuid"
)

// Clip represents the structure of a video clip in the database.
type Clip struct {
	ID              uuid.UUID  `json:"id"`
	SourceVideoID   uuid.UUID  `json:"source_video_id"`
	ProjectID       *uuid.UUID `json:"project_id,omitempty"` // Nullable foreign key
	Title           string     `json:"title"`
	Description     *string    `json:"description,omitempty"`
	StoragePath     *string    `json:"storage_path,omitempty"`
	Duration        *int       `json:"duration,omitempty"`      // Nullable INTEGER
	StartTime       *float64   `json:"start_time,omitempty"`    // Nullable FLOAT
	EndTime         *float64   `json:"end_time,omitempty"`      // Nullable FLOAT
	AspectRatio     *string    `json:"aspect_ratio,omitempty"`
	ViralityScore   *float64   `json:"virality_score,omitempty"` // Nullable FLOAT
	Status          string     `json:"status"`
	ErrorMessage    *string    `json:"error_message,omitempty"`
	Width           *int       `json:"width,omitempty"`         // Nullable INTEGER
	Height          *int       `json:"height,omitempty"`        // Nullable INTEGER
	TemplateID      *uuid.UUID `json:"template_id,omitempty"`   // Nullable foreign key
	BRollEnabled    *bool      `json:"b_roll_enabled,omitempty"`
	CaptionsEnabled *bool      `json:"captions_enabled,omitempty"`
	DownloadURL     *string    `json:"download_url,omitempty"`
	CreatedAt       time.Time  `json:"created_at"`
	UpdatedAt       time.Time  `json:"updated_at"`
}
