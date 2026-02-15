import React, { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  CircularProgress,
  Alert,
  Button,
  Card,
  CardContent,
  Grid,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  MenuItem,
} from '@mui/material';
import api from '../services/api';

const Threats: React.FC = () => {
  const [threats, setThreats] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [openDialog, setOpenDialog] = useState(false);
  const [selectedThreat, setSelectedThreat] = useState<any>(null);
  const [mitigationType, setMitigationType] = useState('blackhole');

  const fetchThreats = async () => {
    try {
      const result = await api.getThreats();
      setThreats(result.threats || []);
      
      // Fetch security stats
      const statsResult = await api.getSecurityStats();
      setStats(statsResult);
      setError('');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load threats');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchThreats();
  }, []);

  const handleMitigate = async () => {
    if (!selectedThreat) return;
    
    try {
      await api.mitigateThreat({
        threat_id: selectedThreat.id,
        mitigation_type: mitigationType,
        target_ips: selectedThreat.source_ips,
      });
      setOpenDialog(false);
      setSelectedThreat(null);
      fetchThreats();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to mitigate threat');
    }
  };

  const getSeverityColor = (severity: string) => {
    const colors: Record<string, 'error' | 'warning' | 'info'> = {
      critical: 'error',
      high: 'warning',
      medium: 'info',
      low: 'info',
    };
    return colors[severity] || 'default';
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, 'success' | 'warning' | 'error' | 'info'> = {
      resolved: 'success',
      mitigated: 'success',
      mitigating: 'warning',
      detected: 'error',
    };
    return colors[status] || 'default';
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Security Threats
      </Typography>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {/* Stats Cards */}
      {stats && (
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={12} md={3}>
            <Card>
              <CardContent>
                <Typography color="text.secondary" variant="overline">
                  Total Threats
                </Typography>
                <Typography variant="h4">
                  {stats.total_threats || 0}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={3}>
            <Card>
              <CardContent>
                <Typography color="text.secondary" variant="overline">
                  Active Threats
                </Typography>
                <Typography variant="h4" color="error">
                  {stats.active_threats || 0}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={3}>
            <Card>
              <CardContent>
                <Typography color="text.secondary" variant="overline">
                  Critical Threats
                </Typography>
                <Typography variant="h4" color="error">
                  {stats.critical_threats || 0}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={3}>
            <Card>
              <CardContent>
                <Typography color="text.secondary" variant="overline">
                  Mitigated (24h)
                </Typography>
                <Typography variant="h4" color="success">
                  {stats.mitigated_threats || 0}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Type</TableCell>
              <TableCell>Severity</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Source IPs</TableCell>
              <TableCell>Target IPs</TableCell>
              <TableCell>Detected</TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {threats.map((threat) => (
              <TableRow key={threat.id}>
                <TableCell>{threat.threat_type}</TableCell>
                <TableCell>
                  <Chip label={threat.severity} color={getSeverityColor(threat.severity)} size="small" />
                </TableCell>
                <TableCell>
                  <Chip label={threat.status} color={getStatusColor(threat.status)} size="small" />
                </TableCell>
                <TableCell>{threat.source_ips?.slice(0, 3).join(', ') || 'N/A'}</TableCell>
                <TableCell>{threat.target_ips?.slice(0, 3).join(', ') || 'N/A'}</TableCell>
                <TableCell>
                  {new Date(threat.detected_at).toLocaleString()}
                </TableCell>
                <TableCell>
                  {threat.status === 'detected' && (
                    <Button
                      size="small"
                      variant="contained"
                      color="error"
                      onClick={() => {
                        setSelectedThreat(threat);
                        setOpenDialog(true);
                      }}
                    >
                      Mitigate
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
            {threats.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} align="center">
                  No threats detected
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Mitigation Dialog */}
      <Dialog open={openDialog} onClose={() => setOpenDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Mitigate Threat</DialogTitle>
        <DialogContent>
          <Typography variant="body2" gutterBottom>
            Threat ID: {selectedThreat?.id}
          </Typography>
          <Typography variant="body2" gutterBottom>
            Type: {selectedThreat?.threat_type}
          </Typography>
          <TextField
            fullWidth
            select
            label="Mitigation Strategy"
            value={mitigationType}
            onChange={(e) => setMitigationType(e.target.value)}
            margin="normal"
          >
            <MenuItem value="blackhole">Blackhole Routing</MenuItem>
            <MenuItem value="rate_limit">Rate Limiting</MenuItem>
            <MenuItem value="acl">Access Control List</MenuItem>
            <MenuItem value="waf">Web Application Firewall</MenuItem>
          </TextField>
          <Alert severity="warning" sx={{ mt: 2 }}>
            This will deploy the mitigation strategy to affected devices.
          </Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenDialog(false)}>Cancel</Button>
          <Button onClick={handleMitigate} variant="contained" color="error">
            Deploy Mitigation
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Threats;
