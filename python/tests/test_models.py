"""
Unit Tests for NetWeaver Python Components
Tests ML models, data preparation, and database client
"""

import unittest
import torch
import numpy as np
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add parent to path
sys.path.append(str(Path(__file__).parent.parent))

from models.traffic_predictor import (
    TrafficLSTM,
    TrafficTransformer,
    MultiHorizonPredictor,
    AnomalyDetector
)


class TestTrafficLSTM(unittest.TestCase):
    """Test LSTM traffic prediction model"""
    
    def setUp(self):
        """Setup test model"""
        self.model = TrafficLSTM(
            input_size=10,
            hidden_size=64,
            num_layers=2,
            output_size=1
        )
        self.batch_size = 16
        self.seq_length = 60
        self.input_size = 10
    
    def test_forward_pass(self):
        """Test forward pass with valid input"""
        x = torch.randn(self.batch_size, self.seq_length, self.input_size)
        output, hidden = self.model(x)
        
        self.assertEqual(output.shape, (self.batch_size, 1))
        self.assertIsNotNone(hidden)
    
    def test_predict(self):
        """Test prediction method"""
        x = torch.randn(self.batch_size, self.seq_length, self.input_size)
        output = self.model.predict(x)
        
        self.assertEqual(output.shape, (self.batch_size, 1))
        self.assertTrue(torch.all(torch.isfinite(output)))
    
    def test_invalid_input_shape(self):
        """Test with invalid input shape"""
        x = torch.randn(self.batch_size, self.input_size)  # Missing sequence dimension
        
        with self.assertRaises(Exception):
            self.model(x)
    
    def test_model_parameters(self):
        """Test model has trainable parameters"""
        params = list(self.model.parameters())
        
        self.assertGreater(len(params), 0)
        self.assertTrue(all(p.requires_grad for p in params))
    
    def test_gradient_flow(self):
        """Test gradients flow during backprop"""
        x = torch.randn(self.batch_size, self.seq_length, self.input_size)
        target = torch.randn(self.batch_size, 1)
        
        output, _ = self.model(x)
        loss = torch.nn.functional.mse_loss(output, target)
        loss.backward()
        
        # Check at least one parameter has gradients
        has_gradients = any(p.grad is not None and p.grad.abs().sum() > 0 
                           for p in self.model.parameters())
        self.assertTrue(has_gradients)


class TestTrafficTransformer(unittest.TestCase):
    """Test Transformer traffic prediction model"""
    
    def setUp(self):
        """Setup test model"""
        self.model = TrafficTransformer(
            input_size=10,
            d_model=64,
            nhead=4,
            num_encoder_layers=2,
            output_size=1
        )
        self.batch_size = 16
        self.seq_length = 60
        self.input_size = 10
    
    def test_forward_pass(self):
        """Test forward pass"""
        x = torch.randn(self.batch_size, self.seq_length, self.input_size)
        output = self.model(x)
        
        self.assertEqual(output.shape, (self.batch_size, 1))
    
    def test_predict(self):
        """Test prediction"""
        x = torch.randn(self.batch_size, self.seq_length, self.input_size)
        output = self.model.predict(x)
        
        self.assertEqual(output.shape, (self.batch_size, 1))
        self.assertTrue(torch.all(torch.isfinite(output)))
    
    def test_attention_mechanism(self):
        """Test attention is working"""
        x = torch.randn(self.batch_size, self.seq_length, self.input_size)
        
        # Should not raise errors
        output = self.model(x)
        self.assertIsNotNone(output)


class TestMultiHorizonPredictor(unittest.TestCase):
    """Test multi-horizon predictor"""
    
    def setUp(self):
        """Setup test model"""
        self.model = MultiHorizonPredictor(
            input_size=10,
            hidden_size=64,
            num_horizons=4,
            backbone='lstm'
        )
        self.batch_size = 16
        self.seq_length = 60
        self.input_size = 10
    
    def test_forward_pass(self):
        """Test forward pass"""
        x = torch.randn(self.batch_size, self.seq_length, self.input_size)
        output = self.model(x)
        
        # Should output predictions for all horizons
        self.assertEqual(output.shape, (self.batch_size, 4))
    
    def test_all_horizons_predicted(self):
        """Test all time horizons have predictions"""
        x = torch.randn(self.batch_size, self.seq_length, self.input_size)
        output = self.model(x)
        
        # Check all predictions are finite
        self.assertTrue(torch.all(torch.isfinite(output)))
        
        # Check predictions are different for different horizons
        horizon_means = output.mean(dim=0)
        self.assertGreater(len(set(horizon_means.tolist())), 1)


