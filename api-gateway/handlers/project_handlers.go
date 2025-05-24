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

// CreateProjectRequest defines the expected request body for creating a project.
// Name is required. Description and ThumbnailURL are optional.
type CreateProjectRequest struct {
	Name         string  `json:"name" validate:"required"`
	Description  *string `json:"description,omitempty"`
	ThumbnailURL *string `json:"thumbnail_url,omitempty"`
}

// ProjectSuccessResponse defines the structure for a successful response for a single project.
type ProjectSuccessResponse struct {
	Status  string         `json:"status"`
	Message string         `json:"message"`
	Data    models.Project `json:"data"`
}

// ProjectListSuccessResponse defines the structure for a successful response when listing projects.
// It includes the standard status and message fields, and a data field containing a slice of projects.
type ProjectListSuccessResponse struct {
	Status  string           `json:"status"`
	Message string           `json:"message"`
	Data    []models.Project `json:"data"`
}

// ErrorResponse defines a common structure for error responses.
type ErrorResponse struct {
	Status  string `json:"status"`
	Message string `json:"message"`
}

// CreateProject godoc
// @Summary Create a new project
// @Description Creates a new project with the provided name and optional description and thumbnail URL.
// @Tags projects
// @Accept  json
// @Produce  json
// @Param   project body CreateProjectRequest true "Project to create"
// @Success 201 {object} ProjectSuccessResponse "Project created successfully"
// @Failure 400 {object} ErrorResponse "Bad request if input is invalid (e.g., missing name)"
// @Failure 500 {object} ErrorResponse "Internal server error if project creation fails"
// @Router /projects [post]
func CreateProject(c *fiber.Ctx) error {
	log.Println("Received request to create a new project")

	projectReq := new(CreateProjectRequest)

	if err := c.BodyParser(projectReq); err != nil {
		log.Printf("Error parsing project data: %v", err)
		return c.Status(fiber.StatusBadRequest).JSON(ErrorResponse{
			Status:  "error",
			Message: fmt.Sprintf("Cannot parse project JSON: %v", err),
		})
	}

	// TODO: Add validation for projectReq using validator package if needed, e.g., projectReq.Name is required.
	// For now, assuming Name will be present as per `validate:"required"` if validator is globally applied.

	projectToInsert := models.Project{
		Name:         projectReq.Name,
		Description:  projectReq.Description,
		ThumbnailURL: projectReq.ThumbnailURL,
		CreatedAt:    time.Now(),
		UpdatedAt:    time.Now(),
	}

	// Create a map of the data to insert, excluding the ID field
	// so the database can generate it.
	projectDataToInsert := map[string]interface{}{
		"name":        projectToInsert.Name,
		"created_at":  projectToInsert.CreatedAt,
		"updated_at":  projectToInsert.UpdatedAt,
	}
	if projectToInsert.Description != nil {
		projectDataToInsert["description"] = *projectToInsert.Description
	}
	if projectToInsert.ThumbnailURL != nil {
		projectDataToInsert["thumbnail_url"] = *projectToInsert.ThumbnailURL
	}

	var results []models.Project

	body, _, err := config.SupabaseClient.From("projects").
		Insert(projectDataToInsert, false, "", "representation", "").
		Execute()

	if err != nil {
		log.Printf("Error executing Supabase insert: %v", err)
		return c.Status(fiber.StatusInternalServerError).JSON(ErrorResponse{
			Status:  "error",
			Message: fmt.Sprintf("Could not create project (execute phase): %v", err),
		})
	}

	if err := json.Unmarshal(body, &results); err != nil {
		log.Printf("Error unmarshalling Supabase response: %v", err)
		return c.Status(fiber.StatusInternalServerError).JSON(ErrorResponse{
			Status:  "error",
			Message: fmt.Sprintf("Could not process project creation response: %v", err),
		})
	}

	if len(results) == 0 {
		log.Println("Error: Project data unmarshalled into an empty slice")
		return c.Status(fiber.StatusInternalServerError).JSON(ErrorResponse{
			Status:  "error",
			Message: "Failed to create project, unmarshalled data is empty.",
		})
	}

	log.Printf("Project created successfully: %+v", results[0])
	return c.Status(fiber.StatusCreated).JSON(ProjectSuccessResponse{
		Status:  "success",
		Message: "Project created successfully",
		Data:    results[0],
	})
}

// GetProjects godoc
// @Summary List all projects
// @Description Retrieves a list of all projects from the database.
// @Tags projects
// @Accept  json
// @Produce  json
// @Success 200 {object} ProjectListSuccessResponse "Successfully retrieved list of projects"
// @Failure 500 {object} ErrorResponse "Internal server error if projects cannot be retrieved"
// @Router /projects [get]
func GetProjects(c *fiber.Ctx) error {
	log.Println("Received request to list projects")

	var projects []models.Project

	// Use the Supabase client with the service key
	supabaseClient := config.GetSupabaseClient()
	
	// Select all columns from the projects table
	// Execute() returns (body []byte, count int64, error)
	body, _, err := supabaseClient.From("projects").Select("*", "", false).Execute()
	if err != nil {
		log.Printf("Error fetching projects from Supabase: %v", err)
		return c.Status(fiber.StatusInternalServerError).JSON(ErrorResponse{
			Status:  "error",
			Message: fmt.Sprintf("Could not retrieve projects: %v", err),
		})
	}

	// Unmarshal the response body into the projects slice
	if err := json.Unmarshal(body, &projects); err != nil {
		log.Printf("Error unmarshalling projects data: %v", err)
		return c.Status(fiber.StatusInternalServerError).JSON(ErrorResponse{
			Status:  "error",
			Message: fmt.Sprintf("Could not process projects data: %v", err),
		})
	}

	log.Printf("Successfully fetched %d projects", len(projects))
	return c.Status(fiber.StatusOK).JSON(ProjectListSuccessResponse{
		Status:  "success",
		Message: "Projects retrieved successfully",
		Data:    projects,
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
