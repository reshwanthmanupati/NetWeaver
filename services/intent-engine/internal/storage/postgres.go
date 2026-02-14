package storage

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"time"

	_ "github.com/lib/pq"
	"github.com/reshwanthmanupati/NetWeaver/services/intent-engine/internal/engine"
)

// PostgresStorage implements the Storage interface using PostgreSQL
type PostgresStorage struct {
	db *sql.DB
}

// DBConfig configuration for PostgreSQL connection
type DBConfig struct {
	Host     string
	Port     string
	Database string
	User     string
	Password string
}

// NewPostgresStorage creates a new PostgreSQL storage instance
func NewPostgresStorage(config DBConfig) (*PostgresStorage, error) {
	connStr := fmt.Sprintf(
		"host=%s port=%s user=%s password=%s dbname=%s sslmode=disable",
		config.Host, config.Port, config.User, config.Password, config.Database,
	)

	db, err := sql.Open("postgres", connStr)
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}

	if err := db.Ping(); err != nil {
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	// Set connection pool settings
	db.SetMaxOpenConns(25)
	db.SetMaxIdleConns(5)
	db.SetConnMaxLifetime(5 * time.Minute)

	storage := &PostgresStorage{db: db}

	// Initialize schema
	if err := storage.initSchema(); err != nil {
		return nil, fmt.Errorf("failed to initialize schema: %w", err)
	}

	return storage, nil
}

func (s *PostgresStorage) initSchema() error {
	schema := `
	CREATE TABLE IF NOT EXISTS intents (
		id VARCHAR(255) PRIMARY KEY,
		name VARCHAR(255) NOT NULL,
		description TEXT,
		priority INTEGER DEFAULT 100,
		policy JSONB NOT NULL,
		targets JSONB NOT NULL,
		status VARCHAR(50) DEFAULT 'draft',
		created_at TIMESTAMP NOT NULL,
		updated_at TIMESTAMP NOT NULL,
		deployed_at TIMESTAMP,
		created_by VARCHAR(255),
		metadata JSONB
	);

	CREATE INDEX IF NOT EXISTS idx_intents_status ON intents(status);
	CREATE INDEX IF NOT EXISTS idx_intents_created_at ON intents(created_at DESC);
	CREATE INDEX IF NOT EXISTS idx_intents_priority ON intents(priority DESC);

	CREATE TABLE IF NOT EXISTS deployments (
		id VARCHAR(255) PRIMARY KEY,
		intent_id VARCHAR(255) NOT NULL REFERENCES intents(id) ON DELETE CASCADE,
		device_id VARCHAR(255) NOT NULL,
		vendor VARCHAR(100) NOT NULL,
		configuration TEXT NOT NULL,
		status VARCHAR(50) DEFAULT 'pending',
		deployed_at TIMESTAMP NOT NULL,
		error TEXT,
		metadata JSONB,
		FOREIGN KEY (intent_id) REFERENCES intents(id)
	);

	CREATE INDEX IF NOT EXISTS idx_deployments_intent_id ON deployments(intent_id);
	CREATE INDEX IF NOT EXISTS idx_deployments_device_id ON deployments(device_id);
	CREATE INDEX IF NOT EXISTS idx_deployments_status ON deployments(status);
	`

	_, err := s.db.Exec(schema)
	return err
}

// SaveIntent saves a new intent
func (s *PostgresStorage) SaveIntent(intent *engine.Intent) error {
	policyJSON, err := json.Marshal(intent.Policy)
	if err != nil {
		return fmt.Errorf("failed to marshal policy: %w", err)
	}

	targetsJSON, err := json.Marshal(intent.Targets)
	if err != nil {
		return fmt.Errorf("failed to marshal targets: %w", err)
	}

	metadataJSON, err := json.Marshal(intent.Metadata)
	if err != nil {
		return fmt.Errorf("failed to marshal metadata: %w", err)
	}

	query := `
		INSERT INTO intents (id, name, description, priority, policy, targets, status, created_at, updated_at, deployed_at, created_by, metadata)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
	`

	_, err = s.db.Exec(query,
		intent.ID, intent.Name, intent.Description, intent.Priority,
		policyJSON, targetsJSON, intent.Status,
		intent.CreatedAt, intent.UpdatedAt, intent.DeployedAt,
		intent.CreatedBy, metadataJSON,
	)

	return err
}

// GetIntent retrieves an intent by ID
func (s *PostgresStorage) GetIntent(id string) (*engine.Intent, error) {
	query := `
		SELECT id, name, description, priority, policy, targets, status, created_at, updated_at, deployed_at, created_by, metadata
		FROM intents
		WHERE id = $1
	`

	row := s.db.QueryRow(query, id)

	var intent engine.Intent
	var policyJSON, targetsJSON, metadataJSON []byte
	var deployedAt sql.NullTime

	err := row.Scan(
		&intent.ID, &intent.Name, &intent.Description, &intent.Priority,
		&policyJSON, &targetsJSON, &intent.Status,
		&intent.CreatedAt, &intent.UpdatedAt, &deployedAt,
		&intent.CreatedBy, &metadataJSON,
	)
	if err != nil {
		return nil, err
	}

	if deployedAt.Valid {
		intent.DeployedAt = &deployedAt.Time
	}

	if err := json.Unmarshal(policyJSON, &intent.Policy); err != nil {
		return nil, fmt.Errorf("failed to unmarshal policy: %w", err)
	}

	if err := json.Unmarshal(targetsJSON, &intent.Targets); err != nil {
		return nil, fmt.Errorf("failed to unmarshal targets: %w", err)
	}

	if len(metadataJSON) > 0 {
		if err := json.Unmarshal(metadataJSON, &intent.Metadata); err != nil {
			return nil, fmt.Errorf("failed to unmarshal metadata: %w", err)
		}
	}

	return &intent, nil
}

