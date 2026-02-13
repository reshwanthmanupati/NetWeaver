// Telemetry Agent - High-performance NetFlow/sFlow collector
// Production-grade collector with concurrent processing and buffering
package main

import (
	"context"
	"flag"
	"fmt"
	"net"
	"os"
	"os/signal"
	"sync"
	"sync/atomic"
	"syscall"
	"time"

	"github.com/netweaver/netweaver/pkg/database"
	"github.com/netweaver/netweaver/pkg/netflow"
	"github.com/netweaver/netweaver/pkg/sflow"
	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"
	"gopkg.in/yaml.v3"
)

// Config represents the telemetry agent configuration
type Config struct {
	Collectors struct {
		NetFlow struct {
			Listen  string `yaml:"listen"`
			Workers int    `yaml:"workers"`
			Enabled bool   `yaml:"enabled"`
		} `yaml:"netflow"`
		SFlow struct {
			Listen  string `yaml:"listen"`
			Workers int    `yaml:"workers"`
			Enabled bool   `yaml:"enabled"`
		} `yaml:"sflow"`
	} `yaml:"collectors"`
	Database struct {
		Host     string `yaml:"host"`
		Port     int    `yaml:"port"`
		Database string `yaml:"database"`
		User     string `yaml:"user"`
		Password string `yaml:"password"`
		PoolSize int    `yaml:"pool_size"`
	} `yaml:"database"`
	Performance struct {
		BufferSize    int `yaml:"buffer_size"`     // Number of records to buffer before database insert
		FlushInterval int `yaml:"flush_interval"`  // Seconds between forced flushes
		UDPBufferSize int `yaml:"udp_buffer_size"` // OS UDP receive buffer size
	} `yaml:"performance"`
	Monitoring struct {
		StatsInterval int  `yaml:"stats_interval"` // Seconds between stats logging
		PrometheusPort int  `yaml:"prometheus_port"`
		Enabled       bool `yaml:"enabled"`
	} `yaml:"monitoring"`
}

// TelemetryAgent is the main agent structure
type TelemetryAgent struct {
	config         Config
	logger         *zap.Logger
	dbClient       *database.Client
	netflowParser  *netflow.Parser
	sflowParser    *sflow.Parser
	flowBuffer     chan database.FlowRecordDB
	wg             sync.WaitGroup
	ctx            context.Context
	cancel         context.CancelFunc
	
	// Statistics
	packetsReceived   atomic.Uint64
	flowsProcessed    atomic.Uint64
	dbInsertsSuccess  atomic.Uint64
	dbInsertsFailed   atomic.Uint64
	parseErrors       atomic.Uint64
}

// NewTelemetryAgent creates a new telemetry agent
func NewTelemetryAgent(config Config) (*TelemetryAgent, error) {
	// Create logger
	loggerConfig := zap.NewProductionConfig()
	loggerConfig.EncoderConfig.TimeKey = "timestamp"
	loggerConfig.EncoderConfig.EncodeTime = zapcore.ISO8601TimeEncoder
	logger, err := loggerConfig.Build()
	if err != nil {
		return nil, fmt.Errorf("failed to create logger: %w", err)
	}

	// Create context
	ctx, cancel := context.WithCancel(context.Background())

	// Create database client
	dbConfig := database.Config{
		Host:     config.Database.Host,
		Port:     config.Database.Port,
		Database: config.Database.Database,
		User:     config.Database.User,
		Password: config.Database.Password,
		PoolSize: config.Database.PoolSize,
	}

	dbClient, err := database.NewClient(ctx, dbConfig)
	if err != nil {
		cancel()
		return nil, fmt.Errorf("failed to create database client: %w", err)
	}

	agent := &TelemetryAgent{
		config:        config,
		logger:        logger,
		dbClient:      dbClient,
		netflowParser: netflow.NewParser(),
		sflowParser:   sflow.NewParser(),
		flowBuffer:    make(chan database.FlowRecordDB, config.Performance.BufferSize),
		ctx:           ctx,
		cancel:        cancel,
	}

	return agent, nil
}

