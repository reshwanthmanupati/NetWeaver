package engine

import (
	"fmt"
	"regexp"
	"strconv"
	"strings"
)

// PolicyParser parses and validates policy constraints
type PolicyParser struct {
	metricValidators map[string]MetricValidator
}

// MetricValidator validates specific metric types
type MetricValidator struct {
	AllowedUnits     []string
	AllowedOperators []string
	ValueType        string // int, float, string
}

// NewPolicyParser creates a new policy parser
func NewPolicyParser() *PolicyParser {
	return &PolicyParser{
		metricValidators: map[string]MetricValidator{
			"latency": {
				AllowedUnits:     []string{"ms", "us", "s"},
				AllowedOperators: []string{"<", "<=", ">", ">=", "=="},
				ValueType:        "float",
			},
			"bandwidth": {
				AllowedUnits:     []string{"bps", "Kbps", "Mbps", "Gbps"},
				AllowedOperators: []string{"<", "<=", ">", ">=", "=="},
				ValueType:        "float",
			},
			"packet_loss": {
				AllowedUnits:     []string{"%", "pct"},
				AllowedOperators: []string{"<", "<=", ">", ">=", "=="},
				ValueType:        "float",
			},
			"jitter": {
				AllowedUnits:     []string{"ms", "us"},
				AllowedOperators: []string{"<", "<="},
				ValueType:        "float",
			},
			"availability": {
				AllowedUnits:     []string{"%", "pct"},
				AllowedOperators: []string{">", ">="},
				ValueType:        "float",
			},
			"throughput": {
				AllowedUnits:     []string{"pps", "Kpps", "Mpps"},
				AllowedOperators: []string{">", ">="},
				ValueType:        "float",
			},
		},
	}
}

// ValidateConstraint validates a policy constraint
func (p *PolicyParser) ValidateConstraint(constraint *Constraint) error {
	// Check if metric is supported
	validator, exists := p.metricValidators[constraint.Metric]
	if !exists {
		return fmt.Errorf("unsupported metric: %s", constraint.Metric)
	}

	// Validate operator
	if !contains(validator.AllowedOperators, constraint.Operator) {
		return fmt.Errorf("invalid operator %s for metric %s, allowed: %v",
			constraint.Operator, constraint.Metric, validator.AllowedOperators)
	}

	// Validate unit
	if constraint.Unit != "" && !contains(validator.AllowedUnits, constraint.Unit) {
		return fmt.Errorf("invalid unit %s for metric %s, allowed: %v",
			constraint.Unit, constraint.Metric, validator.AllowedUnits)
	}

	// Validate value type
	if err := p.validateValue(constraint.Value, validator.ValueType); err != nil {
		return fmt.Errorf("invalid value for metric %s: %w", constraint.Metric, err)
	}

	return nil
}

func (p *PolicyParser) validateValue(value interface{}, expectedType string) error {
	switch expectedType {
	case "float":
		switch v := value.(type) {
		case float64, float32:
			return nil
		case int, int64:
			return nil
		case string:
			// Try parsing as float
			if _, err := strconv.ParseFloat(v, 64); err != nil {
				return fmt.Errorf("expected float, got string: %s", v)
			}
			return nil
		default:
			return fmt.Errorf("expected float, got %T", value)
		}
	case "int":
		switch v := value.(type) {
		case int, int64:
			return nil
		case string:
			if _, err := strconv.Atoi(v); err != nil {
				return fmt.Errorf("expected int, got string: %s", v)
			}
			return nil
		default:
			return fmt.Errorf("expected int, got %T", value)
		}
	case "string":
		if _, ok := value.(string); !ok {
			return fmt.Errorf("expected string, got %T", value)
		}
		return nil
	}
	return nil
}

// ParseNaturalLanguage parses natural language constraints
// Example: "latency should be less than 50ms" -> Constraint{Metric: "latency", Operator: "<", Value: 50, Unit: "ms"}
func (p *PolicyParser) ParseNaturalLanguage(text string) (*Constraint, error) {
	text = strings.ToLower(strings.TrimSpace(text))

	// Pattern: "<metric> should be <operator> <value><unit>"
	// Examples:
	//   - "latency should be less than 50ms"
	//   - "bandwidth should be greater than 1Gbps"
	//   - "packet loss should be below 0.1%"

	patterns := []struct {
		regex    *regexp.Regexp
		operator string
	}{
		{regexp.MustCompile(`(\w+)\s+should\s+be\s+less\s+than\s+([\d.]+)\s*(\w+)`), "<"},
		{regexp.MustCompile(`(\w+)\s+should\s+be\s+below\s+([\d.]+)\s*(\w+)`), "<"},
		{regexp.MustCompile(`(\w+)\s+should\s+be\s+greater\s+than\s+([\d.]+)\s*(\w+)`), ">"},
		{regexp.MustCompile(`(\w+)\s+should\s+be\s+above\s+([\d.]+)\s*(\w+)`), ">"},
		{regexp.MustCompile(`(\w+)\s+<\s+([\d.]+)\s*(\w+)`), "<"},
		{regexp.MustCompile(`(\w+)\s+>\s+([\d.]+)\s*(\w+)`), ">"},
		{regexp.MustCompile(`(\w+)\s+<=\s+([\d.]+)\s*(\w+)`), "<="},
		{regexp.MustCompile(`(\w+)\s+>=\s+([\d.]+)\s*(\w+)`), ">="},
	}

	for _, pattern := range patterns {
		matches := pattern.regex.FindStringSubmatch(text)
		if len(matches) == 4 {
			metric := matches[1]
			value, err := strconv.ParseFloat(matches[2], 64)
			if err != nil {
				return nil, fmt.Errorf("invalid value: %s", matches[2])
			}
			unit := matches[3]

			constraint := &Constraint{
				Metric:   metric,
				Operator: pattern.operator,
				Value:    value,
				Unit:     unit,
			}

			// Validate the constraint
			if err := p.ValidateConstraint(constraint); err != nil {
				return nil, err
			}

			return constraint, nil
		}
	}

	return nil, fmt.Errorf("could not parse natural language constraint: %s", text)
}

