package detector

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"sync"
	"time"

	"github.com/reshwanthmanupati/NetWeaver/services/self-healing/internal/remediator"
	"github.com/reshwanthmanupati/NetWeaver/services/self-healing/internal/storage"
	"github.com/streadway/amqp"
)

// Config configuration for failure detector
type Config struct {
	RabbitMQURL       string
	TelemetryQueue    string
	FailureThresholds map[string]interface{}
	CheckInterval     time.Duration
	DeviceManagerURL  string
}

// FailureDetector detects network failures from telemetry events
type FailureDetector struct {
	config      Config
	storage     storage.Storage
	conn        *amqp.Connection
	channel     *amqp.Channel
	thresholds  map[string]interface{}
	deviceState map[string]*DeviceState
	mu          sync.RWMutex
}

// DeviceState tracks device health metrics
type DeviceState struct {
	DeviceID          string
	LastSeen          time.Time
	ConsecutiveFailures int
	Metrics           map[string]float64
	Status            string
	mu                sync.RWMutex
}

// TelemetryEvent event from telemetry agent
type TelemetryEvent struct {
	Type      string                 `json:"type"`
	Timestamp time.Time              `json:"timestamp"`
	DeviceID  string                 `json:"device_id"`
	Metric    string                 `json:"metric"`
	Value     float64                `json:"value"`
	Severity  string                 `json:"severity"`
	Details   map[string]interface{} `json:"details"`
}

// NewFailureDetector creates a new failure detector
func NewFailureDetector(config Config, store storage.Storage) (*FailureDetector, error) {
	detector := &FailureDetector{
		config:      config,
		storage:     store,
		thresholds:  config.FailureThresholds,
		deviceState: make(map[string]*DeviceState),
	}

	// Connect to RabbitMQ
	if err := detector.connectRabbitMQ(); err != nil {
		return nil, fmt.Errorf("failed to connect to RabbitMQ: %w", err)
	}

	return detector, nil
}

func (fd *FailureDetector) connectRabbitMQ() error {
	var err error
	
	fd.conn, err = amqp.Dial(fd.config.RabbitMQURL)
	if err != nil {
		return err
	}

	fd.channel, err = fd.conn.Channel()
	if err != nil {
		return err
	}

	// Declare telemetry queue
	_, err = fd.channel.QueueDeclare(
		fd.config.TelemetryQueue, // name
		true,                      // durable
		false,                     // delete when unused
		false,                     // exclusive
		false,                     // no-wait
		nil,                       // arguments
	)
	if err != nil {
		return err
	}

	log.Printf("✓ Connected to RabbitMQ, listening on queue: %s", fd.config.TelemetryQueue)
	return nil
}

// Start starts the failure detection loop
func (fd *FailureDetector) Start(ctx context.Context, rem *remediator.Remediator) {
	// Start consuming telemetry events
	go fd.consumeTelemetryEvents(ctx, rem)

	// Start periodic device health checks
	go fd.periodicHealthCheck(ctx, rem)

	log.Println("✓ Failure detector started")
}

