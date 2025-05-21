package handlers

import (
	"encoding/json"
	"fmt"
	"log"
	"time"

	"github.com/gofiber/fiber/v2"
	"videothingy/api-gateway/config"
	"videothingy/api-gateway/models"
)

// CreateProject handles the creation of a new project.
func CreateProject(c *fiber.Ctx) error {
	log.Println("Received request to create a new project")

	project := new(models.Project)

	if err := c.BodyParser(project); err != nil {
		log.Printf("Error parsing project data: %v", err)
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Cannot parse project JSON: %v", err),
		})
	}

	project.CreatedAt = time.Now()
	project.UpdatedAt = time.Now()

	// Create a map of the data to insert, excluding the ID field
	// so the database can generate it.
	projectDataToInsert := map[string]interface{}{
		"name":        project.Name,
		"created_at":  project.CreatedAt,
		"updated_at":  project.UpdatedAt,
	}
	if project.Description != nil {
		projectDataToInsert["description"] = *project.Description
	}
	if project.ThumbnailURL != nil { // Though not sent in curl, good to include if model supports
		projectDataToInsert["thumbnail_url"] = *project.ThumbnailURL
	}

	var results []models.Project

	// Corrected Supabase Insert and Execute call chain
	// Insert(data, upsert, onConflict, returning, count)
	// Execute() returns (body []byte, count int64, error)
	body, _, err := config.SupabaseClient.From("projects").
		Insert(projectDataToInsert, false, "", "representation", "").
		Execute()

	if err != nil {
		log.Printf("Error executing Supabase insert: %v", err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Could not create project (execute phase): %v", err),
		})
	}

	// Unmarshal the response body into the results slice
	if err := json.Unmarshal(body, &results); err != nil {
		log.Printf("Error unmarshalling Supabase response: %v", err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Could not process project creation response: %v", err),
		})
	}

	if len(results) == 0 {
		log.Println("Error: Project data unmarshalled into an empty slice")
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": "Failed to create project, unmarshalled data is empty.",
		})
	}

	log.Printf("Project created successfully: %+v", results[0])
	return c.Status(fiber.StatusCreated).JSON(fiber.Map{
		"status":  "success",
		"message": "Project created successfully",
		"data":    results[0],
	})
}

// GetProjects handles listing all projects.
func GetProjects(c *fiber.Ctx) error {
	log.Println("Received request to list projects")

	var projects []models.Project

	// Select all columns from the projects table
	// Execute() returns (body []byte, count int64, error)
	body, _, err := config.SupabaseClient.From("projects").Select("*", "", false).Execute()
	if err != nil {
		log.Printf("Error fetching projects from Supabase: %v", err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Could not retrieve projects: %v", err),
		})
	}

	// Unmarshal the response body into the projects slice
	if err := json.Unmarshal(body, &projects); err != nil {
		log.Printf("Error unmarshalling projects data: %v", err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Could not process projects list: %v", err),
		})
	}

	log.Printf("Successfully retrieved %d projects", len(projects))
	return c.Status(fiber.StatusOK).JSON(fiber.Map{
		"status":  "success",
		"message": "Projects retrieved successfully",
		"data":    projects,
	})
}

// GetProject handles retrieving a specific project by its ID.
func GetProject(c *fiber.Ctx) error {
	projectID := c.Params("id")
	log.Printf("Received request to get project with ID: %s", projectID)

	var project []models.Project // Expecting a slice, even for one item with Supabase client

	// Select from projects where id equals projectID
	body, _, err := config.SupabaseClient.From("projects").
		Select("*", "", false).
		Eq("id", projectID).
		Execute()

	if err != nil {
		log.Printf("Error fetching project %s from Supabase: %v", projectID, err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Could not retrieve project %s: %v", projectID, err),
		})
	}

	if err := json.Unmarshal(body, &project); err != nil {
		log.Printf("Error unmarshalling project data for ID %s: %v", projectID, err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Could not process project data for ID %s: %v", projectID, err),
		})
	}

	if len(project) == 0 {
		log.Printf("Project with ID %s not found", projectID)
		return c.Status(fiber.StatusNotFound).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Project with ID %s not found", projectID),
		})
	}

	log.Printf("Successfully retrieved project with ID %s", projectID)
	return c.Status(fiber.StatusOK).JSON(fiber.Map{
		"status":  "success",
		"message": "Project retrieved successfully",
		"data":    project[0], // Return the first (and only) project in the slice
	})
}

