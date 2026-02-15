import React, { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  Button,
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
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  MenuItem,
} from '@mui/material';
import { Add as AddIcon } from '@mui/icons-material';
import api from '../services/api';

const Devices: React.FC = () => {
  const [devices, setDevices] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [openDialog, setOpenDialog] = useState(false);
  const [newDevice, setNewDevice] = useState({
    hostname: '',
    ip_address: '',
    device_type: 'router',
    vendor: 'cisco',
    credentials: { username: 'admin', password: '' },
  });

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

  useEffect(() => {
    fetchDevices();
  }, []);

  const handleRegister = async () => {
    try {
      await api.registerDevice(newDevice);
      setOpenDialog(false);
      setNewDevice({
        hostname: '',
        ip_address: '',
        device_type: 'router',
        vendor: 'cisco',
        credentials: { username: 'admin', password: '' },
      });
      fetchDevices();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to register device');
    }
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, 'success' | 'warning' | 'error'> = {
      active: 'success',
      inactive: 'warning',
      error: 'error',
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
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">Devices</Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => setOpenDialog(true)}
        >
          Register Device
        </Button>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Hostname</TableCell>
              <TableCell>IP Address</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Vendor</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Registered</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {devices.map((device) => (
              <TableRow key={device.id}>
                <TableCell>{device.hostname}</TableCell>
                <TableCell>{device.ip_address}</TableCell>
                <TableCell>{device.device_type}</TableCell>
                <TableCell>{device.vendor}</TableCell>
                <TableCell>
                  <Chip label={device.status} color={getStatusColor(device.status)} size="small" />
                </TableCell>
                <TableCell>
                  {new Date(device.registered_at).toLocaleDateString()}
                </TableCell>
              </TableRow>
            ))}
            {devices.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} align="center">
                  No devices found
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Register Dialog */}
      <Dialog open={openDialog} onClose={() => setOpenDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Register New Device</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            label="Hostname"
            value={newDevice.hostname}
            onChange={(e) => setNewDevice({ ...newDevice, hostname: e.target.value })}
            margin="normal"
          />
          <TextField
            fullWidth
            label="IP Address"
            value={newDevice.ip_address}
            onChange={(e) => setNewDevice({ ...newDevice, ip_address: e.target.value })}
            margin="normal"
          />
          <TextField
            fullWidth
            select
            label="Device Type"
            value={newDevice.device_type}
            onChange={(e) => setNewDevice({ ...newDevice, device_type: e.target.value })}
            margin="normal"
          >
            <MenuItem value="router">Router</MenuItem>
            <MenuItem value="switch">Switch</MenuItem>
            <MenuItem value="firewall">Firewall</MenuItem>
          </TextField>
          <TextField
            fullWidth
            select
            label="Vendor"
            value={newDevice.vendor}
            onChange={(e) => setNewDevice({ ...newDevice, vendor: e.target.value })}
            margin="normal"
          >
            <MenuItem value="cisco">Cisco</MenuItem>
            <MenuItem value="juniper">Juniper</MenuItem>
            <MenuItem value="arista">Arista</MenuItem>
          </TextField>
          <TextField
            fullWidth
            label="Username"
            value={newDevice.credentials.username}
            onChange={(e) => setNewDevice({
              ...newDevice,
              credentials: { ...newDevice.credentials, username: e.target.value }
            })}
            margin="normal"
          />
          <TextField
            fullWidth
            label="Password"
            type="password"
            value={newDevice.credentials.password}
            onChange={(e) => setNewDevice({
              ...newDevice,
              credentials: { ...newDevice.credentials, password: e.target.value }
            })}
            margin="normal"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenDialog(false)}>Cancel</Button>
          <Button onClick={handleRegister} variant="contained">Register</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Devices;
