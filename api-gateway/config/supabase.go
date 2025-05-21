package config

import (
	"log"

	supa "github.com/supabase-community/supabase-go"
)

var SupabaseClient *supa.Client

// InitSupabase initializes the Supabase client using environment variables.
func InitSupabase() error {
	supabaseURL := "https://whwbduaefolbnfdrcfuo.supabase.co"
	supabaseKey := "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Indod2JkdWFlZm9sYm5mZHJjZnVvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDcxNTU2MzQsImV4cCI6MjA2MjczMTYzNH0.dVMinX4X2mH_SVsGcokMHEGd1mDOb4pNO7o6wj_XLMU"

	client, err := supa.NewClient(supabaseURL, supabaseKey, nil)
	if err != nil {
		log.Fatalf("Error initializing Supabase client: %v", err)
		return err
	}

	SupabaseClient = client
	log.Println("Supabase client initialized successfully.")
	return nil
}

// GetSupabaseClient returns the initialized Supabase client.
// It's a good practice to check if InitSupabase was called and successful before using the client.
func GetSupabaseClient() *supa.Client {
	if SupabaseClient == nil {
		log.Println("Warning: Supabase client accessed before initialization or initialization failed.")
		// Optionally, you could try to initialize it here if not already, or panic.
		// For now, we'll just return the potentially nil client, relying on prior initialization.
	}
	return SupabaseClient
}
