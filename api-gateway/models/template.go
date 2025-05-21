package models

import (
	"encoding/json"
	"time"

	"github.com/google/uuid"
)

// Template represents the structure of a template in the database.
type Template struct {
	ID               uuid.UUID       `json:"id"`
	Name             string          `json:"name"`
	Description      *string         `json:"description,omitempty"`
	IsSystemTemplate bool            `json:"is_system_template"`
	PreviewURL       *string         `json:"preview_url,omitempty"`
	Settings         json.RawMessage `json:"settings"` // For JSONB type
	CreatedAt        time.Time       `json:"created_at"`
	UpdatedAt        time.Time       `json:"updated_at"`
}
