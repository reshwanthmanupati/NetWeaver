"""
Traffic Prediction Models using LSTM and Transformer architectures
Forecasts network traffic patterns for capacity planning and optimization
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Optional
import math


class TrafficLSTM(nn.Module):
    """
    LSTM-based traffic prediction model
    Predicts future traffic volume based on historical time-series data
    
    Architecture:
    - Multi-layer LSTM with dropout
    - Fully connected output layer
    - Supports multi-step ahead forecasting
    """
    
    def __init__(
        self,
        input_size: int = 10,
        hidden_size: int = 128,
        num_layers: int = 3,
        output_size: int = 1,
        dropout: float = 0.2,
        bidirectional: bool = False
    ):
        """
        Args:
            input_size: Number of input features (e.g., bytes, packets, flow count)
            hidden_size: LSTM hidden state dimension
            num_layers: Number of stacked LSTM layers
            output_size: Number of future time steps to predict
            dropout: Dropout probability for regularization
            bidirectional: Whether to use bidirectional LSTM
        """
        super(TrafficLSTM, self).__init__()
        
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.output_size = output_size
        self.bidirectional = bidirectional
        
        # LSTM layers
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0,
            batch_first=True,
            bidirectional=bidirectional
        )
        
        # Fully connected layers
        fc_input_size = hidden_size * 2 if bidirectional else hidden_size
        self.fc1 = nn.Linear(fc_input_size, 64)
        self.fc2 = nn.Linear(64, 32)
        self.fc3 = nn.Linear(32, output_size)
        
        self.dropout = nn.Dropout(dropout)
        self.relu = nn.ReLU()
        
    def forward(
        self, 
        x: torch.Tensor,
        hidden: Optional[Tuple[torch.Tensor, torch.Tensor]] = None
    ) -> Tuple[torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]:
        """
        Forward pass
        
        Args:
            x: Input tensor of shape (batch_size, sequence_length, input_size)
            hidden: Optional initial hidden state
            
        Returns:
            output: Predicted values of shape (batch_size, output_size)
            hidden: Final hidden state
        """
        # LSTM forward pass
        lstm_out, hidden = self.lstm(x, hidden)
        
        # Use the last time step output
        last_output = lstm_out[:, -1, :]
        
        # Fully connected layers with activation and dropout
        out = self.relu(self.fc1(last_output))
        out = self.dropout(out)
        out = self.relu(self.fc2(out))
        out = self.dropout(out)
        out = self.fc3(out)
        
        return out, hidden
    
    def predict(self, x: torch.Tensor) -> torch.Tensor:
        """
        Make predictions without returning hidden state
        
        Args:
            x: Input tensor of shape (batch_size, sequence_length, input_size)
            
        Returns:
            Predictions of shape (batch_size, output_size)
        """
        self.eval()
        with torch.no_grad():
            output, _ = self.forward(x)
        return output


class PositionalEncoding(nn.Module):
    """Positional encoding for Transformer models"""
    
    def __init__(self, d_model: int, max_len: int = 5000):
        super(PositionalEncoding, self).__init__()
        
        # Create positional encoding matrix
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)  # Add batch dimension
        
        self.register_buffer('pe', pe)
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Add positional encoding to input"""
        x = x + self.pe[:, :x.size(1), :]
        return x


