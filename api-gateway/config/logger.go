package config

import (
	"os"

	"github.com/sirupsen/logrus"
)

var Log *logrus.Logger

func InitLogger() {
	Log = logrus.New()

	// Set formatter to JSON
	Log.SetFormatter(&logrus.JSONFormatter{})

	// Set output to stdout (default)
	Log.SetOutput(os.Stdout)

	// Set log level - you can make this configurable via env vars later
	Log.SetLevel(logrus.InfoLevel)

	// You could add more default fields here if needed, e.g.:
	// Log = Log.WithFields(logrus.Fields{
	// 	"service": "api-gateway",
	// }).Logger
}