// DeleteProject handles deleting a specific project by its ID.
func DeleteProject(c *fiber.Ctx) error {
	projectID := c.Params("id")
	log.Printf("Received request to delete project with ID: %s", projectID)

	// Execute() for delete typically returns (body []byte, count int64, error)
	// We're interested in the count to see if a row was affected.
	// However, count might be 0 even on successful deletion if not explicitly requested.
	// So, we'll primarily rely on the absence of an error.
	_, _, err := config.SupabaseClient.From("projects").
		Delete("", ""). // First arg: returning (e.g. "minimal", "representation"), Second: count (e.g. "exact")
		Eq("id", projectID).
		Execute()

	if err != nil {
		log.Printf("Error deleting project %s from Supabase: %v", projectID, err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Could not delete project %s: %v", projectID, err),
		})
	}

	// If err is nil, the delete operation was accepted by the database.
	// This doesn't strictly confirm a row was deleted (it might not have existed),
	// but for a DELETE operation, this is usually considered a success.
	// A more robust check would involve trying to GET the project first, then deleting if it exists,
	// or using a 'returning' option with Delete if the client supports it to confirm deletion.
	// For now, no error means we proceed as if successful.

	log.Printf("Delete operation for project ID %s processed by database.", projectID)
	return c.Status(fiber.StatusOK).JSON(fiber.Map{
		"status":  "success",
		"message": fmt.Sprintf("Project with ID %s delete request processed", projectID),
	})
}

// UpdateProject handles partially updating an existing project by its ID.
func UpdateProject(c *fiber.Ctx) error {
	projectID := c.Params("id")
	log.Printf("Received request to update project with ID: %s", projectID)

	var payload map[string]interface{}
	if err := c.BodyParser(&payload); err != nil {
		log.Printf("Error parsing update payload for project %s: %v", projectID, err)
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Invalid request body: %v", err),
		})
	}

	dbUpdateData := make(map[string]interface{})

	// Validate and add fields to dbUpdateData
	if val, ok := payload["name"]; ok {
		if nameStr, typeOK := val.(string); typeOK {
			dbUpdateData["name"] = nameStr
		} else {
			return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"status": "error", "message": "'name' field must be a string"})
		}
	}

	if val, exists := payload["description"]; exists {
		if val == nil {
			dbUpdateData["description"] = nil
		} else if descStr, typeOK := val.(string); typeOK {
			dbUpdateData["description"] = descStr
		} else {
			return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"status": "error", "message": "'description' field must be a string or null"})
		}
	}

	if val, exists := payload["thumbnail_url"]; exists {
		if val == nil {
			dbUpdateData["thumbnail_url"] = nil
		} else if thumbStr, typeOK := val.(string); typeOK {
			dbUpdateData["thumbnail_url"] = thumbStr
		} else {
			return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"status": "error", "message": "'thumbnail_url' field must be a string or null"})
		}
	}

	if len(dbUpdateData) == 0 {
		// No updatable fields provided, but we should at least touch updated_at or return a specific response.
		// For now, let's consider it a request to touch updated_at.
		log.Printf("No specific fields to update for project %s, will only update 'updated_at'", projectID)
	}

	dbUpdateData["updated_at"] = time.Now()

	var results []models.Project

	body, _, err := config.SupabaseClient.From("projects").
		Update(dbUpdateData, "representation", "").
		Eq("id", projectID).
		Execute()

	if err != nil {
		log.Printf("Error updating project %s in Supabase: %v", projectID, err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Could not update project %s: %v", projectID, err),
		})
	}

	if err := json.Unmarshal(body, &results); err != nil {
		log.Printf("Error unmarshalling updated project data for ID %s: %v", projectID, err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Could not process project update response for ID %s: %v", projectID, err),
		})
	}

	if len(results) == 0 {
		log.Printf("Project with ID %s not found for update", projectID)
		return c.Status(fiber.StatusNotFound).JSON(fiber.Map{
			"status":  "error",
			"message": fmt.Sprintf("Project with ID %s not found", projectID),
		})
	}

	log.Printf("Successfully updated project with ID %s", projectID)
	return c.Status(fiber.StatusOK).JSON(fiber.Map{
		"status":  "success",
		"message": "Project updated successfully",
		"data":    results[0],
	})
}
