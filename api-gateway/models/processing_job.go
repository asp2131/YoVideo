package models

import (
	"encoding/json"
	"time"

	"github.com/google/uuid"
)

// ProcessingJob represents the structure of a processing job in the database.
type ProcessingJob struct {
	ID            uuid.UUID       `json:"id"`
	JobType       string          `json:"job_type"`
	EntityID      uuid.UUID       `json:"entity_id"`
	EntityType    string          `json:"entity_type"`
	Status        string          `json:"status"`
	Progress      *float64        `json:"progress,omitempty"`       // Nullable FLOAT
	ErrorMessage  *string         `json:"error_message,omitempty"`  // Nullable TEXT
	Metadata      json.RawMessage `json:"metadata,omitempty"`        // Nullable JSONB
	CreatedAt     time.Time       `json:"created_at"`
	UpdatedAt     time.Time       `json:"updated_at"`
	StartedAt     *time.Time      `json:"started_at,omitempty"`     // Nullable TIMESTAMPTZ
	CompletedAt   *time.Time      `json:"completed_at,omitempty"`   // Nullable TIMESTAMPTZ
}
