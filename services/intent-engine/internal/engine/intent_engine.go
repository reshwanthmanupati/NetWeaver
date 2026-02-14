package engine

import (
	"context"
	"fmt"
	"log"
	"sync"
	"time"

	"gopkg.in/yaml.v3"
)

// IntentEngine is the core engine for processing network intents
type IntentEngine struct {
	storage  Storage
	config   EngineConfig
	parser   *PolicyParser
	translator *ConfigTranslator
	validator  *ConflictDetector
	mu       sync.RWMutex
}

// EngineConfig configuration for the intent engine
type EngineConfig struct {
	EnableConflictDetection bool
	EnableCompliance        bool
	ComplianceCheckInterval time.Duration
}

// Storage interface for intent persistence
type Storage interface {
	SaveIntent(intent *Intent) error
	GetIntent(id string) (*Intent, error)
	ListIntents(filters map[string]interface{}) ([]*Intent, error)
	UpdateIntent(intent *Intent) error
	DeleteIntent(id string) error
	SaveDeployment(deployment *Deployment) error
	GetDeployments(intentID string) ([]*Deployment, error)
}

// Intent represents a high-level network policy
type Intent struct {
	ID          string                 `json:"id" yaml:"id"`
	Name        string                 `json:"name" yaml:"name"`
	Description string                 `json:"description" yaml:"description"`
	Priority    int                    `json:"priority" yaml:"priority"`
	Policy      PolicySpec             `json:"policy" yaml:"policy"`
	Targets     []Target               `json:"targets" yaml:"targets"`
	Status      string                 `json:"status"` // draft, validated, deployed, failed
	CreatedAt   time.Time              `json:"created_at"`
	UpdatedAt   time.Time              `json:"updated_at"`
	DeployedAt  *time.Time             `json:"deployed_at,omitempty"`
	CreatedBy   string                 `json:"created_by" yaml:"created_by"`
	Metadata    map[string]interface{} `json:"metadata,omitempty" yaml:"metadata,omitempty"`
}

// PolicySpec defines the intent policy in natural language
type PolicySpec struct {
	Type        string                 `json:"type" yaml:"type"` // latency, bandwidth, security, routing
	Constraints []Constraint           `json:"constraints" yaml:"constraints"`
	Actions     []Action               `json:"actions" yaml:"actions"`
	Conditions  []Condition            `json:"conditions,omitempty" yaml:"conditions,omitempty"`
	Schedule    *Schedule              `json:"schedule,omitempty" yaml:"schedule,omitempty"`
	Metadata    map[string]interface{} `json:"metadata,omitempty" yaml:"metadata,omitempty"`
}

// Constraint defines a policy constraint (e.g., "latency < 50ms")
type Constraint struct {
	Metric   string      `json:"metric" yaml:"metric"`     // latency, bandwidth, packet_loss, jitter
	Operator string      `json:"operator" yaml:"operator"` // <, >, <=, >=, ==
	Value    interface{} `json:"value" yaml:"value"`       // 50ms, 1Gbps, 0.1%
	Unit     string      `json:"unit" yaml:"unit"`         // ms, Gbps, %, pps
}

// Action defines what should happen when policy is applied
type Action struct {
	Type       string                 `json:"type" yaml:"type"` // route, qos, firewall, traffic_engineering
	Parameters map[string]interface{} `json:"parameters" yaml:"parameters"`
}

// Condition defines when the policy should be active
type Condition struct {
	Type       string                 `json:"type" yaml:"type"` // traffic_type, source, destination, time
	Parameters map[string]interface{} `json:"parameters" yaml:"parameters"`
}

// Schedule defines time-based policy activation
type Schedule struct {
	StartTime string   `json:"start_time,omitempty" yaml:"start_time,omitempty"` // "09:00"
	EndTime   string   `json:"end_time,omitempty" yaml:"end_time,omitempty"`     // "17:00"
	Days      []string `json:"days,omitempty" yaml:"days,omitempty"`             // ["monday", "tuesday"]
	Timezone  string   `json:"timezone,omitempty" yaml:"timezone,omitempty"`     // "America/New_York"
}

// Target defines where the intent should be applied
type Target struct {
	Type       string   `json:"type" yaml:"type"`             // device, interface, network, region
	Identifiers []string `json:"identifiers" yaml:"identifiers"` // Device IDs, interface names, IP ranges
}

// Deployment represents a deployed configuration
type Deployment struct {
	ID            string                 `json:"id"`
	IntentID      string                 `json:"intent_id"`
	DeviceID      string                 `json:"device_id"`
	Vendor        string                 `json:"vendor"`
	Configuration string                 `json:"configuration"` // Generated config
	Status        string                 `json:"status"`        // pending, success, failed
	DeployedAt    time.Time              `json:"deployed_at"`
	Error         string                 `json:"error,omitempty"`
	Metadata      map[string]interface{} `json:"metadata,omitempty"`
}

