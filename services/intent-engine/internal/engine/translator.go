package engine

import (
	"bytes"
	"fmt"
	"strings"
	"text/template"
)

// ConfigTranslator translates intents to vendor-specific configurations
type ConfigTranslator struct{
	templates map[string]*VendorTemplates
}

// VendorTemplates templates for a specific vendor
type VendorTemplates struct {
	QoS           *template.Template
	Routing       *template.Template
	ACL           *template.Template
	Bandwidth     *template.Template
	TrafficPolicy *template.Template
}

// NewConfigTranslator creates a new config translator
func NewConfigTranslator() *ConfigTranslator {
	translator := &ConfigTranslator{
		templates: make(map[string]*VendorTemplates),
	}

	// Initialize vendor templates
	translator.initCiscoTemplates()
	translator.initJuniperTemplates()
	translator.initAristaTemplates()

	return translator
}

// TranslateIntent translates an intent to vendor-specific configuration
func (ct *ConfigTranslator) TranslateIntent(intent *Intent, vendor string, deviceID string) (string, error) {
	vendorKey := strings.ToLower(vendor)
	
	templates, exists := ct.templates[vendorKey]
	if !exists {
		return "", fmt.Errorf("unsupported vendor: %s", vendor)
	}

	// Build configuration based on policy type
	config := strings.Builder{}
	config.WriteString(fmt.Sprintf("! Configuration for Intent: %s\n", intent.Name))
	config.WriteString(fmt.Sprintf("! Device: %s\n", deviceID))
	config.WriteString(fmt.Sprintf("! Generated: %s\n\n", intent.CreatedAt.Format("2006-01-02 15:04:05")))

	switch intent.Policy.Type {
	case "latency", "qos":
		qosConfig, err := ct.translateQoS(intent, templates, deviceID)
		if err != nil {
			return "", fmt.Errorf("failed to translate QoS: %w", err)
		}
		config.WriteString(qosConfig)

	case "bandwidth":
		bwConfig, err := ct.translateBandwidth(intent, templates, deviceID)
		if err != nil {
			return "", fmt.Errorf("failed to translate bandwidth: %w", err)
		}
		config.WriteString(bwConfig)

	case "routing":
		routeConfig, err := ct.translateRouting(intent, templates, deviceID)
		if err != nil {
			return "", fmt.Errorf("failed to translate routing: %w", err)
		}
		config.WriteString(routeConfig)

	case "security":
		aclConfig, err := ct.translateACL(intent, templates, deviceID)
		if err != nil {
			return "", fmt.Errorf("failed to translate ACL: %w", err)
		}
		config.WriteString(aclConfig)

	default:
		return "", fmt.Errorf("unsupported policy type: %s", intent.Policy.Type)
	}

	return config.String(), nil
}

func (ct *ConfigTranslator) translateQoS(intent *Intent, templates *VendorTemplates, deviceID string) (string, error) {
	if templates.QoS == nil {
		return "", fmt.Errorf("QoS template not available")
	}

	// Extract relevant data from intent
	data := map[string]interface{}{
		"IntentName":  intent.Name,
		"DeviceID":    deviceID,
		"Priority":    intent.Priority,
		"Constraints": intent.Policy.Constraints,
		"Conditions":  intent.Policy.Conditions,
	}

	// Find latency constraint
	for _, constraint := range intent.Policy.Constraints {
		if constraint.Metric == "latency" {
			data["LatencyTarget"] = constraint.Value
			data["LatencyUnit"] = constraint.Unit
		}
	}

	// Find traffic type from conditions
	for _, condition := range intent.Policy.Conditions {
		if condition.Type == "traffic_type" {
			if trafficType, ok := condition.Parameters["type"].(string); ok {
				data["TrafficType"] = trafficType
				data["ClassMap"] = fmt.Sprintf("class-%s", strings.ToLower(trafficType))
			}
		}
	}

	var buf bytes.Buffer
	if err := templates.QoS.Execute(&buf, data); err != nil {
		return "", err
	}

	return buf.String(), nil
}

