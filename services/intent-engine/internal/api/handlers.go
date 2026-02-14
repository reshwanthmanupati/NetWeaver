package api

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/reshwanthmanupati/NetWeaver/services/intent-engine/internal/engine"
)

// Handler handles HTTP requests for the intent engine API
type Handler struct {
	engine  *engine.IntentEngine
	storage engine.Storage
}

// NewHandler creates a new API handler
func NewHandler(intentEngine *engine.IntentEngine, storage engine.Storage) *Handler {
	return &Handler{
		engine:  intentEngine,
		storage: storage,
	}
}

// CreateIntent handles POST /api/v1/intents
func (h *Handler) CreateIntent(c *gin.Context) {
	var intent engine.Intent
	
	if err := c.ShouldBindJSON(&intent); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Invalid request body",
			"details": err.Error(),
		})
		return
	}

	createdIntent, err := h.engine.CreateIntent(&intent)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to create intent",
			"details": err.Error(),
		})
		return
	}

	c.JSON(http.StatusCreated, createdIntent)
}

// ListIntents handles GET /api/v1/intents
func (h *Handler) ListIntents(c *gin.Context) {
	// Parse query parameters for filtering
	filters := make(map[string]interface{})
	
	if status := c.Query("status"); status != "" {
		filters["status"] = status
	}
	if policyType := c.Query("type"); policyType != "" {
		filters["type"] = policyType
	}

	intents, err := h.storage.ListIntents(filters)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to list intents",
			"details": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"intents": intents,
		"count":   len(intents),
	})
}

// GetIntent handles GET /api/v1/intents/:id
func (h *Handler) GetIntent(c *gin.Context) {
	id := c.Param("id")

	intent, err := h.storage.GetIntent(id)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{
			"error": "Intent not found",
			"details": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, intent)
}

// UpdateIntent handles PUT /api/v1/intents/:id
func (h *Handler) UpdateIntent(c *gin.Context) {
	id := c.Param("id")

	var intent engine.Intent
	if err := c.ShouldBindJSON(&intent); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Invalid request body",
			"details": err.Error(),
		})
		return
	}

	intent.ID = id
	
	if err := h.storage.UpdateIntent(&intent); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to update intent",
			"details": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, intent)
}

// DeleteIntent handles DELETE /api/v1/intents/:id
func (h *Handler) DeleteIntent(c *gin.Context) {
	id := c.Param("id")

	if err := h.storage.DeleteIntent(id); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to delete intent",
			"details": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "Intent deleted successfully",
		"id": id,
	})
}

// ValidateIntent handles POST /api/v1/intents/:id/validate
func (h *Handler) ValidateIntent(c *gin.Context) {
	id := c.Param("id")

	intent, err := h.storage.GetIntent(id)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{
			"error": "Intent not found",
		})
		return
	}

	validation := h.engine.ValidateIntent(intent)
	
	if validation.Valid {
		c.JSON(http.StatusOK, validation)
	} else {
		c.JSON(http.StatusBadRequest, validation)
	}
}

// DeployIntent handles POST /api/v1/intents/:id/deploy
func (h *Handler) DeployIntent(c *gin.Context) {
	id := c.Param("id")

	deployments, err := h.engine.DeployIntent(id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to deploy intent",
			"details": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "Intent deployed successfully",
		"deployments": deployments,
		"count": len(deployments),
	})
}

// RollbackIntent handles POST /api/v1/intents/:id/rollback
func (h *Handler) RollbackIntent(c *gin.Context) {
	id := c.Param("id")

	// TODO: Implement rollback logic
	c.JSON(http.StatusOK, gin.H{
		"message": "Intent rollback initiated",
		"intent_id": id,
	})
}

// CheckCompliance handles GET /api/v1/intents/:id/compliance
func (h *Handler) CheckCompliance(c *gin.Context) {
	id := c.Param("id")

	compliance, err := h.engine.CheckCompliance(id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to check compliance",
			"details": err.Error(),
		})
		return
	}

	statusCode := http.StatusOK
	if !compliance.Compliant {
		statusCode = http.StatusExpectationFailed
	}

	c.JSON(statusCode, compliance)
}

// GetIntentHistory handles GET /api/v1/intents/:id/history
func (h *Handler) GetIntentHistory(c *gin.Context) {
	id := c.Param("id")

	deployments, err := h.storage.GetDeployments(id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to get intent history",
			"details": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"intent_id": id,
		"deployments": deployments,
		"count": len(deployments),
	})
}

// ValidatePolicy handles POST /api/v1/intents/validate-policy
func (h *Handler) ValidatePolicy(c *gin.Context) {
	var intent engine.Intent
	
	if err := c.ShouldBindJSON(&intent); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Invalid request body",
			"details": err.Error(),
		})
		return
	}

	validation := h.engine.ValidateIntent(&intent)
	
	if validation.Valid {
		c.JSON(http.StatusOK, validation)
	} else {
		c.JSON(http.StatusBadRequest, validation)
	}
}

// DetectConflicts handles GET /api/v1/intents/conflicts
func (h *Handler) DetectConflicts(c *gin.Context) {
	// Get all intents and check for conflicts
	intents, err := h.storage.ListIntents(map[string]interface{}{})
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to list intents",
		})
		return
	}

	// TODO: Implement comprehensive conflict detection across all intents
	c.JSON(http.StatusOK, gin.H{
		"conflicts": []interface{}{},
		"total_intents": len(intents),
	})
}

// GetComplianceReport handles GET /api/v1/intents/compliance-report
func (h *Handler) GetComplianceReport(c *gin.Context) {
	intents, err := h.storage.ListIntents(map[string]interface{}{
		"status": "deployed",
	})
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to generate compliance report",
		})
		return
	}

	report := make([]gin.H, 0)
	compliantCount := 0
	
	for _, intent := range intents {
		compliance, err := h.engine.CheckCompliance(intent.ID)
		if err != nil {
			continue
		}

		if compliance.Compliant {
			compliantCount++
		}

		report = append(report, gin.H{
			"intent_id":   intent.ID,
			"intent_name": intent.Name,
			"compliant":   compliance.Compliant,
			"violations":  compliance.Violations,
			"checked_at":  compliance.CheckedAt,
		})
	}

	compliancePercentage := 0.0
	if len(intents) > 0 {
		compliancePercentage = float64(compliantCount) / float64(len(intents)) * 100
	}

	c.JSON(http.StatusOK, gin.H{
		"report": report,
		"summary": gin.H{
			"total_intents": len(intents),
			"compliant": compliantCount,
			"non_compliant": len(intents) - compliantCount,
			"compliance_percentage": compliancePercentage,
		},
	})
}
