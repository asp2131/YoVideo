package utils

import (
	"fmt"
	"strings"

	"github.com/go-playground/validator/v10"
	"github.com/gofiber/fiber/v2"
)

// RespondWithError sends a JSON error response.
func RespondWithError(c *fiber.Ctx, statusCode int, message string) error {
	return c.Status(statusCode).JSON(fiber.Map{
		"status":  "error",
		"message": message,
	})
}

// RespondWithJSON sends a JSON success response.
func RespondWithJSON(c *fiber.Ctx, statusCode int, data interface{}) error {
	return c.Status(statusCode).JSON(fiber.Map{
		"status": "success",
		"data":   data,
	})
}

// FormatValidationErrors formats validation errors from validator/v10.
func FormatValidationErrors(err error) []string {
	var errors []string
	if err != nil {
		for _, err := range err.(validator.ValidationErrors) {
			var element string
			element = fmt.Sprintf("Field '%s' failed on the '%s' tag", err.Field(), err.Tag())
			if err.Param() != "" {
				element = fmt.Sprintf("%s (value: %s)", element, err.Param())
			}
			errors = append(errors, element)
		}
	}
	return errors
}

// SanitizeInput is a placeholder for a potential input sanitization function.
// For now, it just returns the input string.
func SanitizeInput(input string) string {
	// Basic sanitization: trim whitespace
	// More advanced sanitization (e.g., against XSS) would go here if needed.
	return strings.TrimSpace(input)
}