func (fd *FailureDetector) consumeTelemetryEvents(ctx context.Context, rem *remediator.Remediator) {
	for {
		msgs, err := fd.channel.Consume(
			fd.config.TelemetryQueue, // queue
			"self-healing-consumer",   // consumer
			false,                     // auto-ack
			false,                     // exclusive
			false,                     // no-local
			false,                     // no-wait
			nil,                       // args
		)
		if err != nil {
			log.Printf("Failed to start consuming: %v", err)
			select {
			case <-ctx.Done():
				return
			case <-time.After(5 * time.Second):
				continue
			}
		}

		for {
			select {
			case <-ctx.Done():
				return
			case msg, ok := <-msgs:
				if !ok {
					log.Println("RabbitMQ channel closed, reconnecting...")
					for retries := 0; retries < 10; retries++ {
						if err := fd.connectRabbitMQ(); err != nil {
							log.Printf("Reconnect attempt %d failed: %v", retries+1, err)
							select {
							case <-ctx.Done():
								return
							case <-time.After(5 * time.Second):
							}
						} else {
							log.Println("RabbitMQ reconnected successfully")
							break
						}
					}
					break // Break inner loop to re-register consumer
				}

				// Process event
				var event TelemetryEvent
				if err := json.Unmarshal(msg.Body, &event); err != nil {
					log.Printf("Failed to parse telemetry event: %v", err)
					msg.Nack(false, false)
					continue
				}

				// Analyze event for failures
				if incident := fd.analyzeEvent(&event); incident != nil {
					log.Printf("⚠️  Failure detected: %s on device %s", incident.Type, incident.DeviceID)
					
					// Save incident
					if err := fd.storage.SaveIncident(incident); err != nil {
						log.Printf("Failed to save incident: %v", err)
					}

					// Trigger remediation
					go func() {
						remCtx := context.Background()
						if err := rem.Remediate(remCtx, incident); err != nil {
							log.Printf("Remediation failed: %v", err)
						}
					}()
				}

				msg.Ack(false)
			}
		}
	}
}

func (fd *FailureDetector) analyzeEvent(event *TelemetryEvent) *storage.Incident {
	fd.mu.Lock()
	defer fd.mu.Unlock()

	// Get or create device state
	state, exists := fd.deviceState[event.DeviceID]
	if !exists {
		state = &DeviceState{
			DeviceID: event.DeviceID,
			Metrics:  make(map[string]float64),
			Status:   "healthy",
		}
		fd.deviceState[event.DeviceID] = state
	}

	state.mu.Lock()
	defer state.mu.Unlock()

	state.LastSeen = event.Timestamp
	state.Metrics[event.Metric] = event.Value

	// Check for failure conditions
	var incident *storage.Incident

	switch event.Type {
	case "link_down":
		incident = &storage.Incident{
			Type:       "link_failure",
			DeviceID:   event.DeviceID,
			Severity:   "critical",
			Status:     "detected",
			DetectedAt: event.Timestamp,
			Details: map[string]interface{}{
				"interface": event.Details["interface"],
				"reason":    "Link down detected",
			},
		}
		state.ConsecutiveFailures++

	case "device_unreachable":
		incident = &storage.Incident{
			Type:       "device_failure",
			DeviceID:   event.DeviceID,
			Severity:   "critical",
			Status:     "detected",
			DetectedAt: event.Timestamp,
			Details: map[string]interface{}{
				"reason": "Device unreachable",
			},
		}
		state.ConsecutiveFailures++

	case "high_latency":
		threshold := fd.getThreshold("latency_ms", 100.0)
		if event.Value > threshold {
			if state.ConsecutiveFailures >= int(fd.getThreshold("consecutive_failures", 3.0)) {
				incident = &storage.Incident{
					Type:       "performance_degradation",
					DeviceID:   event.DeviceID,
					Severity:   "high",
					Status:     "detected",
					DetectedAt: event.Timestamp,
					Details: map[string]interface{}{
						"metric":    "latency",
						"value":     event.Value,
						"threshold": threshold,
						"source":    event.Details["source"],
						"destination": event.Details["destination"],
					},
				}
			}
			state.ConsecutiveFailures++
		} else {
			state.ConsecutiveFailures = 0
		}

	case "packet_loss":
		threshold := fd.getThreshold("packet_loss_pct", 5.0)
		if event.Value > threshold {
			if state.ConsecutiveFailures >= int(fd.getThreshold("consecutive_failures", 3.0)) {
				incident = &storage.Incident{
					Type:       "packet_loss",
					DeviceID:   event.DeviceID,
					Severity:   "high",
					Status:     "detected",
					DetectedAt: event.Timestamp,
					Details: map[string]interface{}{
						"metric":    "packet_loss",
						"value":     event.Value,
						"threshold": threshold,
					},
				}
			}
			state.ConsecutiveFailures++
		} else {
			state.ConsecutiveFailures = 0
		}

	case "high_cpu":
		threshold := fd.getThreshold("cpu_pct", 90.0)
		if event.Value > threshold {
			incident = &storage.Incident{
				Type:       "resource_exhaustion",
				DeviceID:   event.DeviceID,
				Severity:   "medium",
				Status:     "detected",
				DetectedAt: event.Timestamp,
				Details: map[string]interface{}{
					"metric":    "cpu",
					"value":     event.Value,
					"threshold": threshold,
				},
			}
		}
	}

	if incident != nil {
		state.Status = "unhealthy"
	} else if state.ConsecutiveFailures == 0 {
		state.Status = "healthy"
	}

	return incident
}