// ComplianceStatus represents policy compliance check result
type ComplianceStatus struct {
	IntentID   string    `json:"intent_id"`
	Compliant  bool      `json:"compliant"`
	Violations []string  `json:"violations,omitempty"`
	CheckedAt  time.Time `json:"checked_at"`
	Metrics    map[string]interface{} `json:"metrics"`
}

// ValidationResult result of intent validation
type ValidationResult struct {
	Valid    bool     `json:"valid"`
	Errors   []string `json:"errors,omitempty"`
	Warnings []string `json:"warnings,omitempty"`
	Conflicts []ConflictInfo `json:"conflicts,omitempty"`
}

// ConflictInfo information about policy conflicts
type ConflictInfo struct {
	ConflictingIntentID string `json:"conflicting_intent_id"`
	ConflictType        string `json:"conflict_type"` // resource, constraint, action
	Description         string `json:"description"`
	Severity            string `json:"severity"` // low, medium, high, critical
}

// NewIntentEngine creates a new intent engine instance
func NewIntentEngine(storage Storage, config EngineConfig) *IntentEngine {
	return &IntentEngine{
		storage:    storage,
		config:     config,
		parser:     NewPolicyParser(),
		translator: NewConfigTranslator(),
		validator:  NewConflictDetector(),
	}
}

// CreateIntent creates and validates a new intent
func (e *IntentEngine) CreateIntent(intent *Intent) (*Intent, error) {
	e.mu.Lock()
	defer e.mu.Unlock()

	// Generate ID if not provided
	if intent.ID == "" {
		intent.ID = generateID()
	}

	// Set timestamps
	now := time.Now()
	intent.CreatedAt = now
	intent.UpdatedAt = now
	intent.Status = "draft"

	// Validate intent
	validation := e.ValidateIntent(intent)
	if !validation.Valid {
		return nil, fmt.Errorf("intent validation failed: %v", validation.Errors)
	}

	// Check for conflicts if enabled
	if e.config.EnableConflictDetection {
		conflicts, err := e.validator.DetectConflicts(intent, e.storage)
		if err != nil {
			return nil, fmt.Errorf("conflict detection failed: %w", err)
		}
		if len(conflicts) > 0 {
			// Log warnings but don't fail (user can review)
			log.Printf("Intent %s has %d potential conflicts", intent.ID, len(conflicts))
			for _, conflict := range conflicts {
				log.Printf("  - %s: %s", conflict.ConflictType, conflict.Description)
			}
		}
	}

	// Save to storage
	if err := e.storage.SaveIntent(intent); err != nil {
		return nil, fmt.Errorf("failed to save intent: %w", err)
	}

	intent.Status = "validated"
	return intent, nil
}

// ValidateIntent validates an intent policy
func (e *IntentEngine) ValidateIntent(intent *Intent) *ValidationResult {
	result := &ValidationResult{
		Valid:    true,
		Errors:   []string{},
		Warnings: []string{},
	}

	// Basic validation
	if intent.Name == "" {
		result.Errors = append(result.Errors, "intent name is required")
		result.Valid = false
	}

	if intent.Policy.Type == "" {
		result.Errors = append(result.Errors, "policy type is required")
		result.Valid = false
	}

	// Validate policy type
	validTypes := map[string]bool{
		"latency": true, "bandwidth": true, "security": true,
		"routing": true, "qos": true, "availability": true,
	}
	if !validTypes[intent.Policy.Type] {
		result.Errors = append(result.Errors, fmt.Sprintf("invalid policy type: %s", intent.Policy.Type))
		result.Valid = false
	}

	// Validate constraints
	if len(intent.Policy.Constraints) == 0 {
		result.Warnings = append(result.Warnings, "no constraints defined")
	}

	for _, constraint := range intent.Policy.Constraints {
		if err := e.parser.ValidateConstraint(&constraint); err != nil {
			result.Errors = append(result.Errors, fmt.Sprintf("invalid constraint: %v", err))
			result.Valid = false
		}
	}

	// Validate actions
	if len(intent.Policy.Actions) == 0 {
		result.Errors = append(result.Errors, "at least one action is required")
		result.Valid = false
	}

	// Validate targets
	if len(intent.Targets) == 0 {
		result.Errors = append(result.Errors, "at least one target is required")
		result.Valid = false
	}

	return result
}

