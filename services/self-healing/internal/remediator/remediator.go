package remediator

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"time"

	"github.com/reshwanthmanupati/NetWeaver/services/self-healing/internal/storage"
)

// Config configuration for remediator
type Config struct {
	DeviceManagerURL string
	IntentEngineURL  string
	MaxRetries       int
	RetryDelay       time.Duration
	RollbackOnError  bool
}

// Remediator handles automatic remediation of network failures
type Remediator struct {
	config  Config
	storage storage.Storage
	client  *http.Client
}

// NewRemediator creates a new remediator
func NewRemediator(config Config, store storage.Storage) *Remediator {
	return &Remediator{
		config:  config,
		storage: store,
		client: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// Remediate performs automatic remediation for an incident
func (r *Remediator) Remediate(ctx context.Context, incident *storage.Incident) error {
	log.Printf("🔧 Starting remediation for incident %s (type: %s)", incident.ID, incident.Type)
	
	startTime := time.Now()

	// Update incident status
	incident.Status = "remediating"
	if err := r.storage.UpdateIncident(incident); err != nil {
		return fmt.Errorf("failed to update incident: %w", err)
	}

	// Select remediation strategy based on incident type
	var actions []*storage.RemediationAction
	var err error

	switch incident.Type {
	case "link_failure":
		actions, err = r.remediateLinkFailure(ctx, incident)
	case "device_failure":
		actions, err = r.remediateDeviceFailure(ctx, incident)
	case "performance_degradation":
		actions, err = r.remediatePerformanceDegradation(ctx, incident)
	case "packet_loss":
		actions, err = r.remediatePacketLoss(ctx, incident)
	case "resource_exhaustion":
		actions, err = r.remediateResourceExhaustion(ctx, incident)
	default:
		return fmt.Errorf("unknown incident type: %s", incident.Type)
	}

	if err != nil {
		incident.Status = "failed"
		incident.Error = err.Error()
		r.storage.UpdateIncident(incident)
		return err
	}

	// Save remediation actions
	for _, action := range actions {
		if err := r.storage.SaveRemediationAction(incident.ID, action); err != nil {
			log.Printf("Failed to save remediation action: %v", err)
		}
	}

	// Update incident as remediated
	incident.Status = "remediated"
	incident.RemediatedAt = time.Now()
	incident.ResolutionTime = incident.RemediatedAt.Sub(incident.DetectedAt)
	
	if err := r.storage.UpdateIncident(incident); err != nil {
		return fmt.Errorf("failed to update incident: %w", err)
	}

	duration := time.Since(startTime)
	log.Printf("✅ Remediation completed for incident %s in %v (MTTR: %v)", 
		incident.ID, duration, incident.ResolutionTime)

	return nil
}

// remediateLinkFailure handles link failure remediation
func (r *Remediator) remediateLinkFailure(ctx context.Context, incident *storage.Incident) ([]*storage.RemediationAction, error) {
	log.Printf("🔗 Remediating link failure on device %s", incident.DeviceID)

	actions := []*storage.RemediationAction{}

	// Strategy 1: Reroute traffic via alternate paths
	rerouteAction, err := r.rerouteTraffic(ctx, incident)
	if err != nil {
		log.Printf("Failed to reroute traffic: %v", err)
	} else {
		actions = append(actions, rerouteAction)
	}

	// Strategy 2: Activate VRRP/HSRP failover if available
	failoverAction, err := r.activateFailover(ctx, incident)
	if err != nil {
		log.Printf("Failover not available or failed: %v", err)
	} else {
		actions = append(actions, failoverAction)
	}

	// Strategy 3: Update routing protocols (BGP, OSPF)
	routingAction, err := r.updateRoutingProtocols(ctx, incident)
	if err != nil {
		log.Printf("Failed to update routing: %v", err)
	} else {
		actions = append(actions, routingAction)
	}

	if len(actions) == 0 {
		return nil, fmt.Errorf("all remediation strategies failed")
	}

	return actions, nil
}

// remediateDeviceFailure handles device failure remediation
func (r *Remediator) remediateDeviceFailure(ctx context.Context, incident *storage.Incident) ([]*storage.RemediationAction, error) {
	log.Printf("🖥️  Remediating device failure: %s", incident.DeviceID)

	actions := []*storage.RemediationAction{}

	// Strategy 1: Failover to backup device
	failoverAction, err := r.failoverToBackup(ctx, incident)
	if err != nil {
		log.Printf("Backup failover failed: %v", err)
	} else {
		actions = append(actions, failoverAction)
	}

	// Strategy 2: Redistribute traffic load
	redistributeAction, err := r.redistributeTraffic(ctx, incident)
	if err != nil {
		log.Printf("Traffic redistribution failed: %v", err)
	} else {
		actions = append(actions, redistributeAction)
	}

	// Strategy 3: Alert and isolate failed device
	isolateAction := r.isolateDevice(ctx, incident)
	actions = append(actions, isolateAction)

	return actions, nil
}

// remediatePerformanceDegradation handles performance issues
func (r *Remediator) remediatePerformanceDegradation(ctx context.Context, incident *storage.Incident) ([]*storage.RemediationAction, error) {
	log.Printf("📉 Remediating performance degradation on device %s", incident.DeviceID)

	actions := []*storage.RemediationAction{}

	// Strategy 1: Adjust QoS policies
	qosAction, err := r.adjustQoS(ctx, incident)
	if err != nil {
		log.Printf("QoS adjustment failed: %v", err)
	} else {
		actions = append(actions, qosAction)
	}

	// Strategy 2: Reroute low-priority traffic
	rerouteAction, err := r.rerouteLowPriorityTraffic(ctx, incident)
	if err != nil {
		log.Printf("Traffic rerouting failed: %v", err)
	} else {
		actions = append(actions, rerouteAction)
	}

	// Strategy 3: Increase bandwidth allocation
	bandwidthAction, err := r.increaseBandwidth(ctx, incident)
	if err != nil {
		log.Printf("Bandwidth increase failed: %v", err)
	} else {
		actions = append(actions, bandwidthAction)
	}

	return actions, nil
}

// remediatePacketLoss handles packet loss remediation
func (r *Remediator) remediatePacketLoss(ctx context.Context, incident *storage.Incident) ([]*storage.RemediationAction, error) {
	log.Printf("📦 Remediating packet loss on device %s", incident.DeviceID)

	actions := []*storage.RemediationAction{}

	// Strategy 1: Enable Forward Error Correction (FEC)
	fecAction := r.enableFEC(ctx, incident)
	actions = append(actions, fecAction)

	// Strategy 2: Reroute via more reliable path
	rerouteAction, err := r.rerouteTraffic(ctx, incident)
	if err == nil {
		actions = append(actions, rerouteAction)
	}

	// Strategy 3: Adjust buffer sizes
	bufferAction := r.adjustBuffers(ctx, incident)
	actions = append(actions, bufferAction)

	return actions, nil
}

// remediateResourceExhaustion handles resource exhaustion
func (r *Remediator) remediateResourceExhaustion(ctx context.Context, incident *storage.Incident) ([]*storage.RemediationAction, error) {
	log.Printf("💾 Remediating resource exhaustion on device %s", incident.DeviceID)

	actions := []*storage.RemediationAction{}

	// Strategy 1: Clear caches and buffers
	clearAction := r.clearCaches(ctx, incident)
	actions = append(actions, clearAction)

	// Strategy 2: Kill non-essential processes
	killAction := r.killNonEssentialProcesses(ctx, incident)
	actions = append(actions, killAction)

	// Strategy 3: Offload traffic to other devices
	offloadAction, err := r.redistributeTraffic(ctx, incident)
	if err == nil {
		actions = append(actions, offloadAction)
	}

	return actions, nil
}

// Helper functions for specific remediation actions

func (r *Remediator) rerouteTraffic(ctx context.Context, incident *storage.Incident) (*storage.RemediationAction, error) {
	// Generate rerouting configuration
	config := r.generateReroutingConfig(incident)

	// Deploy configuration via Device Manager
	if err := r.deployConfig(incident.DeviceID, config); err != nil {
		return nil, err
	}

	return &storage.RemediationAction{
		Type:     "traffic_rerouting",
		DeviceID: incident.DeviceID,
		Config:   config,
		Parameters: map[string]interface{}{
			"reason": "link_failure",
			"method": "bgp_route_withdrawal",
		},
		CreatedAt: time.Now(),
	}, nil
}

func (r *Remediator) activateFailover(ctx context.Context, incident *storage.Incident) (*storage.RemediationAction, error) {
	// Generate VRRP/HSRP failover configuration
	config := r.generateFailoverConfig(incident)

	if err := r.deployConfig(incident.DeviceID, config); err != nil {
		return nil, err
	}

	return &storage.RemediationAction{
		Type:     "vrrp_failover",
		DeviceID: incident.DeviceID,
		Config:   config,
		Parameters: map[string]interface{}{
			"protocol": "vrrp",
			"priority": "increase_backup",
		},
		CreatedAt: time.Now(),
	}, nil
}

func (r *Remediator) updateRoutingProtocols(ctx context.Context, incident *storage.Incident) (*storage.RemediationAction, error) {
	config := fmt.Sprintf(`
! BGP route withdrawal for failed link
router bgp 65000
 address-family ipv4
  network 0.0.0.0 mask 0.0.0.0 withdraw
!
! Increase OSPF cost on failed interface
interface %s
 ip ospf cost 10000
!
`, incident.Details["interface"])

	if err := r.deployConfig(incident.DeviceID, config); err != nil {
		return nil, err
	}

	return &storage.RemediationAction{
		Type:     "routing_update",
		DeviceID: incident.DeviceID,
		Config:   config,
		CreatedAt: time.Now(),
	}, nil
}

func (r *Remediator) failoverToBackup(ctx context.Context, incident *storage.Incident) (*storage.RemediationAction, error) {
	// Query for backup device
	backupDevice, err := r.findBackupDevice(incident.DeviceID)
	if err != nil {
		return nil, err
	}

	config := fmt.Sprintf(`
! Activate backup device: %s
! Transfer primary role
vrrp %d priority 120
!
`, backupDevice, 1)

	if err := r.deployConfig(backupDevice, config); err != nil {
		return nil, err
	}

	return &storage.RemediationAction{
		Type:     "backup_failover",
		DeviceID: backupDevice,
		Config:   config,
		Parameters: map[string]interface{}{
			"original_device": incident.DeviceID,
			"backup_device":   backupDevice,
		},
		CreatedAt: time.Now(),
	}, nil
}

func (r *Remediator) redistributeTraffic(ctx context.Context, incident *storage.Incident) (*storage.RemediationAction, error) {
	config := `
! Redistribute traffic to alternate paths
router bgp 65000
 address-family ipv4
  redistribute connected
  redistribute ospf 1
!
`

	if err := r.deployConfig(incident.DeviceID, config); err != nil {
		return nil, err
	}

	return &storage.RemediationAction{
		Type:     "traffic_redistribution",
		DeviceID: incident.DeviceID,
		Config:   config,
		CreatedAt: time.Now(),
	}, nil
}

func (r *Remediator) isolateDevice(ctx context.Context, incident *storage.Incident) *storage.RemediationAction {
	return &storage.RemediationAction{
		Type:     "device_isolation",
		DeviceID: incident.DeviceID,
		Config:   "! Device isolated from network for investigation",
		Parameters: map[string]interface{}{
			"action": "isolate",
			"alert_sent": true,
		},
		CreatedAt: time.Now(),
	}
}

func (r *Remediator) adjustQoS(ctx context.Context, incident *storage.Incident) (*storage.RemediationAction, error) {
	config := `
! Adjust QoS to prioritize critical traffic
policy-map REMEDIATION_QOS
 class class-critical
  priority percent 60
 class class-video
  bandwidth percent 25
 class class-default
  bandwidth percent 15
!
`

	if err := r.deployConfig(incident.DeviceID, config); err != nil {
		return nil, err
	}

	return &storage.RemediationAction{
		Type:     "qos_adjustment",
		DeviceID: incident.DeviceID,
		Config:   config,
		CreatedAt: time.Now(),
	}, nil
}

func (r *Remediator) rerouteLowPriorityTraffic(ctx context.Context, incident *storage.Incident) (*storage.RemediationAction, error) {
	config := `
! Reroute non-critical traffic
ip access-list extended LOW_PRIORITY
 permit ip any any precedence routine
!
route-map REROUTE_LOW_PRIORITY permit 10
 match ip address LOW_PRIORITY
 set ip next-hop 192.168.100.1
!
`

	if err := r.deployConfig(incident.DeviceID, config); err != nil {
		return nil, err
	}

	return &storage.RemediationAction{
		Type:     "low_priority_reroute",
		DeviceID: incident.DeviceID,
		Config:   config,
		CreatedAt: time.Now(),
	}, nil
}

func (r *Remediator) increaseBandwidth(ctx context.Context, incident *storage.Incident) (*storage.RemediationAction, error) {
	config := `
! Increase bandwidth allocation
interface GigabitEthernet0/0/1
 bandwidth 2000000
 no rate-limit
!
`

	if err := r.deployConfig(incident.DeviceID, config); err != nil {
		return nil, err
	}

	return &storage.RemediationAction{
		Type:     "bandwidth_increase",
		DeviceID: incident.DeviceID,
		Config:   config,
		CreatedAt: time.Now(),
	}, nil
}

func (r *Remediator) enableFEC(ctx context.Context, incident *storage.Incident) *storage.RemediationAction {
	return &storage.RemediationAction{
		Type:     "fec_enable",
		DeviceID: incident.DeviceID,
		Config:   "! Enable Forward Error Correction\ninterface GigabitEthernet0/0/1\n fec enable\n!",
		CreatedAt: time.Now(),
	}
}

func (r *Remediator) adjustBuffers(ctx context.Context, incident *storage.Incident) *storage.RemediationAction {
	return &storage.RemediationAction{
		Type:     "buffer_adjustment",
		DeviceID: incident.DeviceID,
		Config:   "! Increase buffer sizes\ninterface GigabitEthernet0/0/1\n tx-ring-limit 1024\n hold-queue 1024 out\n!",
		CreatedAt: time.Now(),
	}
}

func (r *Remediator) clearCaches(ctx context.Context, incident *storage.Incident) *storage.RemediationAction {
	return &storage.RemediationAction{
		Type:     "cache_clear",
		DeviceID: incident.DeviceID,
		Config:   "! Clear caches\nclear ip route *\nclear arp-cache\nclear ip bgp * soft\n!",
		CreatedAt: time.Now(),
	}
}

func (r *Remediator) killNonEssentialProcesses(ctx context.Context, incident *storage.Incident) *storage.RemediationAction {
	return &storage.RemediationAction{
		Type:     "process_termination",
		DeviceID: incident.DeviceID,
		Config:   "! Terminate non-essential processes\nno logging console\nno logging monitor\n!",
		CreatedAt: time.Now(),
	}
}

// Helper functions

func (r *Remediator) deployConfig(deviceID, config string) error {
	url := fmt.Sprintf("%s/api/v1/devices/%s/config", r.config.DeviceManagerURL, deviceID)

	payload := map[string]interface{}{
		"configuration": config,
		"method":        "merge",
	}

	data, err := json.Marshal(payload)
	if err != nil {
		return err
	}

	req, err := http.NewRequest("POST", url, bytes.NewBuffer(data))
	if err != nil {
		return err
	}

	req.Header.Set("Content-Type", "application/json")

	resp, err := r.client.Do(req)
	if err != nil {
		return fmt.Errorf("failed to deploy config: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 && resp.StatusCode != 201 && resp.StatusCode != 202 {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("config deployment failed: %s", string(body))
	}

	log.Printf("✓ Configuration deployed to device %s", deviceID)
	return nil
}

func (r *Remediator) findBackupDevice(primaryDeviceID string) (string, error) {
	// Query device manager for backup device with same role
	url := fmt.Sprintf("%s/api/v1/devices?tags=backup&limit=1", r.config.DeviceManagerURL)

	resp, err := r.client.Get(url)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	var devices []map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&devices); err != nil {
		return "", err
	}

	if len(devices) == 0 {
		return "", fmt.Errorf("no backup device available")
	}

	backupID, ok := devices[0]["id"].(string)
	if !ok {
		return "", fmt.Errorf("invalid device ID format")
	}

	return backupID, nil
}

func (r *Remediator) generateReroutingConfig(incident *storage.Incident) string {
	return fmt.Sprintf(`
! Auto-generated rerouting configuration
! Incident: %s
! Generated: %s

router bgp 65000
 address-family ipv4
  network 0.0.0.0 mask 0.0.0.0 withdraw
!
interface %s
 shutdown
!
`, incident.ID, time.Now().Format(time.RFC3339), incident.Details["interface"])
}

func (r *Remediator) generateFailoverConfig(incident *storage.Incident) string {
	return fmt.Sprintf(`
! VRRP failover configuration
! Incident: %s

track 1 interface %s line-protocol
!
interface Vlan100
 vrrp 1 ip 192.168.1.1
 vrrp 1 priority 120
 vrrp 1 track 1 decrement 30
!
`, incident.ID, incident.Details["interface"])
}

// Rollback performs rollback of remediation actions
func (r *Remediator) Rollback(ctx context.Context, incident *storage.Incident) error {
	log.Printf("↩️  Rolling back remediation for incident %s", incident.ID)

	actions, err := r.storage.GetRemediationActions(incident.ID)
	if err != nil {
		return fmt.Errorf("failed to get remediation actions: %w", err)
	}

	// Rollback actions in reverse order
	for i := len(actions) - 1; i >= 0; i-- {
		action := actions[i]
		
		// Generate rollback configuration
		rollbackConfig := r.generateRollbackConfig(action)
		
		if err := r.deployConfig(action.DeviceID, rollbackConfig); err != nil {
			log.Printf("Failed to rollback action %s: %v", action.Type, err)
			continue
		}

		log.Printf("✓ Rolled back action: %s on device %s", action.Type, action.DeviceID)
	}

	incident.Status = "rolled_back"
	incident.RolledBackAt = time.Now()
	r.storage.UpdateIncident(incident)

	log.Printf("✅ Rollback completed for incident %s", incident.ID)
	return nil
}

func (r *Remediator) generateRollbackConfig(action *storage.RemediationAction) string {
	switch action.Type {
	case "traffic_rerouting":
		return "! Restore original routes\nrouter bgp 65000\n address-family ipv4\n  no network 0.0.0.0 withdraw\n!\n"
	case "vrrp_failover":
		return "! Restore VRRP priority\ninterface Vlan100\n vrrp 1 priority 100\n!\n"
	case "qos_adjustment":
		return "! Restore default QoS\nno policy-map REMEDIATION_QOS\n!\n"
	default:
		return "! Rollback: " + action.Type + "\n"
	}
}
