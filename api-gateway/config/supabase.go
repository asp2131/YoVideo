package config

import (
	"log"
	"os"

	supa "github.com/supabase-community/supabase-go"
)

var SupabaseClient *supa.Client

// InitSupabase initializes the Supabase client using environment variables.
func InitSupabase() error {
	supabaseURL := os.Getenv("SUPABASE_URL")
	if supabaseURL == "" {
		supabaseURL = "https://whwbduaefolbnfdrcfuo.supabase.co"
	}
	
	// Try to use the service key from environment variable first
	supabaseKey := os.Getenv("SUPABASE_SERVICE_KEY")
	if supabaseKey == "" {
		// Fallback to the anonymous key
		supabaseKey = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Indod2JkdWFlZm9sYm5mZHJjZnVvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDcxNTU2MzQsImV4cCI6MjA2MjczMTYzNH0.dVMinX4X2mH_SVsGcokMHEGd1mDOb4pNO7o6wj_XLMU"
		log.Println("Warning: Using anonymous key for Supabase. Set SUPABASE_SERVICE_KEY for full access.")
	}

	client, err := supa.NewClient(supabaseURL, supabaseKey, nil)
	if err != nil {
		log.Fatalf("Error initializing Supabase client: %v", err)
		return err
	}

	SupabaseClient = client
	log.Println("Supabase client initialized successfully.")
	return nil
}

// GetSupabaseClient returns the initialized Supabase client with the service key if available.
// If the client hasn't been initialized yet, it will initialize it.
func GetSupabaseClient() *supa.Client {
	// Check if we need to initialize with service key
	serviceKey := os.Getenv("SUPABASE_SERVICE_KEY")
	if serviceKey != "" {
		// Always reinitialize with the service key to ensure we're using it
		supabaseURL := GetSupabaseURL()
		client, err := supa.NewClient(supabaseURL, serviceKey, nil)
		if err != nil {
			log.Printf("Error initializing Supabase client with service key: %v", err)
			// Fall back to the existing client or initialize it if nil
			if SupabaseClient == nil {
				InitSupabase() // Initialize with anonymous key as fallback
			}
		} else {
			// Update the global client with the service key client
			SupabaseClient = client
			log.Println("Supabase client initialized with service key.")
		}
	} else if SupabaseClient == nil {
		// If no service key and client is nil, initialize with anonymous key
		log.Println("Warning: Supabase client accessed before initialization and no service key available.")
		InitSupabase() // Initialize with anonymous key
	}
	return SupabaseClient
}

// GetSupabaseURL returns the Supabase URL used for API requests
func GetSupabaseURL() string {
	supabaseURL := os.Getenv("SUPABASE_URL")
	if supabaseURL == "" {
		return "https://whwbduaefolbnfdrcfuo.supabase.co"
	}
	return supabaseURL
}

// GetSupabaseKey returns the Supabase API key used for authentication
func GetSupabaseKey() string {
	// Try to use the service key from environment variable first
	supabaseKey := os.Getenv("SUPABASE_SERVICE_KEY")
	if supabaseKey == "" {
		// Fallback to the anonymous key
		return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Indod2JkdWFlZm9sYm5mZHJjZnVvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDcxNTU2MzQsImV4cCI6MjA2MjczMTYzNH0.dVMinX4X2mH_SVsGcokMHEGd1mDOb4pNO7o6wj_XLMU"
	}
	return supabaseKey
}
