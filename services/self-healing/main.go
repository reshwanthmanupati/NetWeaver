package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/reshwanthmanupati/NetWeaver/services/self-healing/internal/detector"
	"github.com/reshwanthmanupati/NetWeaver/services/self-healing/internal/remediator"
	"github.com/reshwanthmanupati/NetWeaver/services/self-healing/internal/storage"
)

func main() {
	log.Println("Starting Self-Healing System...")

	// Database configuration
	dbConfig := storage.DBConfig{
		Host:     getEnv("DB_HOST", "localhost"),
		Port:     getEnv("DB_PORT", "5432"),
		Database: getEnv("DB_NAME", "netweaver"),
		User:     getEnv("DB_USER", "netweaver"),
		Password: getEnv("DB_PASSWORD", "netweaver_secure_pass_2026"),
	}

	// Initialize storage
	store, err := storage.NewPostgresStorage(dbConfig)
	if err != nil {
		log.Fatalf("Failed to initialize storage: %v", err)
	}
	log.Println("✓ Database connection established")

	// RabbitMQ configuration
	rabbitmqURL := fmt.Sprintf("amqp://%s:%s@%s:%s/",
		getEnv("RABBITMQ_USER", "netweaver"),
		getEnv("RABBITMQ_PASSWORD", "netweaver_rabbitmq_2026"),
		getEnv("RABBITMQ_HOST", "rabbitmq"),
		getEnv("RABBITMQ_PORT", "5672"),
	)

	// Initialize failure detector
	detectorConfig := detector.Config{
		RabbitMQURL:         rabbitmqURL,
		TelemetryQueue:      "telemetry.events",
		FailureThresholds:   getDefaultThresholds(),
		CheckInterval:       30 * time.Second,
		DeviceManagerURL:    getEnv("DEVICE_MANAGER_URL", "http://device-manager:8083"),
	}

	failureDetector, err := detector.NewFailureDetector(detectorConfig, store)
	if err != nil {
		log.Fatalf("Failed to initialize failure detector: %v", err)
	}
	log.Println("✓ Failure detector initialized")

	// Initialize remediator
	remediatorConfig := remediator.Config{
		DeviceManagerURL: getEnv("DEVICE_MANAGER_URL", "http://device-manager:8083"),
		IntentEngineURL:  getEnv("INTENT_ENGINE_URL", "http://intent-engine:8081"),
		MaxRetries:       3,
		RetryDelay:       5 * time.Second,
		RollbackOnError:  true,
	}

	rem := remediator.NewRemediator(remediatorConfig, store)
	log.Println("✓ Remediator initialized")

	// Start failure detector with remediation
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	go failureDetector.Start(ctx, rem)
	log.Println("✓ Self-healing engine started")

	// Setup HTTP server
	router := setupRouter(failureDetector, rem, store)
	
	port := getEnv("PORT", "8082")
	srv := &http.Server{
		Addr:    ":" + port,
		Handler: router,
	}

	// Start server in goroutine
	go func() {
		log.Printf("✓ Self-Healing API listening on port %s\n", port)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server error: %v", err)
		}
	}()

	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("Shutting down server...")

	// Graceful shutdown
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer shutdownCancel()

	if err := srv.Shutdown(shutdownCtx); err != nil {
		log.Printf("Server forced to shutdown: %v", err)
	}

	log.Println("Server stopped gracefully")
}

