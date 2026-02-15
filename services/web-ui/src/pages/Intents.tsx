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
} from '@mui/material';
import { Add as AddIcon } from '@mui/icons-material';
import api from '../services/api';

const Intents: React.FC = () => {
  const [intents, setIntents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [openDialog, setOpenDialog] = useState(false);
  const [newIntent, setNewIntent] = useState({
    name: '',
    description: '',
    priority: 100,
  });

  const fetchIntents = async () => {
    try {
      const result = await api.getIntents();
      setIntents(result.intents || []);
      setError('');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load intents');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIntents();
  }, []);

  const handleCreate = async () => {
    try {
      await api.createIntent(newIntent);
      setOpenDialog(false);
      setNewIntent({ name: '', description: '', priority: 100 });
      fetchIntents();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create intent');
    }
  };

  const handleDelete = async (id: string) => {
    if (window.confirm('Are you sure you want to delete this intent?')) {
      try {
        await api.deleteIntent(id);
        fetchIntents();
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to delete intent');
      }
    }
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, 'success' | 'warning' | 'error' | 'info'> = {
      deployed: 'success',
      pending: 'warning',
      failed: 'error',
      draft: 'info',
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
        <Typography variant="h4">Intents</Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => setOpenDialog(true)}
        >
          Create Intent
        </Button>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Name</TableCell>
              <TableCell>Description</TableCell>
              <TableCell>Priority</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Created</TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {intents.map((intent) => (
              <TableRow key={intent.id}>
                <TableCell>{intent.name}</TableCell>
                <TableCell>{intent.description}</TableCell>
                <TableCell>{intent.priority}</TableCell>
                <TableCell>
                  <Chip label={intent.status} color={getStatusColor(intent.status)} size="small" />
                </TableCell>
                <TableCell>
                  {new Date(intent.created_at).toLocaleDateString()}
                </TableCell>
                <TableCell>
                  <Button size="small" onClick={() => handleDelete(intent.id)}>
                    Delete
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {intents.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} align="center">
                  No intents found
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Create Dialog */}
      <Dialog open={openDialog} onClose={() => setOpenDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Create New Intent</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            label="Name"
            value={newIntent.name}
            onChange={(e) => setNewIntent({ ...newIntent, name: e.target.value })}
            margin="normal"
          />
          <TextField
            fullWidth
            label="Description"
            value={newIntent.description}
            onChange={(e) => setNewIntent({ ...newIntent, description: e.target.value })}
            margin="normal"
            multiline
            rows={2}
          />
          <TextField
            fullWidth
            label="Priority"
            type="number"
            value={newIntent.priority}
            onChange={(e) => setNewIntent({ ...newIntent, priority: parseInt(e.target.value) })}
            margin="normal"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenDialog(false)}>Cancel</Button>
          <Button onClick={handleCreate} variant="contained">Create</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Intents;
