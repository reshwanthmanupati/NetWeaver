package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/reshwanthmanupati/NetWeaver/services/intent-engine/internal/api"
	"github.com/reshwanthmanupati/NetWeaver/services/intent-engine/internal/engine"
	"github.com/reshwanthmanupati/NetWeaver/services/intent-engine/internal/storage"
)

const (
	ServiceName = "intent-engine"
	Version     = "2.0.0"
	DefaultPort = "8081"
)

func main() {
	log.Printf("Starting %s v%s", ServiceName, Version)

	// Initialize storage (PostgreSQL)
	dbConfig := storage.DBConfig{
		Host:     getEnv("DB_HOST", "localhost"),
		Port:     getEnv("DB_PORT", "5432"),
		Database: getEnv("DB_NAME", "netweaver"),
		User:     getEnv("DB_USER", "netweaver"),
		Password: getEnv("DB_PASSWORD", "netweaver_secure_pass_2026"),
	}

	store, err := storage.NewPostgresStorage(dbConfig)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}
	defer store.Close()

	log.Println("Database connection established")

	// Initialize intent engine
	engineConfig := engine.EngineConfig{
		EnableConflictDetection: true,
		EnableCompliance:        true,
		ComplianceCheckInterval: 30 * time.Second,
	}

	intentEngine := engine.NewIntentEngine(store, engineConfig)
	log.Println("Intent engine initialized")

	// Start compliance monitoring in background
	go intentEngine.StartComplianceMonitoring(context.Background())

	// Initialize HTTP router
	router := setupRouter(intentEngine, store)

	// Create HTTP server
	port := getEnv("PORT", DefaultPort)
	srv := &http.Server{
		Addr:         ":" + port,
		Handler:      router,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// Start server in goroutine
	go func() {
		log.Printf("Server listening on port %s", port)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server failed: %v", err)
		}
	}()

	// Graceful shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("Shutting down server...")

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		log.Printf("Server forced to shutdown: %v", err)
	}

	log.Println("Server stopped gracefully")
}

func setupRouter(intentEngine *engine.IntentEngine, store engine.Storage) *gin.Engine {
	// Set Gin mode based on environment
	if getEnv("ENV", "development") == "production" {
		gin.SetMode(gin.ReleaseMode)
	}

	router := gin.New()
	router.Use(gin.Logger())
	router.Use(gin.Recovery())
	router.Use(corsMiddleware())

	// Health check endpoint
	router.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status":  "healthy",
			"service": ServiceName,
			"version": Version,
			"time":    time.Now().UTC(),
		})
	})

	// API routes
	apiHandler := api.NewHandler(intentEngine, store)
	v1 := router.Group("/api/v1")
	{
		// Static routes MUST be registered before wildcard :id routes
		// to prevent Gin httprouter panic from wildcard/static conflicts
		v1.POST("/intents", apiHandler.CreateIntent)
		v1.GET("/intents", apiHandler.ListIntents)
		v1.POST("/intents/validate-policy", apiHandler.ValidatePolicy)
		v1.GET("/intents/conflicts", apiHandler.DetectConflicts)
		v1.GET("/intents/compliance-report", apiHandler.GetComplianceReport)

		// Wildcard :id routes (after static routes)
		v1.GET("/intents/:id", apiHandler.GetIntent)
		v1.PUT("/intents/:id", apiHandler.UpdateIntent)
		v1.DELETE("/intents/:id", apiHandler.DeleteIntent)
		v1.POST("/intents/:id/validate", apiHandler.ValidateIntent)
		v1.POST("/intents/:id/deploy", apiHandler.DeployIntent)
		v1.POST("/intents/:id/rollback", apiHandler.RollbackIntent)
		v1.GET("/intents/:id/compliance", apiHandler.CheckCompliance)
		v1.GET("/intents/:id/history", apiHandler.GetIntentHistory)
	}

	return router
}

func corsMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Writer.Header().Set("Access-Control-Allow-Origin", "*")
		c.Writer.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")

		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(http.StatusNoContent)
			return
		}

		c.Next()
	}
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