func (fd *FailureDetector) periodicHealthCheck(ctx context.Context, rem *remediator.Remediator) {
	ticker := time.NewTicker(fd.config.CheckInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			fd.checkDeviceHealth(ctx, rem)
		}
	}
}

func (fd *FailureDetector) checkDeviceHealth(ctx context.Context, rem *remediator.Remediator) {
	fd.mu.RLock()
	devices := make([]*DeviceState, 0, len(fd.deviceState))
	for _, state := range fd.deviceState {
		devices = append(devices, state)
	}
	fd.mu.RUnlock()

	now := time.Now()
	timeout := 5 * time.Minute

	for _, state := range devices {
		state.mu.RLock()
		lastSeen := state.LastSeen
		deviceID := state.DeviceID
		state.mu.RUnlock()

		// Check if device is stale (no recent telemetry)
		if now.Sub(lastSeen) > timeout {
			log.Printf("⚠️  Device %s has not sent telemetry for %v", deviceID, now.Sub(lastSeen))
			
			// Query device manager to verify status
			if !fd.isDeviceReachable(deviceID) {
				incident := &storage.Incident{
					Type:       "device_failure",
					DeviceID:   deviceID,
					Severity:   "critical",
					Status:     "detected",
					DetectedAt: now,
					Details: map[string]interface{}{
						"reason":    "Device unreachable",
						"last_seen": lastSeen,
					},
				}

				if err := fd.storage.SaveIncident(incident); err != nil {
					log.Printf("Failed to save incident: %v", err)
					continue
				}

				go func() {
					if err := rem.Remediate(ctx, incident); err != nil {
						log.Printf("Remediation failed: %v", err)
					}
				}()
			}
		}
	}
}

func (fd *FailureDetector) isDeviceReachable(deviceID string) bool {
	url := fmt.Sprintf("%s/api/v1/devices/%s/health", fd.config.DeviceManagerURL, deviceID)
	
	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Get(url)
	if err != nil {
		return false
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return false
	}

	var result map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return false
	}

	status, ok := result["status"].(string)
	return ok && status == "online"
}

func (fd *FailureDetector) getThreshold(key string, defaultValue float64) float64 {
	if val, ok := fd.thresholds[key]; ok {
		if fVal, ok := val.(float64); ok {
			return fVal
		}
		if iVal, ok := val.(int); ok {
			return float64(iVal)
		}
	}
	return defaultValue
}

// GetConfig returns current configuration
func (fd *FailureDetector) GetConfig() map[string]interface{} {
	fd.mu.RLock()
	defer fd.mu.RUnlock()

	return map[string]interface{}{
		"check_interval": fd.config.CheckInterval.String(),
		"thresholds":     fd.thresholds,
	}
}

// UpdateThresholds updates failure detection thresholds
func (fd *FailureDetector) UpdateThresholds(thresholds map[string]interface{}) error {
	fd.mu.Lock()
	defer fd.mu.Unlock()

	for key, value := range thresholds {
		fd.thresholds[key] = value
	}

	log.Printf("✓ Thresholds updated: %v", thresholds)
	return nil
}

// Close closes RabbitMQ connections
func (fd *FailureDetector) Close() error {
	if fd.channel != nil {
		fd.channel.Close()
	}
	if fd.conn != nil {
		fd.conn.Close()
	}
	return nil
}