// Start starts the telemetry agent
func (a *TelemetryAgent) Start() error {
	a.logger.Info("Starting NetWeaver Telemetry Agent",
		zap.String("version", "1.0.0"),
		zap.Int("netflow_workers", a.config.Collectors.NetFlow.Workers),
		zap.Int("sflow_workers", a.config.Collectors.SFlow.Workers),
		zap.Int("buffer_size", a.config.Performance.BufferSize),
	)

	// Start database writer
	a.wg.Add(1)
	go a.databaseWriter()

	// Start NetFlow collector
	if a.config.Collectors.NetFlow.Enabled {
		a.logger.Info("Starting NetFlow collector", zap.String("listen", a.config.Collectors.NetFlow.Listen))
		for i := 0; i < a.config.Collectors.NetFlow.Workers; i++ {
			a.wg.Add(1)
			go a.netflowCollector()
		}
	}

	// Start sFlow collector
	if a.config.Collectors.SFlow.Enabled {
		a.logger.Info("Starting sFlow collector", zap.String("listen", a.config.Collectors.SFlow.Listen))
		for i := 0; i < a.config.Collectors.SFlow.Workers; i++ {
			a.wg.Add(1)
			go a.sflowCollector()
		}
	}

	// Start statistics reporter
	if a.config.Monitoring.Enabled {
		a.wg.Add(1)
		go a.statsReporter()
	}

	a.logger.Info("Telemetry Agent started successfully")
	return nil
}

// netflowCollector receives and processes NetFlow packets
func (a *TelemetryAgent) netflowCollector() {
	defer a.wg.Done()

	// Create UDP listener
	addr, err := net.ResolveUDPAddr("udp", a.config.Collectors.NetFlow.Listen)
	if err != nil {
		a.logger.Error("Failed to resolve NetFlow address", zap.Error(err))
		return
	}

	conn, err := net.ListenUDP("udp", addr)
	if err != nil {
		a.logger.Error("Failed to listen for NetFlow", zap.Error(err))
		return
	}
	defer conn.Close()

	// Set UDP buffer size for high-throughput environments
	if a.config.Performance.UDPBufferSize > 0 {
		if err := conn.SetReadBuffer(a.config.Performance.UDPBufferSize); err != nil {
			a.logger.Warn("Failed to set UDP buffer size", zap.Error(err))
		}
	}

	buffer := make([]byte, 9000) // Support jumbo frames

	a.logger.Info("NetFlow collector listening", zap.String("address", addr.String()))

	for {
		select {
		case <-a.ctx.Done():
			return
		default:
			// Set read deadline to allow periodic context checking
			conn.SetReadDeadline(time.Now().Add(1 * time.Second))
			
			n, remoteAddr, err := conn.ReadFromUDP(buffer)
			if err != nil {
				if netErr, ok := err.(net.Error); ok && netErr.Timeout() {
					continue
				}
				a.logger.Error("Error reading NetFlow packet", zap.Error(err))
				continue
			}

			a.packetsReceived.Add(1)

			// Parse NetFlow packet
			flows, err := a.netflowParser.Parse(buffer[:n], remoteAddr.IP)
			if err != nil {
				a.parseErrors.Add(1)
				a.logger.Debug("Failed to parse NetFlow packet",
					zap.Error(err),
					zap.String("exporter", remoteAddr.IP.String()),
				)
				continue
			}

			// Convert and buffer flows
			for _, flow := range flows {
				dbRecord := database.FlowRecordDB{
					Time:            flow.Timestamp,
					ExporterIP:      flow.ExporterIP.String(),
					SourceIP:        flow.SourceIP.String(),
					DestinationIP:   flow.DestinationIP.String(),
					SourcePort:      int32(flow.SourcePort),
					DestPort:        int32(flow.DestPort),
					Protocol:        int32(flow.Protocol),
					Bytes:           int64(flow.Bytes),
					Packets:         int64(flow.Packets),
					TCPFlags:        int32(flow.TCPFlags),
					ToS:             int32(flow.ToS),
					InputInterface:  int32(flow.InputInterface),
					OutputInterface: int32(flow.OutputInterface),
					NextHopIP:       flow.NextHopIP.String(),
					SourceAS:        int32(flow.SourceAS),
					DestAS:          int32(flow.DestAS),
					FlowDuration:    int32(flow.FlowDuration),
					SamplingRate:    int32(flow.SamplingRate),
				}

				select {
				case a.flowBuffer <- dbRecord:
					a.flowsProcessed.Add(1)
				case <-a.ctx.Done():
					return
				default:
					// Buffer full, drop packet (or block - adjust based on requirements)
					a.logger.Warn("Flow buffer full, dropping flow")
				}
			}
		}
	}
}

