-- NetWeaver TimescaleDB Schema
-- Production-grade schema for network telemetry, topology, and metrics

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- ============================================================================
-- NETWORK TOPOLOGY TABLES
-- ============================================================================

-- Network devices (routers, switches, firewalls)
CREATE TABLE IF NOT EXISTS network_devices (
    device_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hostname VARCHAR(255) NOT NULL UNIQUE,
    management_ip INET NOT NULL,
    device_type VARCHAR(50) NOT NULL, -- router, switch, firewall, load_balancer
    vendor VARCHAR(50) NOT NULL, -- cisco, juniper, arista, etc.
    model VARCHAR(100),
    os_version VARCHAR(100),
    location VARCHAR(255),
    datacenter VARCHAR(100),
    rack VARCHAR(50),
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_devices_hostname ON network_devices(hostname);
CREATE INDEX idx_devices_type ON network_devices(device_type);
CREATE INDEX idx_devices_location ON network_devices(location);

-- Network interfaces
CREATE TABLE IF NOT EXISTS network_interfaces (
    interface_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id UUID NOT NULL REFERENCES network_devices(device_id) ON DELETE CASCADE,
    interface_name VARCHAR(100) NOT NULL,
    interface_type VARCHAR(50), -- physical, vlan, loopback, tunnel
    ip_address INET,
    subnet_mask INET,
    mac_address MACADDR,
    speed_mbps INTEGER, -- interface speed in Mbps
    mtu INTEGER DEFAULT 1500,
    admin_status VARCHAR(20) DEFAULT 'up', -- up, down
    oper_status VARCHAR(20) DEFAULT 'up', -- up, down
    vlan_id INTEGER,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(device_id, interface_name)
);

CREATE INDEX idx_interfaces_device ON network_interfaces(device_id);
CREATE INDEX idx_interfaces_ip ON network_interfaces(ip_address);

-- Network links (connections between devices)
CREATE TABLE IF NOT EXISTS network_links (
    link_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_device_id UUID NOT NULL REFERENCES network_devices(device_id) ON DELETE CASCADE,
    source_interface_id UUID NOT NULL REFERENCES network_interfaces(interface_id) ON DELETE CASCADE,
    target_device_id UUID NOT NULL REFERENCES network_devices(device_id) ON DELETE CASCADE,
    target_interface_id UUID NOT NULL REFERENCES network_interfaces(interface_id) ON DELETE CASCADE,
    link_type VARCHAR(50) DEFAULT 'ethernet', -- ethernet, fiber, wireless
    bandwidth_mbps INTEGER,
    latency_ms DECIMAL(10,2),
    packet_loss_percent DECIMAL(5,2),
    enabled BOOLEAN DEFAULT true,
    discovered_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_links_source ON network_links(source_device_id);
CREATE INDEX idx_links_target ON network_links(target_device_id);

-- ============================================================================
-- TIME-SERIES TELEMETRY TABLES
-- ============================================================================

-- NetFlow/sFlow records
CREATE TABLE IF NOT EXISTS flow_records (
    time TIMESTAMPTZ NOT NULL,
    exporter_ip INET NOT NULL,
    source_ip INET NOT NULL,
    destination_ip INET NOT NULL,
    source_port INTEGER,
    destination_port INTEGER,
    protocol INTEGER NOT NULL, -- IANA protocol number
    bytes BIGINT NOT NULL,
    packets BIGINT NOT NULL,
    tcp_flags INTEGER,
    tos INTEGER, -- Type of Service / DSCP
    input_interface INTEGER,
    output_interface INTEGER,
    next_hop_ip INET,
    source_as INTEGER, -- Autonomous System Number
    destination_as INTEGER,
    flow_duration_ms INTEGER,
    sampling_rate INTEGER DEFAULT 1,
    metadata JSONB DEFAULT '{}'
);

-- Convert to hypertable for time-series optimization
SELECT create_hypertable('flow_records', 'time', 
    chunk_time_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- Composite indexes for common query patterns
CREATE INDEX idx_flow_time_exporter ON flow_records(time DESC, exporter_ip);
CREATE INDEX idx_flow_src_dst ON flow_records(source_ip, destination_ip, time DESC);
CREATE INDEX idx_flow_protocol ON flow_records(protocol, time DESC);
CREATE INDEX idx_flow_ports ON flow_records(destination_port, time DESC);

-- Enable compression on the hypertable first
ALTER TABLE flow_records SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'exporter_ip, source_ip, destination_ip',
  timescaledb.compress_orderby = 'time DESC'
);

-- Compression policy (compress chunks older than 7 days)
SELECT add_compression_policy('flow_records', INTERVAL '7 days', if_not_exists => TRUE);

-- Retention policy (drop chunks older than 90 days)
SELECT add_retention_policy('flow_records', INTERVAL '90 days', if_not_exists => TRUE);

-- Interface metrics (throughput, errors, discards)
CREATE TABLE IF NOT EXISTS interface_metrics (
    time TIMESTAMPTZ NOT NULL,
    device_id UUID NOT NULL REFERENCES network_devices(device_id) ON DELETE CASCADE,
    interface_id UUID NOT NULL REFERENCES network_interfaces(interface_id) ON DELETE CASCADE,
    bytes_in BIGINT NOT NULL DEFAULT 0,
    bytes_out BIGINT NOT NULL DEFAULT 0,
    packets_in BIGINT NOT NULL DEFAULT 0,
    packets_out BIGINT NOT NULL DEFAULT 0,
    errors_in BIGINT NOT NULL DEFAULT 0,
    errors_out BIGINT NOT NULL DEFAULT 0,
    discards_in BIGINT NOT NULL DEFAULT 0,
    discards_out BIGINT NOT NULL DEFAULT 0,
    utilization_percent DECIMAL(5,2),
    bandwidth_utilization_percent DECIMAL(5,2)
);

SELECT create_hypertable('interface_metrics', 'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

CREATE INDEX idx_iface_metrics_device ON interface_metrics(device_id, time DESC);
CREATE INDEX idx_iface_metrics_interface ON interface_metrics(interface_id, time DESC);

SELECT add_compression_policy('interface_metrics', INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_retention_policy('interface_metrics', INTERVAL '90 days', if_not_exists => TRUE);

-- Device metrics (CPU, memory, temperature)
CREATE TABLE IF NOT EXISTS device_metrics (
    time TIMESTAMPTZ NOT NULL,
    device_id UUID NOT NULL REFERENCES network_devices(device_id) ON DELETE CASCADE,
    cpu_utilization_percent DECIMAL(5,2),
    memory_utilization_percent DECIMAL(5,2),
    temperature_celsius DECIMAL(5,2),
    fan_speed_rpm INTEGER,
    power_watts DECIMAL(8,2),
    uptime_seconds BIGINT,
    session_count INTEGER,
    route_count INTEGER,
    arp_entries INTEGER
);

SELECT create_hypertable('device_metrics', 'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

CREATE INDEX idx_device_metrics_device ON device_metrics(device_id, time DESC);

SELECT add_compression_policy('device_metrics', INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_retention_policy('device_metrics', INTERVAL '90 days', if_not_exists => TRUE);

-- Link latency metrics
CREATE TABLE IF NOT EXISTS link_latency_metrics (
    time TIMESTAMPTZ NOT NULL,
    link_id UUID NOT NULL REFERENCES network_links(link_id) ON DELETE CASCADE,
    latency_ms DECIMAL(10,3) NOT NULL,
    jitter_ms DECIMAL(10,3),
    packet_loss_percent DECIMAL(5,2),
    rtt_min_ms DECIMAL(10,3),
    rtt_max_ms DECIMAL(10,3),
    rtt_avg_ms DECIMAL(10,3)
);

SELECT create_hypertable('link_latency_metrics', 'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

CREATE INDEX idx_latency_link ON link_latency_metrics(link_id, time DESC);

SELECT add_compression_policy('link_latency_metrics', INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_retention_policy('link_latency_metrics', INTERVAL '90 days', if_not_exists => TRUE);

-- ============================================================================
-- ROUTING AND OPTIMIZATION TABLES
-- ============================================================================

-- Routing table snapshots
CREATE TABLE IF NOT EXISTS routing_table_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id UUID NOT NULL REFERENCES network_devices(device_id) ON DELETE CASCADE,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    route_count INTEGER NOT NULL,
    snapshot_data JSONB NOT NULL, -- Array of route entries
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_routing_snapshots_device ON routing_table_snapshots(device_id, captured_at DESC);

-- Optimization events (when NetWeaver makes routing changes)
CREATE TABLE IF NOT EXISTS optimization_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type VARCHAR(50) NOT NULL, -- route_change, qos_update, load_balance, failover
    trigger_reason VARCHAR(255) NOT NULL,
    affected_devices UUID[] NOT NULL,
    optimization_algorithm VARCHAR(100) NOT NULL,
    before_state JSONB,
    after_state JSONB,
    estimated_improvement JSONB, -- latency_reduction_ms, throughput_increase_mbps, etc.
    actual_improvement JSONB,
    success BOOLEAN DEFAULT true,
    error_message TEXT,
    rollback_available BOOLEAN DEFAULT true,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_opt_events_time ON optimization_events(event_time DESC);
CREATE INDEX idx_opt_events_type ON optimization_events(event_type, event_time DESC);

-- Traffic predictions (ML model outputs)
CREATE TABLE IF NOT EXISTS traffic_predictions (
    time TIMESTAMPTZ NOT NULL,
    source_ip INET NOT NULL,
    destination_ip INET NOT NULL,
    predicted_bytes BIGINT NOT NULL,
    predicted_packets BIGINT NOT NULL,
    confidence_score DECIMAL(5,4), -- 0.0 to 1.0
    prediction_horizon_minutes INTEGER NOT NULL, -- how far ahead
    model_version VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

SELECT create_hypertable('traffic_predictions', 'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

CREATE INDEX idx_predictions_src_dst ON traffic_predictions(source_ip, destination_ip, time DESC);

SELECT add_retention_policy('traffic_predictions', INTERVAL '30 days', if_not_exists => TRUE);

-- ============================================================================
-- SECURITY AND ANOMALY TABLES
-- ============================================================================

-- Security events (DDoS, port scans, anomalies)
CREATE TABLE IF NOT EXISTS security_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type VARCHAR(50) NOT NULL, -- ddos, port_scan, anomaly, brute_force
    severity VARCHAR(20) NOT NULL, -- critical, high, medium, low
    source_ip INET NOT NULL,
    destination_ip INET,
    destination_port INTEGER,
    protocol INTEGER,
    attack_signature VARCHAR(255),
    packets_count BIGINT,
    bytes_count BIGINT,
    duration_seconds INTEGER,
    mitigation_applied BOOLEAN DEFAULT false,
    mitigation_action VARCHAR(100),
    false_positive BOOLEAN DEFAULT false,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_security_time ON security_events(detected_at DESC);
CREATE INDEX idx_security_type ON security_events(event_type, detected_at DESC);
CREATE INDEX idx_security_src ON security_events(source_ip, detected_at DESC);
CREATE INDEX idx_security_severity ON security_events(severity, detected_at DESC);

-- Anomaly detection results
CREATE TABLE IF NOT EXISTS anomaly_detections (
    time TIMESTAMPTZ NOT NULL,
    anomaly_type VARCHAR(50) NOT NULL, -- traffic_spike, unusual_pattern, capacity_threshold
    metric_name VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50) NOT NULL, -- device, interface, link, flow
    entity_id UUID NOT NULL,
    baseline_value DECIMAL(20,4),
    observed_value DECIMAL(20,4),
    anomaly_score DECIMAL(10,6), -- higher = more anomalous
    confidence DECIMAL(5,4), -- 0.0 to 1.0
    model_type VARCHAR(50) NOT NULL, -- isolation_forest, lstm, statistical
    metadata JSONB DEFAULT '{}'
);

SELECT create_hypertable('anomaly_detections', 'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

CREATE INDEX idx_anomaly_time ON anomaly_detections(time DESC);
CREATE INDEX idx_anomaly_type ON anomaly_detections(anomaly_type, time DESC);
CREATE INDEX idx_anomaly_entity ON anomaly_detections(entity_id, time DESC);

SELECT add_retention_policy('anomaly_detections', INTERVAL '60 days', if_not_exists => TRUE);

-- ============================================================================
-- CONTINUOUS AGGREGATES (Pre-computed rollups for fast queries)
-- ============================================================================

-- 5-minute flow aggregates
CREATE MATERIALIZED VIEW flow_5min_agg
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('5 minutes', time) AS bucket,
    exporter_ip,
    source_ip,
    destination_ip,
    protocol,
    SUM(bytes) AS total_bytes,
    SUM(packets) AS total_packets,
    COUNT(*) AS flow_count,
    AVG(flow_duration_ms) AS avg_duration_ms
FROM flow_records
GROUP BY bucket, exporter_ip, source_ip, destination_ip, protocol
WITH NO DATA;

SELECT add_continuous_aggregate_policy('flow_5min_agg',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists => TRUE
);

-- Hourly interface metrics aggregates
CREATE MATERIALIZED VIEW interface_metrics_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    device_id,
    interface_id,
    SUM(bytes_in) AS total_bytes_in,
    SUM(bytes_out) AS total_bytes_out,
    SUM(packets_in) AS total_packets_in,
    SUM(packets_out) AS total_packets_out,
    AVG(utilization_percent) AS avg_utilization,
    MAX(utilization_percent) AS max_utilization
FROM interface_metrics
GROUP BY bucket, device_id, interface_id
WITH NO DATA;

SELECT add_continuous_aggregate_policy('interface_metrics_hourly',
    start_offset => INTERVAL '7 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to get top talkers (highest traffic sources)
CREATE OR REPLACE FUNCTION get_top_talkers(
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    top_n INTEGER DEFAULT 10
)
RETURNS TABLE (
    source_ip INET,
    total_bytes NUMERIC,
    total_packets NUMERIC,
    flow_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        fr.source_ip,
        SUM(fr.bytes) AS total_bytes,
        SUM(fr.packets) AS total_packets,
        COUNT(*) AS flow_count
    FROM flow_records fr
    WHERE fr.time BETWEEN start_time AND end_time
    GROUP BY fr.source_ip
    ORDER BY total_bytes DESC
    LIMIT top_n;
END;
$$ LANGUAGE plpgsql;

-- Function to calculate link utilization
CREATE OR REPLACE FUNCTION calculate_link_utilization(
    p_link_id UUID,
    time_window INTERVAL DEFAULT '5 minutes'
)
RETURNS DECIMAL(5,2) AS $$
DECLARE
    link_bandwidth BIGINT;
    recent_bytes BIGINT;
    utilization DECIMAL(5,2);
BEGIN
    -- Get link bandwidth
    SELECT bandwidth_mbps * 1000000 INTO link_bandwidth
    FROM network_links
    WHERE link_id = p_link_id;
    
    -- Get recent traffic
    SELECT SUM(bytes) INTO recent_bytes
    FROM flow_records
    WHERE time >= NOW() - time_window;
    
    -- Calculate utilization percentage
    IF link_bandwidth > 0 THEN
        utilization := (recent_bytes::DECIMAL / link_bandwidth) * 100;
        RETURN LEAST(utilization, 100.0);
    ELSE
        RETURN 0.0;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SAMPLE DATA VIEWS
-- ============================================================================

-- View: Current device health status
CREATE OR REPLACE VIEW device_health_current AS
SELECT
    d.device_id,
    d.hostname,
    d.device_type,
    d.location,
    dm.cpu_utilization_percent,
    dm.memory_utilization_percent,
    dm.temperature_celsius,
    dm.uptime_seconds,
    dm.time AS last_update
FROM network_devices d
LEFT JOIN LATERAL (
    SELECT *
    FROM device_metrics
    WHERE device_id = d.device_id
    ORDER BY time DESC
    LIMIT 1
) dm ON true
WHERE d.enabled = true;

-- View: Interface utilization summary
CREATE OR REPLACE VIEW interface_utilization_summary AS
SELECT
    d.hostname,
    i.interface_name,
    i.speed_mbps,
    im.utilization_percent,
    im.bytes_in,
    im.bytes_out,
    im.time AS last_update
FROM network_interfaces i
JOIN network_devices d ON i.device_id = d.device_id
LEFT JOIN LATERAL (
    SELECT *
    FROM interface_metrics
    WHERE interface_id = i.interface_id
    ORDER BY time DESC
    LIMIT 1
) im ON true
WHERE i.admin_status = 'up';

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO netweaver;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO netweaver;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO netweaver;

-- Create indexes on JSONB columns for faster queries
CREATE INDEX idx_devices_metadata ON network_devices USING GIN(metadata);
CREATE INDEX idx_links_metadata ON network_links USING GIN(metadata);
CREATE INDEX idx_opt_events_before ON optimization_events USING GIN(before_state);
CREATE INDEX idx_opt_events_after ON optimization_events USING GIN(after_state);

-- Analyze tables for query optimization
ANALYZE network_devices;
ANALYZE network_interfaces;
ANALYZE network_links;
ANALYZE flow_records;
ANALYZE interface_metrics;
ANALYZE device_metrics;
