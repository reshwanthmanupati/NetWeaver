package storage

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"time"

	_ "github.com/lib/pq"
)

// Storage interface for self-healing persistence
type Storage interface {
	SaveIncident(incident *Incident) error
	GetIncident(id string) (*Incident, error)
	ListIncidents(filters map[string]interface{}) ([]*Incident, error)
	UpdateIncident(incident *Incident) error
	ResolveIncident(id, resolution, resolvedBy string) error
	
	SaveRemediationAction(incidentID string, action *RemediationAction) error
	GetRemediationActions(incidentID string) ([]*RemediationAction, error)
	
	GetStatistics() (map[string]interface{}, error)
	GetMTTR(period time.Duration) (time.Duration, error)
}

// PostgresStorage implements Storage using PostgreSQL
type PostgresStorage struct {
	db *sql.DB
}

// DBConfig database configuration
type DBConfig struct {
	Host     string
	Port     string
	Database string
	User     string
	Password string
}

// Incident represents a network incident
type Incident struct {
	ID              string                 `json:"id"`
	Type            string                 `json:"type"`
	DeviceID        string                 `json:"device_id"`
	Severity        string                 `json:"severity"`
	Status          string                 `json:"status"`
	DetectedAt      time.Time              `json:"detected_at"`
	RemediatedAt    time.Time              `json:"remediated_at,omitempty"`
	ResolvedAt      time.Time              `json:"resolved_at,omitempty"`
	RolledBackAt    time.Time              `json:"rolled_back_at,omitempty"`
	ResolutionTime  time.Duration          `json:"resolution_time,omitempty"`
	Details         map[string]interface{} `json:"details"`
	Error           string                 `json:"error,omitempty"`
	Resolution      string                 `json:"resolution,omitempty"`
	ResolvedBy      string                 `json:"resolved_by,omitempty"`
}

// RemediationAction represents a remediation action taken
type RemediationAction struct {
	Type       string                 `json:"type"`
	DeviceID   string                 `json:"device_id"`
	Config     string                 `json:"config"`
	Parameters map[string]interface{} `json:"parameters"`
	CreatedAt  time.Time              `json:"created_at"`
}