// sflowCollector receives and processes sFlow packets
func (a *TelemetryAgent) sflowCollector() {
	defer a.wg.Done()

	addr, err := net.ResolveUDPAddr("udp", a.config.Collectors.SFlow.Listen)
	if err != nil {
		a.logger.Error("Failed to resolve sFlow address", zap.Error(err))
		return
	}

	conn, err := net.ListenUDP("udp", addr)
	if err != nil {
		a.logger.Error("Failed to listen for sFlow", zap.Error(err))
		return
	}
	defer conn.Close()

	if a.config.Performance.UDPBufferSize > 0 {
		if err := conn.SetReadBuffer(a.config.Performance.UDPBufferSize); err != nil {
			a.logger.Warn("Failed to set UDP buffer size", zap.Error(err))
		}
	}

	buffer := make([]byte, 9000)

	a.logger.Info("sFlow collector listening", zap.String("address", addr.String()))

	for {
		select {
		case <-a.ctx.Done():
			return
		default:
			conn.SetReadDeadline(time.Now().Add(1 * time.Second))
			
			n, remoteAddr, err := conn.ReadFromUDP(buffer)
			if err != nil {
				if netErr, ok := err.(net.Error); ok && netErr.Timeout() {
					continue
				}
				a.logger.Error("Error reading sFlow packet", zap.Error(err))
				continue
			}

			a.packetsReceived.Add(1)

			flows, err := a.sflowParser.Parse(buffer[:n])
			if err != nil {
				a.parseErrors.Add(1)
				a.logger.Debug("Failed to parse sFlow packet",
					zap.Error(err),
					zap.String("exporter", remoteAddr.IP.String()),
				)
				continue
			}

			// Convert and buffer flows
			for _, flow := range flows {
				dbRecord := database.FlowRecordDB{
					Time:            flow.Timestamp,
					ExporterIP:      flow.AgentIP.String(),
					SourceIP:        flow.SourceIP.String(),
					DestinationIP:   flow.DestinationIP.String(),
					SourcePort:      int32(flow.SourcePort),
					DestPort:        int32(flow.DestPort),
					Protocol:        int32(flow.Protocol),
					Bytes:           int64(flow.Bytes),
					Packets:         int64(flow.Packets),
					InputInterface:  int32(flow.InputInterface),
					OutputInterface: int32(flow.OutputInterface),
					SamplingRate:    int32(flow.SamplingRate),
				}

				select {
				case a.flowBuffer <- dbRecord:
					a.flowsProcessed.Add(1)
				case <-a.ctx.Done():
					return
				default:
					a.logger.Warn("Flow buffer full, dropping flow")
				}
			}
		}
	}
}

