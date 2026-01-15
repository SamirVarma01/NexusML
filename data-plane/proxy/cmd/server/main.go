package main

import (
	"context"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/nexusml/proxy/config"
	"github.com/nexusml/proxy/internal/batcher"
	"github.com/nexusml/proxy/internal/client"
	"github.com/nexusml/proxy/internal/router"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
)

func main() {
	// Load configuration
	cfg := config.Load()

	// Setup logging
	setupLogging(cfg.LogLevel)

	log.Info().
		Str("port", cfg.Port).
		Int("batch_size", cfg.BatchSize).
		Dur("batch_timeout", cfg.BatchTimeout).
		Str("model_server", cfg.ModelServerURL).
		Msg("Starting NexusML Inference Proxy")

	// Create model client
	modelClient := client.New(cfg.ModelServerURL)

	// Create batcher with the model client's ProcessBatch function
	b := batcher.New(cfg.BatchSize, cfg.BatchTimeout, modelClient.ProcessBatch)
	b.Start()

	// Create router
	r := router.New(b)

	// Create HTTP server
	server := &http.Server{
		Addr:         ":" + cfg.Port,
		Handler:      r.Handler(),
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 60 * time.Second,
		IdleTimeout:  120 * time.Second,
	}

	// Start server in goroutine
	go func() {
		log.Info().Str("addr", server.Addr).Msg("HTTP server listening")
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatal().Err(err).Msg("HTTP server failed")
		}
	}()

	// Wait for shutdown signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Info().Msg("Shutting down...")

	// Graceful shutdown
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	// Stop accepting new requests
	if err := server.Shutdown(ctx); err != nil {
		log.Error().Err(err).Msg("Server shutdown error")
	}

	// Stop batcher (processes remaining requests)
	b.Stop()

	log.Info().Msg("Server stopped")
}

func setupLogging(level string) {
	// Pretty console output for development
	log.Logger = log.Output(zerolog.ConsoleWriter{Out: os.Stderr})

	switch level {
	case "debug":
		zerolog.SetGlobalLevel(zerolog.DebugLevel)
	case "info":
		zerolog.SetGlobalLevel(zerolog.InfoLevel)
	case "warn":
		zerolog.SetGlobalLevel(zerolog.WarnLevel)
	case "error":
		zerolog.SetGlobalLevel(zerolog.ErrorLevel)
	default:
		zerolog.SetGlobalLevel(zerolog.InfoLevel)
	}
}
