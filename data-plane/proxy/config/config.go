package config

import (
	"os"
	"strconv"
	"time"
)

// Config holds all configuration for the inference proxy
type Config struct {
	// Server settings
	Port string

	// Batching settings
	BatchSize    int
	BatchTimeout time.Duration

	// Backend model server settings
	ModelServerURL string

	// Logging
	LogLevel string
}

// Load reads configuration from environment variables with sensible defaults
func Load() *Config {
	return &Config{
		Port:           getEnv("PORT", "8080"),
		BatchSize:      getEnvInt("BATCH_SIZE", 32),
		BatchTimeout:   getEnvDuration("BATCH_TIMEOUT_MS", 50),
		ModelServerURL: getEnv("MODEL_SERVER_URL", "http://localhost:8000"),
		LogLevel:       getEnv("LOG_LEVEL", "info"),
	}
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getEnvInt(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if intVal, err := strconv.Atoi(value); err == nil {
			return intVal
		}
	}
	return defaultValue
}

func getEnvDuration(key string, defaultMs int) time.Duration {
	ms := getEnvInt(key, defaultMs)
	return time.Duration(ms) * time.Millisecond
}
