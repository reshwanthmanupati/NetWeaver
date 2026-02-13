"""
Training script for traffic prediction models
Trains LSTM/Transformer models on historical network data
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
import numpy as np
from datetime import datetime, timedelta
import argparse
import yaml
import os
from pathlib import Path
from typing import Dict, Optional
import matplotlib.pyplot as plt

import sys
sys.path.append(str(Path(__file__).parent.parent))

from models.traffic_predictor import create_model, TrafficLSTM, TrafficTransformer
from training.data_preparation import TrafficDataLoader


class TrafficPredictorTrainer:
    """
    Trainer for traffic prediction models
    """
    
    def __init__(
        self,
        model: nn.Module,
        train_loader: DataLoader,
        val_loader: DataLoader,
        test_loader: DataLoader,
        config: Dict,
        device: str = 'cuda' if torch.cuda.is_available() else 'cpu'
    ):
        """
        Args:
            model: PyTorch model to train
            train_loader: Training data loader
            val_loader: Validation data loader
            test_loader: Test data loader
            config: Training configuration
            device: Device to train on
        """
        self.model = model.to(device)
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.test_loader = test_loader
        self.config = config
        self.device = device
        
        # Loss function
        self.criterion = nn.MSELoss()
        
        # Optimizer
        self.optimizer = optim.Adam(
            self.model.parameters(),
            lr=config['learning_rate'],
            weight_decay=config.get('weight_decay', 1e-5)
        )
        
        # Learning rate scheduler
        self.scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer,
            mode='min',
            factor=0.5,
            patience=5,
        )
        
        # Training history
        self.history = {
            'train_loss': [],
            'val_loss': [],
            'learning_rate': []
        }
        
        self.best_val_loss = float('inf')
        
    def train_epoch(self) -> float:
        """Train for one epoch"""
        self.model.train()
        total_loss = 0.0
        num_batches = 0
        
        for batch_idx, (sequences, targets) in enumerate(self.train_loader):
            sequences = sequences.to(self.device)
            targets = targets.to(self.device)
            
            # Forward pass
            self.optimizer.zero_grad()
            
            if isinstance(self.model, TrafficLSTM):
                outputs, _ = self.model(sequences)
            else:
                outputs = self.model(sequences)
            
            # Calculate loss
            loss = self.criterion(outputs, targets)
            
            # Backward pass
            loss.backward()
            
            # Gradient clipping to prevent exploding gradients
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            
            self.optimizer.step()
            
            total_loss += loss.item()
            num_batches += 1
            
            # Log progress
            if (batch_idx + 1) % 50 == 0:
                avg_loss = total_loss / num_batches
                print(f"  Batch {batch_idx + 1}/{len(self.train_loader)}, Loss: {avg_loss:.6f}")
        
        return total_loss / num_batches
    
    def validate(self) -> float:
        """Validate model"""
        self.model.eval()
        total_loss = 0.0
        num_batches = 0
        
        with torch.no_grad():
            for sequences, targets in self.val_loader:
                sequences = sequences.to(self.device)
                targets = targets.to(self.device)
                
                if isinstance(self.model, TrafficLSTM):
                    outputs, _ = self.model(sequences)
                else:
                    outputs = self.model(sequences)
                
                loss = self.criterion(outputs, targets)
                total_loss += loss.item()
                num_batches += 1
        
        return total_loss / num_batches
    
    def test(self) -> Dict[str, float]:
        """Test model and return metrics"""
        self.model.eval()
        total_loss = 0.0
        all_predictions = []
        all_targets = []
        
        with torch.no_grad():
            for sequences, targets in self.test_loader:
                sequences = sequences.to(self.device)
                targets = targets.to(self.device)
                
                if isinstance(self.model, TrafficLSTM):
                    outputs, _ = self.model(sequences)
                else:
                    outputs = self.model(sequences)
                
                loss = self.criterion(outputs, targets)
                total_loss += loss.item()
                
                all_predictions.append(outputs.cpu().numpy())
                all_targets.append(targets.cpu().numpy())
        
        # Concatenate all predictions and targets
        predictions = np.concatenate(all_predictions, axis=0)
        targets = np.concatenate(all_targets, axis=0)
        
        # Calculate metrics
        mse = np.mean((predictions - targets) ** 2)
        rmse = np.sqrt(mse)
        mae = np.mean(np.abs(predictions - targets))
        mape = np.mean(np.abs((targets - predictions) / (targets + 1e-8))) * 100
        
        return {
            'mse': mse,
            'rmse': rmse,
            'mae': mae,
            'mape': mape
        }
    
    def train(self, num_epochs: int, save_dir: str):
        """
        Train model for specified number of epochs
        
        Args:
            num_epochs: Number of epochs to train
            save_dir: Directory to save model checkpoints
        """
        print(f"\n=== Training on {self.device} ===")
        print(f"Model parameters: {sum(p.numel() for p in self.model.parameters()):,}")
        print(f"Training samples: {len(self.train_loader.dataset)}")
        print(f"Validation samples: {len(self.val_loader.dataset)}")
        print(f"Test samples: {len(self.test_loader.dataset)}\n")
        
        os.makedirs(save_dir, exist_ok=True)
        
        for epoch in range(num_epochs):
            print(f"Epoch {epoch + 1}/{num_epochs}")
            print("-" * 60)
            
            # Train
            train_loss = self.train_epoch()
            
            # Validate
            val_loss = self.validate()
            
            # Update scheduler
            self.scheduler.step(val_loss)
            
            # Save history
            self.history['train_loss'].append(train_loss)
            self.history['val_loss'].append(val_loss)
            self.history['learning_rate'].append(self.optimizer.param_groups[0]['lr'])
            
            print(f"Train Loss: {train_loss:.6f}, Val Loss: {val_loss:.6f}")
            print(f"Learning Rate: {self.optimizer.param_groups[0]['lr']:.2e}\n")
            
            # Save best model
            if val_loss < self.best_val_loss:
                self.best_val_loss = val_loss
                checkpoint_path = os.path.join(save_dir, 'best_model.pth')
                torch.save({
                    'epoch': epoch,
                    'model_state_dict': self.model.state_dict(),
                    'optimizer_state_dict': self.optimizer.state_dict(),
                    'val_loss': val_loss,
                    'config': self.config
                }, checkpoint_path)
                print(f"✓ Saved best model (val_loss: {val_loss:.6f})\n")
        
        # Test on best model
        print("\n=== Testing Best Model ===")
        self.load_checkpoint(os.path.join(save_dir, 'best_model.pth'))
        test_metrics = self.test()
        
        print(f"Test MSE: {test_metrics['mse']:.6f}")
        print(f"Test RMSE: {test_metrics['rmse']:.6f}")
        print(f"Test MAE: {test_metrics['mae']:.6f}")
        print(f"Test MAPE: {test_metrics['mape']:.2f}%")
        
        # Save training history
        self.save_training_plot(os.path.join(save_dir, 'training_history.png'))
        
        return test_metrics
    
    def load_checkpoint(self, checkpoint_path: str):
        """Load model from checkpoint"""
        checkpoint = torch.load(checkpoint_path, map_location=self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        print(f"Loaded model from {checkpoint_path}")
    
    def save_training_plot(self, filepath: str):
        """Save training history plot"""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5))
        
        # Loss plot
        epochs = range(1, len(self.history['train_loss']) + 1)
        ax1.plot(epochs, self.history['train_loss'], 'b-', label='Train Loss')
        ax1.plot(epochs, self.history['val_loss'], 'r-', label='Val Loss')
        ax1.set_xlabel('Epoch')
        ax1.set_ylabel('Loss')
        ax1.set_title('Training and Validation Loss')
        ax1.legend()
        ax1.grid(True)
        
        # Learning rate plot
        ax2.plot(epochs, self.history['learning_rate'], 'g-')
        ax2.set_xlabel('Epoch')
        ax2.set_ylabel('Learning Rate')
        ax2.set_title('Learning Rate Schedule')
        ax2.set_yscale('log')
        ax2.grid(True)
        
        plt.tight_layout()
        plt.savefig(filepath, dpi=150)
        plt.close()
        print(f"Training plot saved to {filepath}")


def main():
    parser = argparse.ArgumentParser(description='Train traffic prediction model')
    parser.add_argument('--config', type=str, default='configs/training.yaml',
                        help='Path to training configuration file')
    parser.add_argument('--model', type=str, default='lstm',
                        choices=['lstm', 'transformer'],
                        help='Model architecture')
    parser.add_argument('--epochs', type=int, default=50,
                        help='Number of training epochs')
    parser.add_argument('--output', type=str, default='models/checkpoints',
                        help='Output directory for model checkpoints')
    
    args = parser.parse_args()
    
    # Load configuration
    # with open(args.config, 'r') as f:
    #     config = yaml.safe_load(f)
    
    # Placeholder config for now
    config = {
        'learning_rate': 0.001,
        'weight_decay': 1e-5,
        'batch_size': 32,
        'sequence_length': 60,
        'prediction_horizon': 5
    }
    
    # Database configuration
    db_config = {
        'host': 'localhost',
        'port': 5432,
        'database': 'netweaver',
        'user': 'netweaver',
        'password': 'netweaver_secure_pass_2026'
    }
    
    print("=== NetWeaver Traffic Predictor Training ===\n")
    
    # Prepare data
    print("Preparing data...")
    data_loader = TrafficDataLoader(
        db_config=db_config,
        sequence_length=config['sequence_length'],
        prediction_horizon=config['prediction_horizon'],
        scaling="standard"
    )
    
    # For demonstration, use recent data
    end_time = datetime.now()
    start_time = end_time - timedelta(days=7)  # 7 days of data
    
    try:
        train_loader, val_loader, test_loader = data_loader.prepare_data(
            start_time=start_time,
            end_time=end_time,
            train_ratio=0.7,
            val_ratio=0.15
        )
    except Exception as e:
        print(f"Error loading data: {e}")
        print("Using synthetic data for demonstration...")
        
        # Generate synthetic data for demonstration
        from torch.utils.data import TensorDataset
        
        n_samples = 1000
        seq_length = config['sequence_length']
        n_features = 10
        
        X = torch.randn(n_samples, seq_length, n_features)
        y = torch.randn(n_samples, 1)
        
        train_size = int(0.7 * n_samples)
        val_size = int(0.15 * n_samples)
        
        train_dataset = TensorDataset(X[:train_size], y[:train_size])
        val_dataset = TensorDataset(X[train_size:train_size+val_size], y[train_size:train_size+val_size])
        test_dataset = TensorDataset(X[train_size+val_size:], y[train_size+val_size:])
        
        train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False)
        test_loader = DataLoader(test_dataset, batch_size=32, shuffle=False)
    
    # Create model
    print(f"\nCreating {args.model.upper()} model...")
    
    if args.model == 'lstm':
        model = create_model(
            'lstm',
            input_size=10,
            hidden_size=128,
            num_layers=3,
            output_size=1,
            dropout=0.2
        )
    else:
        model = create_model(
            'transformer',
            input_size=10,
            d_model=128,
            nhead=8,
            num_encoder_layers=4,
            output_size=1
        )
    
    # Create trainer
    trainer = TrafficPredictorTrainer(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        test_loader=test_loader,
        config=config
    )
    
    # Train model
    test_metrics = trainer.train(
        num_epochs=args.epochs,
        save_dir=args.output
    )
    
    # Save scaler
    data_loader.save_scaler(os.path.join(args.output, 'scaler.pkl'))
    
    print("\n=== Training Complete ===")
    print(f"Best model saved to: {args.output}/best_model.pth")
    print(f"Scaler saved to: {args.output}/scaler.pkl")


if __name__ == "__main__":
    main()
