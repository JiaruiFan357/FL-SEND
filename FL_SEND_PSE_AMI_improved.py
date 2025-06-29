# FL-SEND-PSE: Federated Learning for Speaker Embedding-aware Neural Diarization with Power-Set Encoding
import os
import pickle
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import torchaudio
import librosa
import matplotlib.pyplot as plt
from collections import OrderedDict, defaultdict
from typing import List, Tuple, Dict, Any
from torch.utils.data import DataLoader, Dataset, random_split
import flwr as fl
from flwr.client import NumPyClient
from flwr.common import Context, Metrics
from pyannote.core import Segment, Annotation
from pyannote.metrics.diarization import DiarizationErrorRate
from speechbrain.pretrained import EncoderClassifier
from datasets import load_dataset
import seaborn as sns
from tqdm import tqdm
import logging
from sklearn.metrics import confusion_matrix
import json
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set random seeds for reproducibility
def set_seed(seed: int = 42):
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    np.random.seed(seed)
    random.seed(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

set_seed(42)

# Set device
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
logger.info(f"Using device: {device}")

class PowerSetEncoder:
    """Power Set Encoding for overlapping speech diarization."""
    def __init__(self, max_speakers: int = 4):
        self.max_speakers = max_speakers
        self.num_classes = 2 ** max_speakers
        
    def encode(self, speaker_labels: List[int]) -> int:
        """Encode speaker labels into a single integer using power set encoding."""
        if len(speaker_labels) > self.max_speakers:
            raise ValueError(f"Number of speakers exceeds maximum ({self.max_speakers})")
        
        # Pad with zeros if necessary
        padded_labels = speaker_labels + [0] * (self.max_speakers - len(speaker_labels))
        return sum(label * (2 ** i) for i, label in enumerate(padded_labels))
    
    def decode(self, encoded_value: int) -> List[int]:
        """Decode an encoded value back into speaker labels."""
        binary = format(encoded_value, f'0{self.max_speakers}b')
        return [int(bit) for bit in binary]

class SENDModel(nn.Module):
    """Speaker Embedding-aware Neural Diarization model with Power-Set Encoding."""
    def __init__(self, input_dim: int = 80, hidden_dim: int = 256, num_classes: int = 16):
        super().__init__()
        self.conv1 = nn.Conv1d(input_dim, hidden_dim, kernel_size=3, padding=1)
        self.conv2 = nn.Conv1d(hidden_dim, hidden_dim, kernel_size=3, padding=1)
        self.conv3 = nn.Conv1d(hidden_dim, hidden_dim, kernel_size=3, padding=1)
        
        self.lstm = nn.LSTM(
            input_size=hidden_dim,
            hidden_size=hidden_dim,
            num_layers=2,
            batch_first=True,
            bidirectional=True
        )
        
        self.attention = nn.MultiheadAttention(
            embed_dim=hidden_dim * 2,
            num_heads=4,
            batch_first=True
        )
        
        self.fc = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(hidden_dim, num_classes)
        )
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Input shape: (batch_size, sequence_length, input_dim)
        x = x.transpose(1, 2)  # (batch_size, input_dim, sequence_length)
        
        # Convolutional layers
        x = F.relu(self.conv1(x))
        x = F.relu(self.conv2(x))
        x = F.relu(self.conv3(x))
        
        # Transpose back for LSTM
        x = x.transpose(1, 2)  # (batch_size, sequence_length, hidden_dim)
        
        # LSTM layers
        x, _ = self.lstm(x)
        
        # Self-attention
        x, _ = self.attention(x, x, x)
        
        # Final classification
        x = self.fc(x)
        
        return x

class OverlappingSpeechDataset(Dataset):
    """Dataset for overlapping speech diarization."""
    def __init__(self, features: np.ndarray, labels: np.ndarray, speaker_encoder: EncoderClassifier):
        self.features = features
        self.labels = labels
        self.speaker_encoder = speaker_encoder
        
    def __len__(self) -> int:
        return len(self.features)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        feature = torch.tensor(self.features[idx], dtype=torch.float32)
        label = torch.tensor(self.labels[idx], dtype=torch.long)
        
        # Extract speaker embeddings
        with torch.no_grad():
            speaker_embedding = self.speaker_encoder.encode_batch(feature.unsqueeze(0))
            speaker_embedding = speaker_embedding.squeeze(0)
        
        return feature, speaker_embedding, label

