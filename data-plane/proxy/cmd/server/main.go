package main

import (
	"fmt"
	"log"
	"net/http"
	"os"
)

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	http.HandleFunc("/health", healthHandler)
	http.HandleFunc("/predict", predictHandler)

	log.Printf("🚀 NexusML Inference Proxy starting on port %s", port)
	log.Printf("📊 Batch size: %s", getEnv("BATCH_SIZE", "32"))
	log.Printf("⏱️  Batch timeout: %sms", getEnv("BATCH_TIMEOUT_MS", "50"))

	if err := http.ListenAndServe(":"+port, nil); err != nil {
		log.Fatal(err)
	}
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	fmt.Fprintf(w, `{"status":"healthy"}`)
}

func predictHandler(w http.ResponseWriter, r *http.Request) {
	// TODO: Implement batching logic
	w.WriteHeader(http.StatusOK)
	fmt.Fprintf(w, `{"result":"placeholder - batching not implemented yet"}`)
}

func getEnv(key, defaultValue string) string {
	value := os.Getenv(key)
	if value == "" {
		return defaultValue
	}
	return value
}
