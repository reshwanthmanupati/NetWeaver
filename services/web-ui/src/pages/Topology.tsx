import React, { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  CircularProgress,
  Alert,
  Card,
  CardContent,
} from '@mui/material';
import api from '../services/api';

const Topology: React.FC = () => {
  const [devices, setDevices] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchDevices = async () => {
      try {
        const result = await api.getDevices();
        setDevices(result.devices || []);
        setError('');
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to load devices');
      } finally {
        setLoading(false);
      }
    };

    fetchDevices();
  }, []);

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
        Network Topology
      </Typography>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Paper sx={{ p: 3, minHeight: 600 }}>
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: 500,
          }}
        >
          <Typography variant="h6" color="text.secondary" gutterBottom>
            Interactive Network Topology Visualization
          </Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            Cytoscape.js visualization would be rendered here
          </Typography>
          
          {/* Device Summary */}
          <Box sx={{ mt: 4, width: '100%' }}>
            <Typography variant="h6" gutterBottom>
              Device Summary
            </Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: 2 }}>
              {devices.map((device) => (
                <Card key={device.id}>
                  <CardContent>
                    <Typography variant="subtitle1">{device.hostname}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      {device.device_type} ({device.vendor})
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {device.ip_address}
                    </Typography>
                    <Typography variant="caption" color={device.status === 'active' ? 'success.main' : 'error.main'}>
                      {device.status}
                    </Typography>
                  </CardContent>
                </Card>
              ))}
            </Box>
          </Box>
        </Box>
      </Paper>
    </Box>
  );
};

export default Topology;
