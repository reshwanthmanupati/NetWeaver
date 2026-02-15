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
} from '@mui/material';
import api from '../services/api';

const Incidents: React.FC = () => {
  const [incidents, setIncidents] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchIncidents = async () => {
    try {
      const result = await api.getIncidents();
      setIncidents(result.incidents || []);
      
      // Fetch MTTR stats
      const mttrResult = await api.getMTTR('24h');
      setStats(mttrResult);
      setError('');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load incidents');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIncidents();
  }, []);

  const handleResolve = async (id: string) => {
    try {
      await api.resolveIncident(id, { resolution: 'Manually resolved', resolved_by: 'admin' });
      fetchIncidents();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to resolve incident');
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
      remediated: 'success',
      remediating: 'warning',
      detected: 'error',
      failed: 'error',
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
        Incidents
      </Typography>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {/* Stats Cards */}
      {stats && (
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={12} md={3}>
            <Card>
              <CardContent>
                <Typography color="text.secondary" variant="overline">
                  Total Incidents
                </Typography>
                <Typography variant="h4">
                  {stats.total_incidents || 0}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={3}>
            <Card>
              <CardContent>
                <Typography color="text.secondary" variant="overline">
                  Mean Time to Resolution
                </Typography>
                <Typography variant="h4">
                  {stats.mttr_seconds ? `${Math.round(stats.mttr_seconds)}s` : 'N/A'}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={3}>
            <Card>
              <CardContent>
                <Typography color="text.secondary" variant="overline">
                  Auto-Resolved
                </Typography>
                <Typography variant="h4">
                  {stats.auto_resolved || 0}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={3}>
            <Card>
              <CardContent>
                <Typography color="text.secondary" variant="overline">
                  Active Incidents
                </Typography>
                <Typography variant="h4">
                  {incidents.filter((i) => i.status === 'detected' || i.status === 'remediating').length}
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
              <TableCell>Device</TableCell>
              <TableCell>Detected</TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {incidents.map((incident) => (
              <TableRow key={incident.id}>
                <TableCell>{incident.incident_type}</TableCell>
                <TableCell>
                  <Chip label={incident.severity} color={getSeverityColor(incident.severity)} size="small" />
                </TableCell>
                <TableCell>
                  <Chip label={incident.status} color={getStatusColor(incident.status)} size="small" />
                </TableCell>
                <TableCell>{incident.device_id || 'N/A'}</TableCell>
                <TableCell>
                  {new Date(incident.detected_at).toLocaleString()}
                </TableCell>
                <TableCell>
                  {(incident.status === 'detected' || incident.status === 'failed') && (
                    <Button size="small" onClick={() => handleResolve(incident.id)}>
                      Resolve
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
            {incidents.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} align="center">
                  No incidents found
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};

export default Incidents;