// databaseWriter batches and writes flows to the database
func (a *TelemetryAgent) databaseWriter() {
	defer a.wg.Done()

	batch := make([]database.FlowRecordDB, 0, a.config.Performance.BufferSize)
	ticker := time.NewTicker(time.Duration(a.config.Performance.FlushInterval) * time.Second)
	defer ticker.Stop()

	flush := func() {
		if len(batch) == 0 {
			return
		}

		if err := a.dbClient.InsertFlowRecords(batch); err != nil {
			a.dbInsertsFailed.Add(1)
			a.logger.Error("Failed to insert flow records", zap.Error(err), zap.Int("count", len(batch)))
		} else {
			a.dbInsertsSuccess.Add(1)
			a.logger.Debug("Inserted flow records", zap.Int("count", len(batch)))
		}

		batch = batch[:0] // Clear batch
	}

	for {
		select {
		case <-a.ctx.Done():
			// Flush remaining records before shutdown
			flush()
			return
		case flow := <-a.flowBuffer:
			batch = append(batch, flow)
			if len(batch) >= a.config.Performance.BufferSize {
				flush()
			}
		case <-ticker.C:
			// Periodic flush
			flush()
		}
	}
}

// statsReporter periodically logs statistics
func (a *TelemetryAgent) statsReporter() {
	defer a.wg.Done()

	ticker := time.NewTicker(time.Duration(a.config.Monitoring.StatsInterval) * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-a.ctx.Done():
			return
		case <-ticker.C:
			dbStats := a.dbClient.GetStats()
			
			a.logger.Info("Telemetry Agent Statistics",
				zap.Uint64("packets_received", a.packetsReceived.Load()),
				zap.Uint64("flows_processed", a.flowsProcessed.Load()),
				zap.Uint64("db_inserts_success", a.dbInsertsSuccess.Load()),
				zap.Uint64("db_inserts_failed", a.dbInsertsFailed.Load()),
				zap.Uint64("parse_errors", a.parseErrors.Load()),
				zap.Int("buffer_size", len(a.flowBuffer)),
				zap.Int32("db_active_conns", dbStats.AcquiredConns()),
				zap.Int32("db_idle_conns", dbStats.IdleConns()),
			)
		}
	}
}

// Stop stops the telemetry agent gracefully
func (a *TelemetryAgent) Stop() {
	a.logger.Info("Stopping Telemetry Agent...")
	a.cancel()
	a.wg.Wait()
	a.dbClient.Close()
	a.logger.Info("Telemetry Agent stopped")
}

// loadConfig loads configuration from YAML file
func loadConfig(filename string) (Config, error) {
	var config Config
	
	data, err := os.ReadFile(filename)
	if err != nil {
		return config, fmt.Errorf("failed to read config file: %w", err)
	}

	if err := yaml.Unmarshal(data, &config); err != nil {
		return config, fmt.Errorf("failed to parse config: %w", err)
	}

	// Set defaults
	if config.Performance.BufferSize == 0 {
		config.Performance.BufferSize = 10000
	}
	if config.Performance.FlushInterval == 0 {
		config.Performance.FlushInterval = 5
	}
	if config.Performance.UDPBufferSize == 0 {
		config.Performance.UDPBufferSize = 26214400 // 25 MB
	}
	if config.Database.PoolSize == 0 {
		config.Database.PoolSize = 20
	}
	if config.Monitoring.StatsInterval == 0 {
		config.Monitoring.StatsInterval = 30
	}

	return config, nil
}

func main() {
	configFile := flag.String("config", "configs/telemetry-agent.yaml", "Path to configuration file")
	flag.Parse()

	// Load configuration
	config, err := loadConfig(*configFile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to load config: %v\n", err)
		os.Exit(1)
	}

	// Create and start agent
	agent, err := NewTelemetryAgent(config)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create agent: %v\n", err)
		os.Exit(1)
	}

	if err := agent.Start(); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to start agent: %v\n", err)
		os.Exit(1)
	}

	// Wait for interrupt signal
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)
	<-sigChan

	// Graceful shutdown
	agent.Stop()
}
