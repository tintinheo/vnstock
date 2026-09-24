"""models/bilstm_model.py – PyTorch BiLSTM for stock price prediction."""
import numpy as np, os, torch, torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from config.settings import LSTM_PARAMS, MODEL_DIR

class StockSequenceDataset(Dataset):
    def __init__(self, X, y, seq_len=30):
        self.X, self.y, self.seq_len = X, y, seq_len
    def __len__(self): return max(0, len(self.X) - self.seq_len)
    def __getitem__(self, idx):
        x = self.X[idx:idx + self.seq_len]
        y = self.y[idx + self.seq_len - 1] if self.y is not None else 0.0
        return torch.FloatTensor(x), torch.FloatTensor([y])

class BiLSTMModel(nn.Module):
    def __init__(self, input_size=16, hidden_size=64, num_layers=2, dropout=0.2):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True,
                            bidirectional=True, dropout=dropout)
        self.fc = nn.Sequential(nn.Linear(hidden_size * 2, 32), nn.ReLU(), nn.Dropout(dropout),
                                nn.Linear(32, 1), nn.Sigmoid())
    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])

class BiLSTMTrainer:
    def __init__(self, **kwargs):
        self.params = {**LSTM_PARAMS, **kwargs}
        self.model = None; self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def train(self, X_train, y_train, X_val=None, y_val=None):
        p = self.params
        self.model = BiLSTMModel(p["input_size"], p["hidden_size"], p["num_layers"], p["dropout"]).to(self.device)
        optimizer = torch.optim.Adam(self.model.parameters(), lr=p["lr"])
        criterion = nn.BCELoss()
        train_ds = StockSequenceDataset(X_train, y_train, p["seq_len"])
        train_dl = DataLoader(train_ds, batch_size=p["batch_size"], shuffle=False)
        best_loss, patience, counter = float("inf"), 5, 0
        for epoch in range(p["epochs"]):
            self.model.train(); total_loss = 0
            for xb, yb in train_dl:
                xb, yb = xb.to(self.device), yb.to(self.device)
                pred = self.model(xb); loss = criterion(pred, yb)
                optimizer.zero_grad(); loss.backward(); optimizer.step()
                total_loss += loss.item()
            avg = total_loss / max(len(train_dl), 1)
            if avg < best_loss: best_loss = avg; counter = 0
            else:
                counter += 1
                if counter >= patience: print(f"Early stop epoch {epoch+1}"); break
        return self

    def predict(self, X):
        self.model.eval()
        ds = StockSequenceDataset(X, None, self.params["seq_len"])
        dl = DataLoader(ds, batch_size=64, shuffle=False)
        preds = []
        with torch.no_grad():
            for xb, _ in dl: preds.append(self.model(xb.to(self.device)).cpu().numpy())
        return np.concatenate(preds).flatten() if preds else np.array([])

    def save(self, name="bilstm"):
        os.makedirs(MODEL_DIR, exist_ok=True)
        torch.save(self.model.state_dict(), os.path.join(MODEL_DIR, f"{name}.pt"))

    def load(self, name="bilstm"):
        p = self.params
        self.model = BiLSTMModel(p["input_size"], p["hidden_size"], p["num_layers"], p["dropout"])
        self.model.load_state_dict(torch.load(os.path.join(MODEL_DIR, f"{name}.pt")))
        self.model.to(self.device)