class TrafficTransformer(nn.Module):
    """
    Transformer-based traffic prediction model
    More powerful than LSTM for capturing long-range dependencies
    
    Architecture:
    - Input embedding + positional encoding
    - Multi-head self-attention layers
    - Feed-forward network
    - Output projection layer
    """
    
    def __init__(
        self,
        input_size: int = 10,
        d_model: int = 128,
        nhead: int = 8,
        num_encoder_layers: int = 4,
        dim_feedforward: int = 512,
        dropout: float = 0.1,
        output_size: int = 1,
        max_seq_length: int = 1000
    ):
        """
        Args:
            input_size: Number of input features
            d_model: Dimension of model embeddings
            nhead: Number of attention heads
            num_encoder_layers: Number of transformer encoder layers
            dim_feedforward: Dimension of feedforward network
            dropout: Dropout rate
            output_size: Number of future time steps to predict
            max_seq_length: Maximum sequence length for positional encoding
        """
        super(TrafficTransformer, self).__init__()
        
        self.input_size = input_size
        self.d_model = d_model
        self.output_size = output_size
        
        # Input projection
        self.input_projection = nn.Linear(input_size, d_model)
        
        # Positional encoding
        self.positional_encoding = PositionalEncoding(d_model, max_seq_length)
        
        # Transformer encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            batch_first=True
        )
        self.transformer_encoder = nn.TransformerEncoder(
            encoder_layer,
            num_layers=num_encoder_layers
        )
        
        # Output layers
        self.fc1 = nn.Linear(d_model, 128)
        self.fc2 = nn.Linear(128, 64)
        self.fc3 = nn.Linear(64, output_size)
        
        self.dropout = nn.Dropout(dropout)
        self.relu = nn.ReLU()
        
    def forward(self, x: torch.Tensor, mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        """
        Forward pass
        
        Args:
            x: Input tensor of shape (batch_size, sequence_length, input_size)
            mask: Optional attention mask
            
        Returns:
            output: Predicted values of shape (batch_size, output_size)
        """
        # Project input to d_model dimensions
        x = self.input_projection(x)
        
        # Add positional encoding
        x = self.positional_encoding(x)
        
        # Transformer encoding
        encoded = self.transformer_encoder(x, mask=mask)
        
        # Use the last time step output
        last_output = encoded[:, -1, :]
        
        # Output layers
        out = self.relu(self.fc1(last_output))
        out = self.dropout(out)
        out = self.relu(self.fc2(out))
        out = self.dropout(out)
        out = self.fc3(out)
        
        return out
    
    def predict(self, x: torch.Tensor) -> torch.Tensor:
        """
        Make predictions
        
        Args:
            x: Input tensor of shape (batch_size, sequence_length, input_size)
            
        Returns:
            Predictions of shape (batch_size, output_size)
        """
        self.eval()
        with torch.no_grad():
            output = self.forward(x)
        return output


class MultiHorizonPredictor(nn.Module):
    """
    Multi-horizon traffic predictor
    Predicts traffic at multiple future time horizons (e.g., 5min, 15min, 1hr, 24hr)
    """
    
    def __init__(
        self,
        input_size: int = 10,
        hidden_size: int = 128,
        num_horizons: int = 4,
        backbone: str = "lstm"
    ):
        """
        Args:
            input_size: Number of input features
            hidden_size: Hidden layer dimension
            num_horizons: Number of prediction horizons
            backbone: "lstm" or "transformer"
        """
        super(MultiHorizonPredictor, self).__init__()
        
        self.num_horizons = num_horizons
        self.backbone = backbone
        
        if backbone == "lstm":
            self.encoder = TrafficLSTM(
                input_size=input_size,
                hidden_size=hidden_size,
                output_size=hidden_size,
                num_layers=3
            )
        elif backbone == "transformer":
            self.encoder = TrafficTransformer(
                input_size=input_size,
                d_model=hidden_size,
                output_size=hidden_size
            )
        else:
            raise ValueError(f"Unknown backbone: {backbone}")
        
        # Separate prediction heads for each horizon
        self.horizon_heads = nn.ModuleList([
            nn.Sequential(
                nn.Linear(hidden_size, 64),
                nn.ReLU(),
                nn.Dropout(0.1),
                nn.Linear(64, 1)
            )
            for _ in range(num_horizons)
        ])
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass
        
        Args:
            x: Input tensor of shape (batch_size, sequence_length, input_size)
            
        Returns:
            predictions: Tensor of shape (batch_size, num_horizons)
        """
        # Encode input sequence
        if self.backbone == "lstm":
            encoded, _ = self.encoder(x)
        else:
            encoded = self.encoder(x)
        
        # Predict for each horizon
        predictions = []
        for head in self.horizon_heads:
            pred = head(encoded)
            predictions.append(pred)
        
        predictions = torch.cat(predictions, dim=1)
        return predictions
    
    def predict(self, x: torch.Tensor) -> torch.Tensor:
        """Make predictions"""
        self.eval()
        with torch.no_grad():
            output = self.forward(x)
        return output


class AnomalyDetector(nn.Module):
    """
    Autoencoder-based anomaly detector for network traffic
    Detects unusual traffic patterns by reconstruction error
    """
    
    def __init__(
        self,
        input_size: int = 10,
        encoding_dim: int = 32,
        hidden_dims: list = [128, 64]
    ):
        """
        Args:
            input_size: Number of input features
            encoding_dim: Dimension of encoded representation
            hidden_dims: List of hidden layer dimensions
        """
        super(AnomalyDetector, self).__init__()
        
        # Encoder
        encoder_layers = []
        prev_dim = input_size
        for hidden_dim in hidden_dims:
            encoder_layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.ReLU(),
                nn.BatchNorm1d(hidden_dim),
                nn.Dropout(0.2)
            ])
            prev_dim = hidden_dim
        encoder_layers.append(nn.Linear(prev_dim, encoding_dim))
        self.encoder = nn.Sequential(*encoder_layers)
        
        # Decoder
        decoder_layers = []
        prev_dim = encoding_dim
        for hidden_dim in reversed(hidden_dims):
            decoder_layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.ReLU(),
                nn.BatchNorm1d(hidden_dim),
                nn.Dropout(0.2)
            ])
            prev_dim = hidden_dim
        decoder_layers.append(nn.Linear(prev_dim, input_size))
        self.decoder = nn.Sequential(*decoder_layers)
        
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass
        
        Args:
            x: Input tensor of shape (batch_size, input_size)
            
        Returns:
            reconstruction: Reconstructed input
            encoding: Encoded representation
        """
        encoding = self.encoder(x)
        reconstruction = self.decoder(encoding)
        return reconstruction, encoding
    
    def detect_anomaly(
        self,
        x: torch.Tensor,
        threshold: float = 2.0
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Detect anomalies based on reconstruction error
        
        Args:
            x: Input tensor
            threshold: Anomaly threshold (multiplier of mean reconstruction error)
            
        Returns:
            is_anomaly: Boolean tensor indicating anomalies
            reconstruction_errors: Reconstruction error for each sample
        """
        self.eval()
        with torch.no_grad():
            reconstruction, _ = self.forward(x)
            reconstruction_errors = torch.mean((x - reconstruction) ** 2, dim=1)
            
            # Calculate dynamic threshold
            mean_error = torch.mean(reconstruction_errors)
            std_error = torch.std(reconstruction_errors)
            threshold_value = mean_error + threshold * std_error
            
            is_anomaly = reconstruction_errors > threshold_value
            
        return is_anomaly, reconstruction_errors


def create_model(model_type: str, **kwargs) -> nn.Module:
    """
    Factory function to create models
    
    Args:
        model_type: Type of model ("lstm", "transformer", "multi_horizon", "anomaly")
        **kwargs: Model-specific parameters
        
    Returns:
        Initialized model
    """
    if model_type == "lstm":
        return TrafficLSTM(**kwargs)
    elif model_type == "transformer":
        return TrafficTransformer(**kwargs)
    elif model_type == "multi_horizon":
        return MultiHorizonPredictor(**kwargs)
    elif model_type == "anomaly":
        return AnomalyDetector(**kwargs)
    else:
        raise ValueError(f"Unknown model type: {model_type}")


if __name__ == "__main__":
    # Example usage
    print("=== Traffic Prediction Models ===\n")
    
    # LSTM model
    lstm_model = TrafficLSTM(input_size=10, hidden_size=128, output_size=1)
    print(f"LSTM Model: {sum(p.numel() for p in lstm_model.parameters()):,} parameters")
    
    # Transformer model
    transformer_model = TrafficTransformer(input_size=10, d_model=128, output_size=1)
    print(f"Transformer Model: {sum(p.numel() for p in transformer_model.parameters()):,} parameters")
    
    # Multi-horizon predictor
    multi_model = MultiHorizonPredictor(input_size=10, hidden_size=128, num_horizons=4)
    print(f"Multi-Horizon Model: {sum(p.numel() for p in multi_model.parameters()):,} parameters")
    
    # Anomaly detector
    anomaly_model = AnomalyDetector(input_size=10, encoding_dim=32)
    print(f"Anomaly Detector: {sum(p.numel() for p in anomaly_model.parameters()):,} parameters")
    
    # Test forward pass
    batch_size = 32
    seq_length = 60  # 1 hour of 1-minute samples
    input_size = 10
    
    x = torch.randn(batch_size, seq_length, input_size)
    
    print("\n=== Testing Forward Pass ===")
    lstm_out, _ = lstm_model(x)
    print(f"LSTM output shape: {lstm_out.shape}")
    
    transformer_out = transformer_model(x)
    print(f"Transformer output shape: {transformer_out.shape}")
    
    multi_out = multi_model(x)
    print(f"Multi-horizon output shape: {multi_out.shape}")
    
    # Test anomaly detection
    x_anomaly = torch.randn(batch_size, input_size)
    is_anomaly, errors = anomaly_model.detect_anomaly(x_anomaly)
    print(f"Anomaly detection: {is_anomaly.sum().item()}/{batch_size} anomalies detected")
