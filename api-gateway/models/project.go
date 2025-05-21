package models

import (
	"time"

	"github.com/google/uuid"
)

// Project represents the structure of a project in the database.
type Project struct {
	ID           uuid.UUID `json:"id,omitempty"`
	Name         string    `json:"name"`
	Description  *string   `json:"description,omitempty"`      // Use a pointer for nullable TEXT fields
	ThumbnailURL *string   `json:"thumbnail_url,omitempty"`    // Use a pointer for nullable TEXT fields
	CreatedAt    time.Time `json:"created_at"`
	UpdatedAt    time.Time `json:"updated_at"`
}
