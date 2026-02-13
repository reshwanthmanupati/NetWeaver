"""
Data preparation utilities for traffic prediction
Loads data from TimescaleDB and prepares it for ML models
"""

import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Tuple, List, Optional
from datetime import datetime, timedelta
import torch
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler, MinMaxScaler
import pickle


class TrafficDataset(Dataset):
    """
    PyTorch Dataset for network traffic time-series data
    """
    
    def __init__(
        self,
        sequences: np.ndarray,
        targets: np.ndarray,
        transform: Optional[callable] = None
    ):
        """
        Args:
            sequences: Input sequences of shape (num_samples, seq_length, num_features)
            targets: Target values of shape (num_samples, output_size)
            transform: Optional transform to apply
        """
        self.sequences = torch.FloatTensor(sequences)
        self.targets = torch.FloatTensor(targets)
        self.transform = transform
        
    def __len__(self) -> int:
        return len(self.sequences)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        sequence = self.sequences[idx]
        target = self.targets[idx]
        
        if self.transform:
            sequence = self.transform(sequence)
            
        return sequence, target


class TrafficDataLoader:
    """
    Loads and prepares traffic data from TimescaleDB
    """
    
    def __init__(
        self,
        db_config: dict,
        sequence_length: int = 60,
        prediction_horizon: int = 1,
        features: List[str] = None,
        scaling: str = "standard"
    ):
        """
        Args:
            db_config: Database connection configuration
            sequence_length: Number of time steps in input sequence
            prediction_horizon: Number of time steps to predict ahead
            features: List of feature names to extract
            scaling: "standard", "minmax", or None
        """
        self.db_config = db_config
        self.sequence_length = sequence_length
        self.prediction_horizon = prediction_horizon
        self.scaling = scaling
        
        # Default features
        if features is None:
            self.features = [
                'total_bytes', 'total_packets', 'flow_count',
                'unique_sources', 'unique_destinations',
                'tcp_ratio', 'udp_ratio', 'avg_packet_size',
                'hour_of_day', 'day_of_week'
            ]
        else:
            self.features = features
        
        # Scalers
        if scaling == "standard":
            self.scaler = StandardScaler()
        elif scaling == "minmax":
            self.scaler = MinMaxScaler()
        else:
            self.scaler = None
            
    def connect_db(self):
        """Create database connection"""
        return psycopg2.connect(
            host=self.db_config['host'],
            port=self.db_config['port'],
            database=self.db_config['database'],
            user=self.db_config['user'],
            password=self.db_config['password']
        )
    
    def fetch_flow_aggregates(
        self,
        start_time: datetime,
        end_time: datetime,
        interval: str = '1 minute'
    ) -> pd.DataFrame:
        """
        Fetch aggregated flow data from database
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            interval: Aggregation interval (e.g., '1 minute', '5 minutes')
            
        Returns:
            DataFrame with aggregated metrics
        """
        query = f"""
        SELECT
            time_bucket('{interval}', time) AS bucket,
            SUM(bytes) AS total_bytes,
            SUM(packets) AS total_packets,
            COUNT(*) AS flow_count,
            COUNT(DISTINCT source_ip) AS unique_sources,
            COUNT(DISTINCT destination_ip) AS unique_destinations,
            SUM(CASE WHEN protocol = 6 THEN 1 ELSE 0 END) AS tcp_flows,
            SUM(CASE WHEN protocol = 17 THEN 1 ELSE 0 END) AS udp_flows,
            AVG(bytes::float / NULLIF(packets, 0)) AS avg_packet_size,
            AVG(flow_duration_ms) AS avg_flow_duration
        FROM flow_records
        WHERE time BETWEEN %s AND %s
        GROUP BY bucket
        ORDER BY bucket
        """
        
        conn = self.connect_db()
        df = pd.read_sql_query(
            query,
            conn,
            params=(start_time, end_time)
        )
        conn.close()
        
        return df
    
    def engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Engineer additional features from raw data
        
        Args:
            df: Raw data DataFrame
            
        Returns:
            DataFrame with engineered features
        """
        df = df.copy()
        
        # Time-based features
        df['hour_of_day'] = df['bucket'].dt.hour
        df['day_of_week'] = df['bucket'].dt.dayofweek
        df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
        df['is_business_hours'] = ((df['hour_of_day'] >= 9) & (df['hour_of_day'] <= 17)).astype(int)
        
        # Protocol ratios
        df['tcp_ratio'] = df['tcp_flows'] / df['flow_count'].clip(lower=1)
        df['udp_ratio'] = df['udp_flows'] / df['flow_count'].clip(lower=1)
        
        # Traffic intensity features
        df['bytes_per_flow'] = df['total_bytes'] / df['flow_count'].clip(lower=1)
        df['packets_per_flow'] = df['total_packets'] / df['flow_count'].clip(lower=1)
        
        # Moving averages (lag features)
        for window in [5, 15, 60]:
            df[f'bytes_ma_{window}'] = df['total_bytes'].rolling(window=window, min_periods=1).mean()
            df[f'packets_ma_{window}'] = df['total_packets'].rolling(window=window, min_periods=1).mean()
        
        # Trend features (rate of change)
        df['bytes_diff_1'] = df['total_bytes'].diff(1).fillna(0)
        df['bytes_diff_5'] = df['total_bytes'].diff(5).fillna(0)
        
        # Fill any remaining NaN values
        df.fillna(0, inplace=True)
        
        return df
    
    def create_sequences(
        self,
        data: np.ndarray,
        target_col_idx: int = 0
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Create sequences for time-series prediction
        
        Args:
            data: Input data array of shape (num_samples, num_features)
            target_col_idx: Index of target column
            
        Returns:
            X: Input sequences of shape (num_sequences, seq_length, num_features)
            y: Target values of shape (num_sequences, 1)
        """
        X, y = [], []
        
        for i in range(len(data) - self.sequence_length - self.prediction_horizon + 1):
            # Input sequence
            sequence = data[i:i + self.sequence_length]
            
            # Target value (prediction_horizon steps ahead)
            target = data[i + self.sequence_length + self.prediction_horizon - 1, target_col_idx]
            
            X.append(sequence)
            y.append(target)
        
        return np.array(X), np.array(y).reshape(-1, 1)
    
    def prepare_data(
        self,
        start_time: datetime,
        end_time: datetime,
        train_ratio: float = 0.7,
        val_ratio: float = 0.15,
        interval: str = '1 minute'
    ) -> Tuple[DataLoader, DataLoader, DataLoader]:
        """
        Prepare training, validation, and test data loaders
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            train_ratio: Proportion of data for training
            val_ratio: Proportion of data for validation
            interval: Data aggregation interval
            
        Returns:
            train_loader, val_loader, test_loader
        """
        print(f"Fetching data from {start_time} to {end_time}...")
        
        # Fetch data
        df = self.fetch_flow_aggregates(start_time, end_time, interval)
        print(f"Fetched {len(df)} records")
        
        # Engineer features
        print("Engineering features...")
        df = self.engineer_features(df)
        
        # Select feature columns
        feature_cols = [col for col in self.features if col in df.columns]
        data = df[feature_cols].values
        
        print(f"Using {len(feature_cols)} features: {feature_cols}")
        
        # Scale data
        if self.scaler:
            print(f"Scaling data using {self.scaling}...")
            data = self.scaler.fit_transform(data)
        
        # Create sequences
        print("Creating sequences...")
        X, y = self.create_sequences(data, target_col_idx=0)
        print(f"Created {len(X)} sequences")
        
        # Split data
        n_samples = len(X)
        train_size = int(n_samples * train_ratio)
        val_size = int(n_samples * val_ratio)
        
        X_train = X[:train_size]
        y_train = y[:train_size]
        
        X_val = X[train_size:train_size + val_size]
        y_val = y[train_size:train_size + val_size]
        
        X_test = X[train_size + val_size:]
        y_test = y[train_size + val_size:]
        
        print(f"Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")
        
        # Create datasets
        train_dataset = TrafficDataset(X_train, y_train)
        val_dataset = TrafficDataset(X_val, y_val)
        test_dataset = TrafficDataset(X_test, y_test)
        
        # Create data loaders
        train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True, num_workers=0)
        val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False, num_workers=0)
        test_loader = DataLoader(test_dataset, batch_size=32, shuffle=False, num_workers=0)
        
        return train_loader, val_loader, test_loader
    
    def save_scaler(self, filepath: str):
        """Save scaler for later use"""
        if self.scaler:
            with open(filepath, 'wb') as f:
                pickle.dump(self.scaler, f)
            print(f"Scaler saved to {filepath}")
    
    def load_scaler(self, filepath: str):
        """Load saved scaler"""
        with open(filepath, 'rb') as f:
            self.scaler = pickle.load(f)
        print(f"Scaler loaded from {filepath}")