func setupRouter(detector *detector.FailureDetector, rem *remediator.Remediator, store storage.Storage) *gin.Engine {
	// Set Gin mode
	if getEnv("ENV", "development") == "production" {
		gin.SetMode(gin.ReleaseMode)
	}

	router := gin.Default()

	// CORS middleware
	router.Use(func(c *gin.Context) {
		c.Writer.Header().Set("Access-Control-Allow-Origin", "*")
		c.Writer.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
		
		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}
		
		c.Next()
	})

	// Health check
	router.GET("/health", func(c *gin.Context) {
		c.JSON(200, gin.H{
			"status":  "healthy",
			"service": "self-healing",
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	})

	// API routes
	api := router.Group("/api/v1")
	{
		// Incident management
		api.GET("/incidents", getIncidents(store))
		api.GET("/incidents/:id", getIncident(store))
		api.POST("/incidents/:id/resolve", resolveIncident(store))
		
		// Remediation actions
		api.POST("/remediate", triggerRemediation(rem, store))
		api.POST("/rollback/:incident_id", rollbackRemediation(rem, store))
		
		// Statistics
		api.GET("/stats", getStats(store))
		api.GET("/stats/mttr", getMTTR(store))
		
		// Configuration
		api.GET("/config", getConfig(detector))
		api.PUT("/config/thresholds", updateThresholds(detector))
	}

	return router
}

// HTTP Handlers

func getIncidents(store storage.Storage) gin.HandlerFunc {
	return func(c *gin.Context) {
		status := c.Query("status")
		limit := c.DefaultQuery("limit", "100")
		
		filters := map[string]interface{}{
			"limit": limit,
		}
		if status != "" {
			filters["status"] = status
		}

		incidents, err := store.ListIncidents(filters)
		if err != nil {
			c.JSON(500, gin.H{"error": err.Error()})
			return
		}

		c.JSON(200, gin.H{
			"count":     len(incidents),
			"incidents": incidents,
		})
	}
}

func getIncident(store storage.Storage) gin.HandlerFunc {
	return func(c *gin.Context) {
		id := c.Param("id")
		
		incident, err := store.GetIncident(id)
		if err != nil {
			c.JSON(404, gin.H{"error": "Incident not found"})
			return
		}

		c.JSON(200, incident)
	}
}

func resolveIncident(store storage.Storage) gin.HandlerFunc {
	return func(c *gin.Context) {
		id := c.Param("id")
		
		var req struct {
			Resolution string `json:"resolution"`
			ResolvedBy string `json:"resolved_by"`
		}
		
		if err := c.BindJSON(&req); err != nil {
			c.JSON(400, gin.H{"error": "Invalid request"})
			return
		}

		if err := store.ResolveIncident(id, req.Resolution, req.ResolvedBy); err != nil {
			c.JSON(500, gin.H{"error": err.Error()})
			return
		}

		c.JSON(200, gin.H{"message": "Incident resolved"})
	}
}

func triggerRemediation(rem *remediator.Remediator, store storage.Storage) gin.HandlerFunc {
	return func(c *gin.Context) {
		var req struct {
			IncidentType string                 `json:"incident_type"`
			DeviceID     string                 `json:"device_id"`
			Details      map[string]interface{} `json:"details"`
		}
		
		if err := c.BindJSON(&req); err != nil {
			c.JSON(400, gin.H{"error": "Invalid request"})
			return
		}

		// Create incident
		incident := &storage.Incident{
			Type:       req.IncidentType,
			DeviceID:   req.DeviceID,
			Severity:   "high",
			Status:     "detected",
			DetectedAt: time.Now().UTC(),
			Details:    req.Details,
		}

		if err := store.SaveIncident(incident); err != nil {
			c.JSON(500, gin.H{"error": err.Error()})
			return
		}

		// Trigger remediation
		go func() {
			ctx := context.Background()
			if err := rem.Remediate(ctx, incident); err != nil {
				log.Printf("Remediation failed for incident %s: %v", incident.ID, err)
			}
		}()

		c.JSON(202, gin.H{
			"message":     "Remediation triggered",
			"incident_id": incident.ID,
		})
	}
}

func rollbackRemediation(rem *remediator.Remediator, store storage.Storage) gin.HandlerFunc {
	return func(c *gin.Context) {
		incidentID := c.Param("incident_id")
		
		incident, err := store.GetIncident(incidentID)
		if err != nil {
			c.JSON(404, gin.H{"error": "Incident not found"})
			return
		}

		ctx := context.Background()
		if err := rem.Rollback(ctx, incident); err != nil {
			c.JSON(500, gin.H{"error": err.Error()})
			return
		}

		c.JSON(200, gin.H{"message": "Rollback successful"})
	}
}

func getStats(store storage.Storage) gin.HandlerFunc {
	return func(c *gin.Context) {
		stats, err := store.GetStatistics()
		if err != nil {
			c.JSON(500, gin.H{"error": err.Error()})
			return
		}

		c.JSON(200, stats)
	}
}

func getMTTR(store storage.Storage) gin.HandlerFunc {
	return func(c *gin.Context) {
		period := c.DefaultQuery("period", "24h")
		
		duration, err := time.ParseDuration(period)
		if err != nil {
			c.JSON(400, gin.H{"error": "Invalid period"})
			return
		}

		mttr, err := store.GetMTTR(duration)
		if err != nil {
			c.JSON(500, gin.H{"error": err.Error()})
			return
		}

		c.JSON(200, gin.H{
			"period":     period,
			"mttr":       mttr.String(),
			"mttr_seconds": mttr.Seconds(),
		})
	}
}

func getConfig(detector *detector.FailureDetector) gin.HandlerFunc {
	return func(c *gin.Context) {
		config := detector.GetConfig()
		c.JSON(200, config)
	}
}

func updateThresholds(detector *detector.FailureDetector) gin.HandlerFunc {
	return func(c *gin.Context) {
		var thresholds map[string]interface{}
		
		if err := c.BindJSON(&thresholds); err != nil {
			c.JSON(400, gin.H{"error": "Invalid request"})
			return
		}

		if err := detector.UpdateThresholds(thresholds); err != nil {
			c.JSON(500, gin.H{"error": err.Error()})
			return
		}

		c.JSON(200, gin.H{"message": "Thresholds updated"})
	}
}

// Helper functions

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getDefaultThresholds() map[string]interface{} {
	return map[string]interface{}{
		"latency_ms":        100,  // High latency threshold
		"packet_loss_pct":   5,    // Packet loss threshold
		"jitter_ms":         50,   // Jitter threshold
		"bandwidth_pct":     80,   // Bandwidth utilization
		"cpu_pct":           90,   // CPU utilization
		"memory_pct":        90,   // Memory utilization
		"link_down_count":   1,    // Immediate action on link down
		"consecutive_failures": 3, // Failures before triggering
	}
}