// DeployIntent translates intent to vendor configs and deploys
func (e *IntentEngine) DeployIntent(intentID string) ([]*Deployment, error) {
	e.mu.Lock()
	defer e.mu.Unlock()

	// Get intent
	intent, err := e.storage.GetIntent(intentID)
	if err != nil {
		return nil, fmt.Errorf("failed to get intent: %w", err)
	}

	// Validate before deployment
	validation := e.ValidateIntent(intent)
	if !validation.Valid {
		return nil, fmt.Errorf("intent validation failed: %v", validation.Errors)
	}

	deployments := []*Deployment{}

	// Translate to vendor configurations
	for _, target := range intent.Targets {
		for _, deviceID := range target.Identifiers {
			// Get device info (vendor, model, etc.) - would query device-manager service
			vendor := "cisco_ios" // Placeholder - should come from device-manager

			// Translate intent to device config
			config, err := e.translator.TranslateIntent(intent, vendor, deviceID)
			if err != nil {
				log.Printf("Failed to translate intent for device %s: %v", deviceID, err)
				continue
			}

			deployment := &Deployment{
				ID:            generateID(),
				IntentID:      intentID,
				DeviceID:      deviceID,
				Vendor:        vendor,
				Configuration: config,
				Status:        "pending",
				DeployedAt:    time.Now(),
			}

			// TODO: Call device-manager service to actually push config
			// For now, mark as success
			deployment.Status = "success"

			// Save deployment record
			if err := e.storage.SaveDeployment(deployment); err != nil {
				log.Printf("Failed to save deployment: %v", err)
			}

			deployments = append(deployments, deployment)
		}
	}

	// Update intent status
	now := time.Now()
	intent.DeployedAt = &now
	intent.Status = "deployed"
	if err := e.storage.UpdateIntent(intent); err != nil {
		log.Printf("Failed to update intent status: %v", err)
	}

	return deployments, nil
}

// CheckCompliance checks if deployed intent is compliant with policy
func (e *IntentEngine) CheckCompliance(intentID string) (*ComplianceStatus, error) {
	// Get intent
	intent, err := e.storage.GetIntent(intentID)
	if err != nil {
		return nil, fmt.Errorf("failed to get intent: %w", err)
	}

	if intent.Status != "deployed" {
		return &ComplianceStatus{
			IntentID:  intentID,
			Compliant: false,
			Violations: []string{"intent not deployed"},
			CheckedAt: time.Now(),
		}, nil
	}

	// TODO: Query telemetry data to check actual metrics against constraints
	// For now, return compliant
	status := &ComplianceStatus{
		IntentID:   intentID,
		Compliant:  true,
		Violations: []string{},
		CheckedAt:  time.Now(),
		Metrics:    map[string]interface{}{},
	}

	// Check each constraint
	for _, constraint := range intent.Policy.Constraints {
		// TODO: Query actual metric value from TimescaleDB
		// Example: SELECT AVG(latency) FROM flow_metrics WHERE ...
		
		// Placeholder logic
		actualValue := 45.0 // ms
		targetValue := 50.0 // from constraint
		
		if constraint.Operator == "<" && actualValue >= targetValue {
			status.Compliant = false
			status.Violations = append(status.Violations, 
				fmt.Sprintf("%s constraint violated: %v >= %v %s", 
					constraint.Metric, actualValue, targetValue, constraint.Unit))
		}
		
		status.Metrics[constraint.Metric] = actualValue
	}

	return status, nil
}

// StartComplianceMonitoring starts periodic compliance checks
func (e *IntentEngine) StartComplianceMonitoring(ctx context.Context) {
	if !e.config.EnableCompliance {
		return
	}

	ticker := time.NewTicker(e.config.ComplianceCheckInterval)
	defer ticker.Stop()

	log.Printf("Starting compliance monitoring (interval: %v)", e.config.ComplianceCheckInterval)

	for {
		select {
		case <-ctx.Done():
			log.Println("Compliance monitoring stopped")
			return
		case <-ticker.C:
			e.checkAllCompliance()
		}
	}
}

func (e *IntentEngine) checkAllCompliance() {
	// Get all deployed intents
	intents, err := e.storage.ListIntents(map[string]interface{}{
		"status": "deployed",
	})
	if err != nil {
		log.Printf("Failed to list intents for compliance check: %v", err)
		return
	}

	for _, intent := range intents {
		status, err := e.CheckCompliance(intent.ID)
		if err != nil {
			log.Printf("Compliance check failed for intent %s: %v", intent.ID, err)
			continue
		}

		if !status.Compliant {
			log.Printf("ALERT: Intent %s is non-compliant: %v", intent.ID, status.Violations)
			// TODO: Trigger self-healing or alert
		}
	}
}

// ParseYAMLIntent parses a YAML policy into an Intent struct
func ParseYAMLIntent(yamlData []byte) (*Intent, error) {
	var intent Intent
	if err := yaml.Unmarshal(yamlData, &intent); err != nil {
		return nil, fmt.Errorf("failed to parse YAML: %w", err)
	}
	return &intent, nil
}

// Helper function to generate unique IDs
func generateID() string {
	return fmt.Sprintf("intent-%d", time.Now().UnixNano())
}