// ListIntents retrieves intents with optional filtering
func (s *PostgresStorage) ListIntents(filters map[string]interface{}) ([]*engine.Intent, error) {
	query := "SELECT id, name, description, priority, policy, targets, status, created_at, updated_at, deployed_at, created_by, metadata FROM intents WHERE 1=1"
	args := []interface{}{}
	argCount := 1

	if status, ok := filters["status"].(string); ok {
		query += fmt.Sprintf(" AND status = $%d", argCount)
		args = append(args, status)
		argCount++
	}

	if policyType, ok := filters["type"].(string); ok {
		query += fmt.Sprintf(" AND policy->>'type' = $%d", argCount)
		args = append(args, policyType)
		argCount++
	}

	query += " ORDER BY priority DESC, created_at DESC"

	rows, err := s.db.Query(query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	intents := []*engine.Intent{}

	for rows.Next() {
		var intent engine.Intent
		var policyJSON, targetsJSON, metadataJSON []byte
		var deployedAt sql.NullTime

		err := rows.Scan(
			&intent.ID, &intent.Name, &intent.Description, &intent.Priority,
			&policyJSON, &targetsJSON, &intent.Status,
			&intent.CreatedAt, &intent.UpdatedAt, &deployedAt,
			&intent.CreatedBy, &metadataJSON,
		)
		if err != nil {
			return nil, err
		}

		if deployedAt.Valid {
			intent.DeployedAt = &deployedAt.Time
		}

		if err := json.Unmarshal(policyJSON, &intent.Policy); err != nil {
			continue
		}

		if err := json.Unmarshal(targetsJSON, &intent.Targets); err != nil {
			continue
		}

		if len(metadataJSON) > 0 {
			json.Unmarshal(metadataJSON, &intent.Metadata)
		}

		intents = append(intents, &intent)
	}

	return intents, nil
}

// UpdateIntent updates an existing intent
func (s *PostgresStorage) UpdateIntent(intent *engine.Intent) error {
	policyJSON, err := json.Marshal(intent.Policy)
	if err != nil {
		return err
	}

	targetsJSON, err := json.Marshal(intent.Targets)
	if err != nil {
		return err
	}

	metadataJSON, err := json.Marshal(intent.Metadata)
	if err != nil {
		return err
	}

	intent.UpdatedAt = time.Now()

	query := `
		UPDATE intents
		SET name = $2, description = $3, priority = $4, policy = $5, targets = $6, status = $7, updated_at = $8, deployed_at = $9, metadata = $10
		WHERE id = $1
	`

	_, err = s.db.Exec(query,
		intent.ID, intent.Name, intent.Description, intent.Priority,
		policyJSON, targetsJSON, intent.Status, intent.UpdatedAt,
		intent.DeployedAt, metadataJSON,
	)

	return err
}

// DeleteIntent deletes an intent
func (s *PostgresStorage) DeleteIntent(id string) error {
	query := "DELETE FROM intents WHERE id = $1"
	_, err := s.db.Exec(query, id)
	return err
}

// SaveDeployment saves a deployment record
func (s *PostgresStorage) SaveDeployment(deployment *engine.Deployment) error {
	metadataJSON, err := json.Marshal(deployment.Metadata)
	if err != nil {
		return err
	}

	query := `
		INSERT INTO deployments (id, intent_id, device_id, vendor, configuration, status, deployed_at, error, metadata)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
	`

	_, err = s.db.Exec(query,
		deployment.ID, deployment.IntentID, deployment.DeviceID, deployment.Vendor,
		deployment.Configuration, deployment.Status, deployment.DeployedAt,
		deployment.Error, metadataJSON,
	)

	return err
}

// GetDeployments retrieves deployment history for an intent
func (s *PostgresStorage) GetDeployments(intentID string) ([]*engine.Deployment, error) {
	query := `
		SELECT id, intent_id, device_id, vendor, configuration, status, deployed_at, error, metadata
		FROM deployments
		WHERE intent_id = $1
		ORDER BY deployed_at DESC
	`

	rows, err := s.db.Query(query, intentID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	deployments := []*engine.Deployment{}

	for rows.Next() {
		var deployment engine.Deployment
		var metadataJSON []byte
		var errorStr sql.NullString

		err := rows.Scan(
			&deployment.ID, &deployment.IntentID, &deployment.DeviceID, &deployment.Vendor,
			&deployment.Configuration, &deployment.Status, &deployment.DeployedAt,
			&errorStr, &metadataJSON,
		)
		if err != nil {
			return nil, err
		}

		if errorStr.Valid {
			deployment.Error = errorStr.String
		}

		if len(metadataJSON) > 0 {
			json.Unmarshal(metadataJSON, &deployment.Metadata)
		}

		deployments = append(deployments, &deployment)
	}

	return deployments, nil
}

// Close closes the database connection
func (s *PostgresStorage) Close() error {
	return s.db.Close()
}