func (ct *ConfigTranslator) translateBandwidth(intent *Intent, templates *VendorTemplates, deviceID string) (string, error) {
	if templates.Bandwidth == nil {
		return "", fmt.Errorf("bandwidth template not available")
	}

	data := map[string]interface{}{
		"IntentName": intent.Name,
		"DeviceID":   deviceID,
	}

	// Extract bandwidth constraint
	for _, constraint := range intent.Policy.Constraints {
		if constraint.Metric == "bandwidth" {
			data["BandwidthValue"] = constraint.Value
			data["BandwidthUnit"] = constraint.Unit
			data["Operator"] = constraint.Operator
		}
	}

	var buf bytes.Buffer
	if err := templates.Bandwidth.Execute(&buf, data); err != nil {
		return "", err
	}

	return buf.String(), nil
}

func (ct *ConfigTranslator) translateRouting(intent *Intent, templates *VendorTemplates, deviceID string) (string, error) {
	if templates.Routing == nil {
		return "", fmt.Errorf("routing template not available")
	}

	data := map[string]interface{}{
		"IntentName": intent.Name,
		"DeviceID":   deviceID,
		"Actions":    intent.Policy.Actions,
	}

	// Extract routing actions
	for _, action := range intent.Policy.Actions {
		if action.Type == "route" {
			data["RouteAction"] = action.Parameters
		}
	}

	var buf bytes.Buffer
	if err := templates.Routing.Execute(&buf, data); err != nil {
		return "", err
	}

	return buf.String(), nil
}

func (ct *ConfigTranslator) translateACL(intent *Intent, templates *VendorTemplates, deviceID string) (string, error) {
	if templates.ACL == nil {
		return "", fmt.Errorf("ACL template not available")
	}

	data := map[string]interface{}{
		"IntentName": intent.Name,
		"DeviceID":   deviceID,
		"Actions":    intent.Policy.Actions,
	}

	var buf bytes.Buffer
	if err := templates.ACL.Execute(&buf, data); err != nil {
		return "", err
	}

	return buf.String(), nil
}

// Initialize Cisco IOS/IOS-XE templates
func (ct *ConfigTranslator) initCiscoTemplates() {
	qosTemplate := `! QoS Configuration for {{.TrafficType}} traffic
{{if .ClassMap}}
class-map match-any {{.ClassMap}}
 match protocol {{.TrafficType}}
 match dscp ef
!
policy-map {{.IntentName}}-policy
 class {{.ClassMap}}
  priority percent 30
  set dscp ef
 class class-default
  fair-queue
!
{{range $target := .Interfaces}}
interface {{$target}}
 service-policy output {{$.IntentName}}-policy
!
{{end}}
{{end}}`

	bandwidthTemplate := `! Bandwidth Configuration
{{range $target := .Interfaces}}
interface {{$target}}
 bandwidth {{.BandwidthValue}}
 {{if eq .Operator ">"}}
 ! Minimum bandwidth guaranteed
 {{end}}
!
{{end}}`

	routingTemplate := `! Routing Configuration
{{if .RouteAction.destination}}
ip route {{.RouteAction.destination}} {{.RouteAction.mask}} {{.RouteAction.next_hop}}
{{end}}
{{if .RouteAction.metric}}
 ! Metric: {{.RouteAction.metric}}
{{end}}`

	aclTemplate := `! ACL Configuration
ip access-list extended {{.IntentName}}-acl
{{range $action := .Actions}}
 {{if eq $action.Type "firewall"}}
  {{$action.Parameters.rule}}
 {{end}}
{{end}}
!`

	ct.templates["cisco_ios"] = &VendorTemplates{
		QoS:       template.Must(template.New("cisco_qos").Parse(qosTemplate)),
		Bandwidth: template.Must(template.New("cisco_bandwidth").Parse(bandwidthTemplate)),
		Routing:   template.Must(template.New("cisco_routing").Parse(routingTemplate)),
		ACL:       template.Must(template.New("cisco_acl").Parse(aclTemplate)),
	}

	ct.templates["cisco_iosxe"] = ct.templates["cisco_ios"] // Same syntax
}