class RealTimePredictor:
    """
    Real-time traffic prediction using trained models
    """
    
    def __init__(
        self,
        model: torch.nn.Module,
        scaler: Optional[StandardScaler] = None,
        device: str = 'cpu'
    ):
        """
        Args:
            model: Trained PyTorch model
            scaler: Fitted scaler for input normalization
            device: 'cpu' or 'cuda'
        """
        self.model = model
        self.scaler = scaler
        self.device = device
        self.model.to(device)
        self.model.eval()
    
    def predict(
        self,
        sequence: np.ndarray
    ) -> Tuple[float, float]:
        """
        Make prediction for a single sequence
        
        Args:
            sequence: Input sequence of shape (seq_length, num_features)
            
        Returns:
            prediction: Predicted value
            confidence: Confidence score (placeholder for now)
        """
        # Scale input
        if self.scaler:
            sequence = self.scaler.transform(sequence)
        
        # Convert to tensor
        x = torch.FloatTensor(sequence).unsqueeze(0).to(self.device)
        
        # Predict
        with torch.no_grad():
            output = self.model.predict(x)
            prediction = output.cpu().numpy()[0, 0]
        
        # Inverse scale if needed
        if self.scaler:
            # Create dummy array for inverse transform
            dummy = np.zeros((1, sequence.shape[1]))
            dummy[0, 0] = prediction
            prediction = self.scaler.inverse_transform(dummy)[0, 0]
        
        # Placeholder confidence score
        confidence = 0.85
        
        return float(prediction), confidence
    
    def predict_batch(
        self,
        sequences: np.ndarray
    ) -> np.ndarray:
        """
        Make predictions for multiple sequences
        
        Args:
            sequences: Input sequences of shape (batch_size, seq_length, num_features)
            
        Returns:
            predictions: Array of predictions
        """
        if self.scaler:
            # Scale each sequence
            scaled_sequences = []
            for seq in sequences:
                scaled_seq = self.scaler.transform(seq)
                scaled_sequences.append(scaled_seq)
            sequences = np.array(scaled_sequences)
        
        x = torch.FloatTensor(sequences).to(self.device)
        
        with torch.no_grad():
            output = self.model.predict(x)
            predictions = output.cpu().numpy()
        
        return predictions


if __name__ == "__main__":
    # Example usage
    print("=== Traffic Data Preparation ===\n")
    
    # Database configuration
    db_config = {
        'host': 'localhost',
        'port': 5432,
        'database': 'netweaver',
        'user': 'netweaver',
        'password': 'netweaver_secure_pass_2026'
    }
    
    # Create data loader
    data_loader = TrafficDataLoader(
        db_config=db_config,
        sequence_length=60,
        prediction_horizon=5,
        scaling="standard"
    )
    
    print("Data loader initialized")
    print(f"Sequence length: {data_loader.sequence_length}")
    print(f"Prediction horizon: {data_loader.prediction_horizon}")
    print(f"Features: {data_loader.features}")