class SENDClient(NumPyClient):
    """Federated Learning client for SEND model."""
    def __init__(
        self,
        model: SENDModel,
        train_loader: DataLoader,
        val_loader: DataLoader,
        device: torch.device,
        power_set_encoder: PowerSetEncoder
    ):
        self.model = model
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.device = device
        self.power_set_encoder = power_set_encoder
        self.optimizer = optim.Adam(model.parameters())
        self.criterion = nn.CrossEntropyLoss()
        
    def get_parameters(self, config):
        return [val.cpu().numpy() for _, val in self.model.state_dict().items()]
    
    def set_parameters(self, parameters):
        params_dict = zip(self.model.state_dict().keys(), parameters)
        state_dict = OrderedDict({k: torch.tensor(v) for k, v in params_dict})
        self.model.load_state_dict(state_dict, strict=True)
    
    def fit(self, parameters, config):
        self.set_parameters(parameters)
        
        # Train the model
        self.model.train()
        train_loss = 0.0
        for batch_idx, (features, speaker_embeddings, labels) in enumerate(self.train_loader):
            features, speaker_embeddings, labels = (
                features.to(self.device),
                speaker_embeddings.to(self.device),
                labels.to(self.device)
            )
            
            self.optimizer.zero_grad()
            outputs = self.model(features)
            loss = self.criterion(outputs, labels)
            loss.backward()
            self.optimizer.step()
            
            train_loss += loss.item()
        
        return self.get_parameters({}), len(self.train_loader), {"train_loss": train_loss / len(self.train_loader)}
    
    def evaluate(self, parameters, config):
        self.set_parameters(parameters)
        
        # Evaluate the model
        self.model.eval()
        val_loss = 0.0
        all_predictions = []
        all_labels = []
        
        with torch.no_grad():
            for features, speaker_embeddings, labels in self.val_loader:
                features, speaker_embeddings, labels = (
                    features.to(self.device),
                    speaker_embeddings.to(self.device),
                    labels.to(self.device)
                )
                
                outputs = self.model(features)
                loss = self.criterion(outputs, labels)
                val_loss += loss.item()
                
                predictions = torch.argmax(outputs, dim=1)
                all_predictions.extend(predictions.cpu().numpy())
                all_labels.extend(labels.cpu().numpy())
        
        # Calculate DER
        der = self.calculate_der(all_predictions, all_labels)
        
        return (
            float(val_loss / len(self.val_loader)),
            len(self.val_loader),
            {"val_loss": val_loss / len(self.val_loader), "der": der}
        )
    
    def calculate_der(self, predictions: List[int], labels: List[int]) -> float:
        """Calculate Diarization Error Rate."""
        reference = Annotation()
        hypothesis = Annotation()
        
        for i, (pred, label) in enumerate(zip(predictions, labels)):
            # Convert power set encoded values back to speaker labels
            pred_speakers = self.power_set_encoder.decode(pred)
            true_speakers = self.power_set_encoder.decode(label)
            
            # Add segments to reference and hypothesis
            for speaker in true_speakers:
                if speaker == 1:
                    reference[Segment(i, i+1)] = f"speaker_{speaker}"
            
            for speaker in pred_speakers:
                if speaker == 1:
                    hypothesis[Segment(i, i+1)] = f"speaker_{speaker}"
        
        # Calculate DER
        metric = DiarizationErrorRate()
        der = metric(reference, hypothesis)
        
        return der

def main():
    # Load and preprocess data
    dataset = load_dataset("edinburghcstr/ami", "ihm")
    
    # Initialize Power Set Encoder
    power_set_encoder = PowerSetEncoder(max_speakers=4)
    
    # Create and train model
    model = SENDModel().to(device)
    
    # Split data for federated learning
    num_clients = 5
    client_data = split_data_for_clients(dataset, num_clients)
    
    # Initialize clients
    clients = []
    for client_id, (train_loader, val_loader) in enumerate(client_data):
        client = SENDClient(
            model=model,
            train_loader=train_loader,
            val_loader=val_loader,
            device=device,
            power_set_encoder=power_set_encoder
        )
        clients.append(client)
    
    # Start federated learning
    strategy = fl.server.strategy.FedAvg(
        fraction_fit=0.8,
        fraction_eval=0.2,
        min_fit_clients=3,
        min_eval_clients=2,
        min_available_clients=3,
        eval_fn=None,
        on_fit_config_fn=lambda _: {"epochs": 5},
        on_eval_config_fn=lambda _: {"epochs": 1},
        initial_parameters=fl.common.ndarrays_to_parameters(
            [val.cpu().numpy() for _, val in model.state_dict().items()]
        ),
    )
    
    # Start Flower server
    fl.server.start_server(
        server_address="[::]:8080",
        config=fl.server.ServerConfig(num_rounds=10),
        strategy=strategy
    )

if __name__ == "__main__":
    main() 