// NewPostgresStorage creates a new PostgreSQL storage
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
	-- Incidents table
	CREATE TABLE IF NOT EXISTS incidents (
		id VARCHAR(255) PRIMARY KEY,
		type VARCHAR(100) NOT NULL,
		device_id VARCHAR(255) NOT NULL,
		severity VARCHAR(50) NOT NULL,
		status VARCHAR(50) NOT NULL,
		detected_at TIMESTAMP NOT NULL,
		remediated_at TIMESTAMP,
		resolved_at TIMESTAMP,
		rolled_back_at TIMESTAMP,
		resolution_time_seconds FLOAT,
		details JSONB,
		error TEXT,
		resolution TEXT,
		resolved_by VARCHAR(255),
		created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
	);

	CREATE INDEX IF NOT EXISTS idx_incidents_device_id ON incidents(device_id);
	CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
	CREATE INDEX IF NOT EXISTS idx_incidents_type ON incidents(type);
	CREATE INDEX IF NOT EXISTS idx_incidents_detected_at ON incidents(detected_at DESC);
	CREATE INDEX IF NOT EXISTS idx_incidents_severity ON incidents(severity);

	-- Remediation actions table
	CREATE TABLE IF NOT EXISTS remediation_actions (
		id SERIAL PRIMARY KEY,
		incident_id VARCHAR(255) NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
		type VARCHAR(100) NOT NULL,
		device_id VARCHAR(255) NOT NULL,
		config TEXT,
		parameters JSONB,
		created_at TIMESTAMP NOT NULL,
		status VARCHAR(50) DEFAULT 'pending',
		error TEXT
	);

	CREATE INDEX IF NOT EXISTS idx_remediation_incident_id ON remediation_actions(incident_id);
	CREATE INDEX IF NOT EXISTS idx_remediation_device_id ON remediation_actions(device_id);
	CREATE INDEX IF NOT EXISTS idx_remediation_type ON remediation_actions(type);
	`

	_, err := s.db.Exec(schema)
	return err
}

// SaveIncident saves a new incident
func (s *PostgresStorage) SaveIncident(incident *Incident) error {
	if incident.ID == "" {
		incident.ID = fmt.Sprintf("incident-%d", time.Now().UnixNano())
	}

	detailsJSON, err := json.Marshal(incident.Details)
	if err != nil {
		return err
	}

	query := `
		INSERT INTO incidents (
			id, type, device_id, severity, status, detected_at, details
		) VALUES ($1, $2, $3, $4, $5, $6, $7)
	`

	_, err = s.db.Exec(query,
		incident.ID,
		incident.Type,
		incident.DeviceID,
		incident.Severity,
		incident.Status,
		incident.DetectedAt,
		detailsJSON,
	)

	return err
}

// GetIncident retrieves an incident by ID
func (s *PostgresStorage) GetIncident(id string) (*Incident, error) {
	query := `
		SELECT id, type, device_id, severity, status, detected_at, 
		       remediated_at, resolved_at, rolled_back_at, resolution_time_seconds,
		       details, error, resolution, resolved_by
		FROM incidents
		WHERE id = $1
	`

	var incident Incident
	var detailsJSON []byte
	var remediatedAt, resolvedAt, rolledBackAt sql.NullTime
	var resolutionTime sql.NullFloat64
	var err, resolution, resolvedBy sql.NullString

	scanErr := s.db.QueryRow(query, id).Scan(
		&incident.ID,
		&incident.Type,
		&incident.DeviceID,
		&incident.Severity,
		&incident.Status,
		&incident.DetectedAt,
		&remediatedAt,
		&resolvedAt,
		&rolledBackAt,
		&resolutionTime,
		&detailsJSON,
		&err,
		&resolution,
		&resolvedBy,
	)

	if scanErr != nil {
		return nil, scanErr
	}

	if remediatedAt.Valid {
		incident.RemediatedAt = remediatedAt.Time
	}
	if resolvedAt.Valid {
		incident.ResolvedAt = resolvedAt.Time
	}
	if rolledBackAt.Valid {
		incident.RolledBackAt = rolledBackAt.Time
	}
	if resolutionTime.Valid {
		incident.ResolutionTime = time.Duration(resolutionTime.Float64 * float64(time.Second))
	}
	if err.Valid {
		incident.Error = err.String
	}
	if resolution.Valid {
		incident.Resolution = resolution.String
	}
	if resolvedBy.Valid {
		incident.ResolvedBy = resolvedBy.String
	}

	if err := json.Unmarshal(detailsJSON, &incident.Details); err != nil {
		return nil, err
	}

	return &incident, nil
}

// ListIncidents lists incidents with optional filters
func (s *PostgresStorage) ListIncidents(filters map[string]interface{}) ([]*Incident, error) {
	query := "SELECT id, type, device_id, severity, status, detected_at, details FROM incidents"
	args := []interface{}{}
	conditions := []string{}
	argIndex := 1

	if status, ok := filters["status"].(string); ok && status != "" {
		conditions = append(conditions, fmt.Sprintf("status = $%d", argIndex))
		args = append(args, status)
		argIndex++
	}

	if deviceID, ok := filters["device_id"].(string); ok && deviceID != "" {
		conditions = append(conditions, fmt.Sprintf("device_id = $%d", argIndex))
		args = append(args, deviceID)
		argIndex++
	}

	if len(conditions) > 0 {
		query += " WHERE " + conditions[0]
		for i := 1; i < len(conditions); i++ {
			query += " AND " + conditions[i]
		}
	}

	query += " ORDER BY detected_at DESC"

	if limitStr, ok := filters["limit"].(string); ok && limitStr != "" {
		// Parameterize LIMIT to prevent SQL injection
		query += fmt.Sprintf(" LIMIT $%d", argIndex)
		args = append(args, limitStr)
	} else {
		query += " LIMIT 100"
	}

	rows, err := s.db.Query(query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	incidents := []*Incident{}
	for rows.Next() {
		var incident Incident
		var detailsJSON []byte

		if err := rows.Scan(
			&incident.ID,
			&incident.Type,
			&incident.DeviceID,
			&incident.Severity,
			&incident.Status,
			&incident.DetectedAt,
			&detailsJSON,
		); err != nil {
			return nil, err
		}

		if err := json.Unmarshal(detailsJSON, &incident.Details); err != nil {
			return nil, err
		}

		incidents = append(incidents, &incident)
	}

	return incidents, nil
}

// UpdateIncident updates an existing incident
func (s *PostgresStorage) UpdateIncident(incident *Incident) error {
	detailsJSON, err := json.Marshal(incident.Details)
	if err != nil {
		return err
	}

	var resolutionTime *float64
	if incident.ResolutionTime > 0 {
		seconds := incident.ResolutionTime.Seconds()
		resolutionTime = &seconds
	}

	query := `
		UPDATE incidents SET
			status = $1,
			remediated_at = $2,
			resolved_at = $3,
			rolled_back_at = $4,
			resolution_time_seconds = $5,
			details = $6,
			error = $7,
			resolution = $8,
			resolved_by = $9
		WHERE id = $10
	`

	_, err = s.db.Exec(query,
		incident.Status,
		nullTime(incident.RemediatedAt),
		nullTime(incident.ResolvedAt),
		nullTime(incident.RolledBackAt),
		resolutionTime,
		detailsJSON,
		nullString(incident.Error),
		nullString(incident.Resolution),
		nullString(incident.ResolvedBy),
		incident.ID,
	)

	return err
}

// ResolveIncident marks an incident as resolved
func (s *PostgresStorage) ResolveIncident(id, resolution, resolvedBy string) error {
	query := `
		UPDATE incidents SET
			status = 'resolved',
			resolved_at = $1,
			resolution = $2,
			resolved_by = $3
		WHERE id = $4
	`

	_, err := s.db.Exec(query, time.Now(), resolution, resolvedBy, id)
	return err
}

// SaveRemediationAction saves a remediation action
func (s *PostgresStorage) SaveRemediationAction(incidentID string, action *RemediationAction) error {
	parametersJSON, err := json.Marshal(action.Parameters)
	if err != nil {
		return err
	}

	query := `
		INSERT INTO remediation_actions (
			incident_id, type, device_id, config, parameters, created_at, status
		) VALUES ($1, $2, $3, $4, $5, $6, 'completed')
	`

	_, err = s.db.Exec(query, incidentID, action.Type, action.DeviceID, action.Config, parametersJSON, action.CreatedAt)
	return err
}

// GetRemediationActions retrieves all remediation actions for an incident
func (s *PostgresStorage) GetRemediationActions(incidentID string) ([]*RemediationAction, error) {
	query := `
		SELECT type, device_id, config, parameters, created_at
		FROM remediation_actions
		WHERE incident_id = $1
		ORDER BY created_at ASC
	`

	rows, err := s.db.Query(query, incidentID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	actions := []*RemediationAction{}
	for rows.Next() {
		var actionType, deviceID, config string
		var parametersJSON []byte
		var createdAt time.Time

		if err := rows.Scan(&actionType, &deviceID, &config, &parametersJSON, &createdAt); err != nil {
			return nil, err
		}

		var parameters map[string]interface{}
		if err := json.Unmarshal(parametersJSON, &parameters); err != nil {
			return nil, err
		}

		action := &RemediationAction{
			Type:       actionType,
			DeviceID:   deviceID,
			Config:     config,
			Parameters: parameters,
			CreatedAt:  createdAt,
		}

		actions = append(actions, action)
	}

	return actions, nil
}

// GetStatistics returns incident statistics
func (s *PostgresStorage) GetStatistics() (map[string]interface{}, error) {
	query := `
		SELECT 
			COUNT(*) as total,
			COUNT(*) FILTER (WHERE status = 'detected') as detected,
			COUNT(*) FILTER (WHERE status = 'remediating') as remediating,
			COUNT(*) FILTER (WHERE status = 'remediated') as remediated,
			COUNT(*) FILTER (WHERE status = 'resolved') as resolved,
			COUNT(*) FILTER (WHERE status = 'failed') as failed,
			COUNT(*) FILTER (WHERE severity = 'critical') as critical,
			COUNT(*) FILTER (WHERE severity = 'high') as high,
			COUNT(*) FILTER (WHERE severity = 'medium') as medium,
			AVG(resolution_time_seconds) FILTER (WHERE resolution_time_seconds IS NOT NULL) as avg_mttr
		FROM incidents
		WHERE detected_at > NOW() - INTERVAL '24 hours'
	`

	var stats struct {
		Total       int
		Detected    int
		Remediating int
		Remediated  int
		Resolved    int
		Failed      int
		Critical    int
		High        int
		Medium      int
		AvgMTTR     sql.NullFloat64
	}

	err := s.db.QueryRow(query).Scan(
		&stats.Total,
		&stats.Detected,
		&stats.Remediating,
		&stats.Remediated,
		&stats.Resolved,
		&stats.Failed,
		&stats.Critical,
		&stats.High,
		&stats.Medium,
		&stats.AvgMTTR,
	)

	if err != nil {
		return nil, err
	}

	result := map[string]interface{}{
		"total_incidents":  stats.Total,
		"by_status": map[string]int{
			"detected":    stats.Detected,
			"remediating": stats.Remediating,
			"remediated":  stats.Remediated,
			"resolved":    stats.Resolved,
			"failed":      stats.Failed,
		},
		"by_severity": map[string]int{
			"critical": stats.Critical,
			"high":     stats.High,
			"medium":   stats.Medium,
		},
	}

	if stats.AvgMTTR.Valid {
		result["avg_mttr_seconds"] = stats.AvgMTTR.Float64
		result["avg_mttr"] = fmt.Sprintf("%.2fs", stats.AvgMTTR.Float64)
	}

	return result, nil
}

// GetMTTR calculates Mean Time To Resolution for a given period
func (s *PostgresStorage) GetMTTR(period time.Duration) (time.Duration, error) {
	// Convert Go duration to seconds for PostgreSQL interval
	periodSeconds := int(period.Seconds())
	query := `
		SELECT AVG(resolution_time_seconds)
		FROM incidents
		WHERE resolution_time_seconds IS NOT NULL
		  AND detected_at > NOW() - make_interval(secs => $1)
	`

	var avgSeconds sql.NullFloat64
	err := s.db.QueryRow(query, periodSeconds).Scan(&avgSeconds)
	
	if err != nil {
		return 0, err
	}

	if !avgSeconds.Valid {
		return 0, nil
	}

	return time.Duration(avgSeconds.Float64 * float64(time.Second)), nil
}

// Helper functions

func nullTime(t time.Time) interface{} {
	if t.IsZero() {
		return nil
	}
	return t
}

func nullString(s string) interface{} {
	if s == "" {
		return nil
	}
	return s
}

// Close closes the database connection
func (s *PostgresStorage) Close() error {
	return s.db.Close()
}