// Initialize Juniper JunOS templates
func (ct *ConfigTranslator) initJuniperTemplates() {
	qosTemplate := `# QoS Configuration for {{.TrafficType}} traffic
{{if .ClassMap}}
set class-of-service classifiers dscp {{.ClassMap}} forwarding-class expedited-forwarding loss-priority low code-points ef
set class-of-service interfaces {{range .Interfaces}}{{.}} {{end}}scheduler-map {{.IntentName}}-scheduler
set class-of-service scheduler-maps {{.IntentName}}-scheduler forwarding-class expedited-forwarding scheduler {{.IntentName}}-sched
set class-of-service schedulers {{.IntentName}}-sched transmit-rate percent 30
set class-of-service schedulers {{.IntentName}}-sched priority strict-high
{{end}}`

	bandwidthTemplate := `# Bandwidth Configuration
{{range $target := .Interfaces}}
set interfaces {{$target}} bandwidth {{.BandwidthValue}}{{.BandwidthUnit}}
{{end}}`

	routingTemplate := `# Routing Configuration
{{if .RouteAction.destination}}
set routing-options static route {{.RouteAction.destination}} next-hop {{.RouteAction.next_hop}}
{{if .RouteAction.metric}}
set routing-options static route {{.RouteAction.destination}} metric {{.RouteAction.metric}}
{{end}}
{{end}}`

	aclTemplate := `# Firewall Configuration
set firewall family inet filter {{.IntentName}}-filter
{{range $action := .Actions}}
{{if eq $action.Type "firewall"}}
set firewall family inet filter {{$.IntentName}}-filter term {{$action.Parameters.term}} {{$action.Parameters.rule}}
{{end}}
{{end}}`

	ct.templates["juniper_junos"] = &VendorTemplates{
		QoS:       template.Must(template.New("juniper_qos").Parse(qosTemplate)),
		Bandwidth: template.Must(template.New("juniper_bandwidth").Parse(bandwidthTemplate)),
		Routing:   template.Must(template.New("juniper_routing").Parse(routingTemplate)),
		ACL:       template.Must(template.New("juniper_acl").Parse(aclTemplate)),
	}
}

// Initialize Arista EOS templates
func (ct *ConfigTranslator) initAristaTemplates() {
	qosTemplate := `! QoS Configuration for {{.TrafficType}} traffic
{{if .ClassMap}}
class-map {{.ClassMap}}
  match ip dscp ef
!
policy-map {{.IntentName}}-policy
  class {{.ClassMap}}
    priority
    set dscp ef
    bandwidth percent 30
!
{{range $target := .Interfaces}}
interface {{$target}}
  service-policy output {{$.IntentName}}-policy
!
{{end}}
{{end}}`

	bandwidthTemplate := `! Bandwidth Configuration
{{range $target := .Interfaces}}
interface {{$target}}
  speed forced {{.BandwidthValue}}{{.BandwidthUnit}}
!
{{end}}`

	routingTemplate := `! Routing Configuration
{{if .RouteAction.destination}}
ip route {{.RouteAction.destination}} {{.RouteAction.mask}} {{.RouteAction.next_hop}}
{{if .RouteAction.metric}}
  metric {{.RouteAction.metric}}
{{end}}
{{end}}`

	aclTemplate := `! ACL Configuration
ip access-list {{.IntentName}}-acl
{{range $action := .Actions}}
  {{if eq $action.Type "firewall"}}
  {{$action.Parameters.rule}}
  {{end}}
{{end}}
!`

	ct.templates["arista_eos"] = &VendorTemplates{
		QoS:       template.Must(template.New("arista_qos").Parse(qosTemplate)),
		Bandwidth: template.Must(template.New("arista_bandwidth").Parse(bandwidthTemplate)),
		Routing:   template.Must(template.New("arista_routing").Parse(routingTemplate)),
		ACL:       template.Must(template.New("arista_acl").Parse(aclTemplate)),
	}
}
