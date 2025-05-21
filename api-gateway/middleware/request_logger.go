package middleware

import (
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/google/uuid"
	"videothingy/api-gateway/config" // To use our configured logrus instance
)

// RequestLogger creates a new middleware handler for structured request logging with Logrus.
func RequestLogger() fiber.Handler {
	return func(c *fiber.Ctx) error {
		start := time.Now()
		requestID := uuid.NewString()

		// Set requestID in locals to be accessible by handlers if needed
		c.Locals("requestid", requestID)

		// Let Fiber process the request
		err := c.Next()

		// Calculate latency
		latency := time.Since(start)

		// Get status code from response
		statusCode := c.Response().StatusCode()

		// Prepare log fields
		logEntry := config.Log.WithFields(map[string]interface{}{
			"request_id": requestID,
			"http_method": c.Method(),
			"uri":         c.OriginalURL(),
			"status_code": statusCode,
			"latency_ms":  latency.Milliseconds(),
			"client_ip":   c.IP(),
			"user_agent":  string(c.Request().Header.UserAgent()),
		})

		// If an error occurred, log it at the error level with the error message
		if err != nil {
			// The error will be handled by the global error handler, 
			// but we log it here with request context as well.
			logEntry.WithField("error", err.Error()).Error("Request processing failed")
		} else {
			// Log based on status code
			if statusCode >= 500 {
				logEntry.Error("Request completed with server error")
			} else if statusCode >= 400 {
				logEntry.Warn("Request completed with client error")
			} else {
				logEntry.Info("Request completed successfully")
			}
		}

		// Important: return the error so that Fiber's error handler
		// (including our custom one in main.go) can process it.
		return err
	}
}