// ConflictDetector detects conflicts between policies
type ConflictDetector struct{}

// NewConflictDetector creates a new conflict detector
func NewConflictDetector() *ConflictDetector {
	return &ConflictDetector{}
}

// DetectConflicts detects conflicts between a new intent and existing intents
func (cd *ConflictDetector) DetectConflicts(newIntent *Intent, storage Storage) ([]ConflictInfo, error) {
	conflicts := []ConflictInfo{}

	// Get all existing intents
	existingIntents, err := storage.ListIntents(map[string]interface{}{})
	if err != nil {
		return nil, err
	}

	for _, existing := range existingIntents {
		// Skip if same intent
		if existing.ID == newIntent.ID {
			continue
		}

		// Check for target overlap
		if cd.hasTargetOverlap(newIntent, existing) {
			// Check for conflicting constraints
			if conflict := cd.checkConstraintConflicts(newIntent, existing); conflict != nil {
				conflicts = append(conflicts, *conflict)
			}

			// Check for conflicting actions
			if conflict := cd.checkActionConflicts(newIntent, existing); conflict != nil {
				conflicts = append(conflicts, *conflict)
			}

			// Check priority conflicts
			if conflict := cd.checkPriorityConflicts(newIntent, existing); conflict != nil {
				conflicts = append(conflicts, *conflict)
			}
		}
	}

	return conflicts, nil
}

func (cd *ConflictDetector) hasTargetOverlap(intent1, intent2 *Intent) bool {
	// Check if any targets overlap
	for _, t1 := range intent1.Targets {
		for _, t2 := range intent2.Targets {
			if t1.Type == t2.Type {
				// Check for identifier overlap
				for _, id1 := range t1.Identifiers {
					for _, id2 := range t2.Identifiers {
						if id1 == id2 {
							return true
						}
					}
				}
			}
		}
	}
	return false
}

func (cd *ConflictDetector) checkConstraintConflicts(intent1, intent2 *Intent) *ConflictInfo {
	// Check if constraints on same metric conflict
	for _, c1 := range intent1.Policy.Constraints {
		for _, c2 := range intent2.Policy.Constraints {
			if c1.Metric == c2.Metric {
				// Check if constraints are incompatible
				if cd.areConstraintsIncompatible(&c1, &c2) {
					return &ConflictInfo{
						ConflictingIntentID: intent2.ID,
						ConflictType:       "constraint",
						Description: fmt.Sprintf("Constraint on %s conflicts: %s %v %s vs %s %v %s",
							c1.Metric, c1.Operator, c1.Value, c1.Unit,
							c2.Operator, c2.Value, c2.Unit),
						Severity: "high",
					}
				}
			}
		}
	}
	return nil
}

func (cd *ConflictDetector) areConstraintsIncompatible(c1, c2 *Constraint) bool {
	// Example: "latency < 50ms" vs "latency > 100ms" would be incompatible
	// This is a simplified check
	v1, ok1 := c1.Value.(float64)
	v2, ok2 := c2.Value.(float64)
	
	if !ok1 || !ok2 {
		return false
	}

	// Check for impossible combinations
	if c1.Operator == "<" && c2.Operator == ">" && v1 < v2 {
		return true
	}
	if c1.Operator == ">" && c2.Operator == "<" && v1 > v2 {
		return true
	}

	return false
}

func (cd *ConflictDetector) checkActionConflicts(intent1, intent2 *Intent) *ConflictInfo {
	// Check if actions conflict
	for _, a1 := range intent1.Policy.Actions {
		for _, a2 := range intent2.Policy.Actions {
			if a1.Type == a2.Type {
				// Same action type on overlapping targets could conflict
				return &ConflictInfo{
					ConflictingIntentID: intent2.ID,
					ConflictType:       "action",
					Description:        fmt.Sprintf("Action %s already defined by intent %s", a1.Type, intent2.ID),
					Severity:           "medium",
				}
			}
		}
	}
	return nil
}

func (cd *ConflictDetector) checkPriorityConflicts(intent1, intent2 *Intent) *ConflictInfo {
	// If same priority on overlapping targets, warn
	if intent1.Priority == intent2.Priority {
		return &ConflictInfo{
			ConflictingIntentID: intent2.ID,
			ConflictType:       "priority",
			Description:        fmt.Sprintf("Same priority (%d) as intent %s", intent1.Priority, intent2.ID),
			Severity:           "low",
		}
	}
	return nil
}

// Helper function
func contains(slice []string, item string) bool {
	for _, s := range slice {
		if s == item {
			return true
		}
	}
	return false
}
