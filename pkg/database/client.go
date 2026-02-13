// Package database provides TimescaleDB connectivity and operations
package database

import (
	"context"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// Config holds database configuration
type Config struct {
	Host     string
	Port     int
	Database string
	User     string
	Password string
	PoolSize int
}

// Client represents a database client
type Client struct {
	pool *pgxpool.Pool
	ctx  context.Context
}

// NewClient creates a new database client
func NewClient(ctx context.Context, config Config) (*Client, error) {
	// Build connection string
	connString := fmt.Sprintf(
		"host=%s port=%d dbname=%s user=%s password=%s pool_max_conns=%d",
		config.Host, config.Port, config.Database, config.User, config.Password, config.PoolSize,
	)

	// Create connection pool
	poolConfig, err := pgxpool.ParseConfig(connString)
	if err != nil {
		return nil, fmt.Errorf("failed to parse config: %w", err)
	}

	// Configure pool settings
	poolConfig.MaxConns = int32(config.PoolSize)
	poolConfig.MinConns = int32(config.PoolSize / 4)
	poolConfig.MaxConnLifetime = time.Hour
	poolConfig.MaxConnIdleTime = time.Minute * 30
	poolConfig.HealthCheckPeriod = time.Minute

	pool, err := pgxpool.NewWithConfig(ctx, poolConfig)
	if err != nil {
		return nil, fmt.Errorf("failed to create pool: %w", err)
	}

	// Test connection
	if err := pool.Ping(ctx); err != nil {
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	return &Client{
		pool: pool,
		ctx:  ctx,
	}, nil
}

// Close closes the database connection pool
func (c *Client) Close() {
	c.pool.Close()
}

// FlowRecordDB represents a flow record for database insertion
type FlowRecordDB struct {
	Time            time.Time
	ExporterIP      string
	SourceIP        string
	DestinationIP   string
	SourcePort      int32
	DestPort        int32
	Protocol        int32
	Bytes           int64
	Packets         int64
	TCPFlags        int32
	ToS             int32
	InputInterface  int32
	OutputInterface int32
	NextHopIP       string
	SourceAS        int32
	DestAS          int32
	FlowDuration    int32
	SamplingRate    int32
}

// InsertFlowRecords inserts flow records into the database using batch insert
func (c *Client) InsertFlowRecords(records []FlowRecordDB) error {
	if len(records) == 0 {
		return nil
	}

	// Use COPY for high-performance bulk inserts
	conn, err := c.pool.Acquire(c.ctx)
	if err != nil {
		return fmt.Errorf("failed to acquire connection: %w", err)
	}
	defer conn.Release()

	// Prepare column names
	columns := []string{
		"time", "exporter_ip", "source_ip", "destination_ip",
		"source_port", "destination_port", "protocol", "bytes", "packets",
		"tcp_flags", "tos", "input_interface", "output_interface",
		"next_hop_ip", "source_as", "destination_as", "flow_duration_ms", "sampling_rate",
	}

	// Use CopyFrom for optimal performance
	_, err = conn.Conn().CopyFrom(
		c.ctx,
		pgx.Identifier{"flow_records"},
		columns,
		pgx.CopyFromSlice(len(records), func(i int) ([]interface{}, error) {
			r := records[i]
			return []interface{}{
				r.Time, r.ExporterIP, r.SourceIP, r.DestinationIP,
				r.SourcePort, r.DestPort, r.Protocol, r.Bytes, r.Packets,
				r.TCPFlags, r.ToS, r.InputInterface, r.OutputInterface,
				r.NextHopIP, r.SourceAS, r.DestAS, r.FlowDuration, r.SamplingRate,
			}, nil
		}),
	)

	if err != nil {
		return fmt.Errorf("failed to insert flow records: %w", err)
	}

	return nil
}

// InterfaceMetricDB represents interface metrics for database insertion
type InterfaceMetricDB struct {
	Time                     time.Time
	DeviceID                 string
	InterfaceID              string
	BytesIn                  int64
	BytesOut                 int64
	PacketsIn                int64
	PacketsOut               int64
	ErrorsIn                 int64
	ErrorsOut                int64
	DiscardsIn               int64
	DiscardsOut              int64
	UtilizationPercent       float64
	BandwidthUtilizationPercent float64
}

// InsertInterfaceMetrics inserts interface metrics into the database
func (c *Client) InsertInterfaceMetrics(metrics []InterfaceMetricDB) error {
	if len(metrics) == 0 {
		return nil
	}

	conn, err := c.pool.Acquire(c.ctx)
	if err != nil {
		return fmt.Errorf("failed to acquire connection: %w", err)
	}
	defer conn.Release()

	columns := []string{
		"time", "device_id", "interface_id", "bytes_in", "bytes_out",
		"packets_in", "packets_out", "errors_in", "errors_out",
		"discards_in", "discards_out", "utilization_percent", "bandwidth_utilization_percent",
	}

	_, err = conn.Conn().CopyFrom(
		c.ctx,
		pgx.Identifier{"interface_metrics"},
		columns,
		pgx.CopyFromSlice(len(metrics), func(i int) ([]interface{}, error) {
			m := metrics[i]
			return []interface{}{
				m.Time, m.DeviceID, m.InterfaceID, m.BytesIn, m.BytesOut,
				m.PacketsIn, m.PacketsOut, m.ErrorsIn, m.ErrorsOut,
				m.DiscardsIn, m.DiscardsOut, m.UtilizationPercent, m.BandwidthUtilizationPercent,
			}, nil
		}),
	)

	if err != nil {
		return fmt.Errorf("failed to insert interface metrics: %w", err)
	}

	return nil
}

// GetTopTalkers retrieves the top N traffic sources
func (c *Client) GetTopTalkers(startTime, endTime time.Time, limit int) ([]TopTalker, error) {
	query := `
		SELECT 
			source_ip,
			SUM(bytes) AS total_bytes,
			SUM(packets) AS total_packets,
			COUNT(*) AS flow_count
		FROM flow_records
		WHERE time BETWEEN $1 AND $2
		GROUP BY source_ip
		ORDER BY total_bytes DESC
		LIMIT $3
	`

	rows, err := c.pool.Query(c.ctx, query, startTime, endTime, limit)
	if err != nil {
		return nil, fmt.Errorf("failed to query top talkers: %w", err)
	}
	defer rows.Close()

	var results []TopTalker
	for rows.Next() {
		var tt TopTalker
		if err := rows.Scan(&tt.SourceIP, &tt.TotalBytes, &tt.TotalPackets, &tt.FlowCount); err != nil {
			return nil, fmt.Errorf("failed to scan row: %w", err)
		}
		results = append(results, tt)
	}

	return results, rows.Err()
}

// TopTalker represents a top traffic source
type TopTalker struct {
	SourceIP     string
	TotalBytes   int64
	TotalPackets int64
	FlowCount    int64
}

// GetFlowAggregates retrieves aggregated flow statistics
func (c *Client) GetFlowAggregates(startTime, endTime time.Time) (*FlowAggregates, error) {
	query := `
		SELECT 
			COUNT(*) AS flow_count,
			SUM(bytes) AS total_bytes,
			SUM(packets) AS total_packets,
			COUNT(DISTINCT source_ip) AS unique_sources,
			COUNT(DISTINCT destination_ip) AS unique_destinations,
			COUNT(DISTINCT protocol) AS unique_protocols
		FROM flow_records
		WHERE time BETWEEN $1 AND $2
	`

	var agg FlowAggregates
	err := c.pool.QueryRow(c.ctx, query, startTime, endTime).Scan(
		&agg.FlowCount, &agg.TotalBytes, &agg.TotalPackets,
		&agg.UniqueSources, &agg.UniqueDestinations, &agg.UniqueProtocols,
	)

	if err != nil {
		return nil, fmt.Errorf("failed to query aggregates: %w", err)
	}

	return &agg, nil
}

// FlowAggregates represents aggregated flow statistics
type FlowAggregates struct {
	FlowCount           int64
	TotalBytes          int64
	TotalPackets        int64
	UniqueSources       int64
	UniqueDestinations  int64
	UniqueProtocols     int64
}

// GetProtocolDistribution retrieves traffic distribution by protocol
func (c *Client) GetProtocolDistribution(startTime, endTime time.Time) ([]ProtocolStats, error) {
	query := `
		SELECT 
			protocol,
			SUM(bytes) AS total_bytes,
			SUM(packets) AS total_packets,
			COUNT(*) AS flow_count
		FROM flow_records
		WHERE time BETWEEN $1 AND $2
		GROUP BY protocol
		ORDER BY total_bytes DESC
	`

	rows, err := c.pool.Query(c.ctx, query, startTime, endTime)
	if err != nil {
		return nil, fmt.Errorf("failed to query protocol distribution: %w", err)
	}
	defer rows.Close()

	var results []ProtocolStats
	for rows.Next() {
		var ps ProtocolStats
		if err := rows.Scan(&ps.Protocol, &ps.TotalBytes, &ps.TotalPackets, &ps.FlowCount); err != nil {
			return nil, fmt.Errorf("failed to scan row: %w", err)
		}
		results = append(results, ps)
	}

	return results, rows.Err()
}

// ProtocolStats represents statistics for a specific protocol
type ProtocolStats struct {
	Protocol     int32
	TotalBytes   int64
	TotalPackets int64
	FlowCount    int64
}

// HealthCheck performs a database health check
func (c *Client) HealthCheck() error {
	return c.pool.Ping(c.ctx)
}

// GetStats returns connection pool statistics
func (c *Client) GetStats() *pgxpool.Stat {
	return c.pool.Stat()
}