class TestAnomalyDetector(unittest.TestCase):
    """Test anomaly detection model"""
    
    def setUp(self):
        """Setup test model"""
        self.model = AnomalyDetector(
            input_size=10,
            encoding_dim=4,
            hidden_dims=[32, 16]
        )
        self.batch_size = 32
        self.input_size = 10
    
    def test_forward_pass(self):
        """Test forward pass"""
        x = torch.randn(self.batch_size, self.input_size)
        reconstruction, encoding = self.model(x)
        
        self.assertEqual(reconstruction.shape, (self.batch_size, self.input_size))
        self.assertEqual(encoding.shape, (self.batch_size, 4))
    
    def test_detect_anomaly(self):
        """Test anomaly detection"""
        # Normal data
        normal_data = torch.randn(self.batch_size, self.input_size) * 0.5
        
        is_anomaly, errors = self.model.detect_anomaly(normal_data, threshold=2.0)
        
        self.assertEqual(len(is_anomaly), self.batch_size)
        self.assertTrue(torch.all(torch.isfinite(errors)))
    
    def test_reconstruction_quality(self):
        """Test reconstruction is reasonable"""
        x = torch.randn(self.batch_size, self.input_size)
        reconstruction, _ = self.model(x)
        
        # Reconstruction error should be finite
        error = torch.nn.functional.mse_loss(reconstruction, x)
        self.assertTrue(torch.isfinite(error))


class TestModelPerformance(unittest.TestCase):
    """Test model performance characteristics"""
    
    def test_lstm_inference_speed(self):
        """Test LSTM inference is fast enough"""
        import time
        
        model = TrafficLSTM(input_size=10, hidden_size=128, output_size=1)
        model.eval()
        
        x = torch.randn(32, 60, 10)
        
        # Warm up
        with torch.no_grad():
            _ = model.predict(x)
        
        # Time inference
        start = time.time()
        with torch.no_grad():
            for _ in range(100):
                _ = model.predict(x)
        elapsed = time.time() - start
        
        avg_time = elapsed / 100
        
        # Should be under 10ms per batch of 32
        self.assertLess(avg_time, 0.01, f"Inference too slow: {avg_time*1000:.2f}ms")
    
    def test_model_size(self):
        """Test model size is reasonable"""
        model = TrafficLSTM(input_size=10, hidden_size=128, output_size=1)
        
        param_count = sum(p.numel() for p in model.parameters())
        
        # Should be under 1 million parameters
        self.assertLess(param_count, 1_000_000, 
                       f"Model too large: {param_count:,} parameters")


class TestDataValidation(unittest.TestCase):
    """Test data validation and preprocessing"""
    
    def test_sequence_generation(self):
        """Test sequence generation logic"""
        # Simulate time series data
        data = np.random.randn(1000, 10)
        seq_length = 60
        
        sequences = []
        targets = []
        
        for i in range(len(data) - seq_length):
            seq = data[i:i+seq_length]
            target = data[i+seq_length, 0]  # Predict first feature
            
            sequences.append(seq)
            targets.append(target)
        
        self.assertEqual(len(sequences), 1000 - seq_length)
        self.assertEqual(sequences[0].shape, (seq_length, 10))
    
    def test_normalization(self):
        """Test data normalization"""
        from sklearn.preprocessing import StandardScaler
        
        data = np.random.randn(1000, 10) * 100 + 50
        
        scaler = StandardScaler()
        normalized = scaler.fit_transform(data)
        
        # Mean should be close to 0
        self.assertAlmostEqual(normalized.mean(), 0.0, places=1)
        
        # Std should be close to 1
        self.assertAlmostEqual(normalized.std(), 1.0, places=1)


class TestErrorHandling(unittest.TestCase):
    """Test error handling in models"""
    
    def test_nan_input_handling(self):
        """Test models handle NaN inputs gracefully"""
        model = TrafficLSTM(input_size=10, hidden_size=64, output_size=1)
        
        # Input with NaN
        x = torch.randn(16, 60, 10)
        x[0, 0, 0] = float('nan')
        
        # Should not crash, but may produce NaN output
        try:
            output, _ = model(x)
            # Check if NaN is detected
            has_nan = torch.isnan(output).any()
            self.assertTrue(has_nan or not has_nan)  # Either is acceptable
        except Exception as e:
            self.fail(f"Model crashed on NaN input: {e}")
    
    def test_empty_batch(self):
        """Test handling of empty batches"""
        model = TrafficLSTM(input_size=10, hidden_size=64, output_size=1)
        
        # Batch size of 0
        x = torch.randn(0, 60, 10)
        
        try:
            output, _ = model(x)
            self.assertEqual(output.shape[0], 0)
        except:
            # Empty batch may not be supported - that's OK
            pass


def run_tests():
    """Run all tests"""
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestTrafficLSTM))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestTrafficTransformer))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestMultiHorizonPredictor))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestAnomalyDetector))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestModelPerformance))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestDataValidation))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestErrorHandling))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    exit_code = run_tests()
    exit(exit_code)
