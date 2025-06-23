"""
Ranking model for video highlight selection.

This module defines the interface for ranking models and provides
implementations for different model types.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Tuple
import numpy as np
import json
from pathlib import Path
import logging
import os

from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import joblib

from app.editing.pipeline.core import Segment

logger = logging.getLogger(__name__)

class BaseRankingModel(ABC):
    """
    Abstract base class for ranking models.
    
    All ranking models should inherit from this class and implement
    the required methods.
    """
    
    def __init__(self, model_params: Optional[Dict[str, Any]] = None):
        """
        Initialize the ranking model.
        
        Args:
            model_params: Dictionary of model-specific parameters
        """
        self.model_params = model_params or {}
        self.model = None
        self.feature_scaler = None
        self.feature_importances_ = None
        self.feature_names_ = None
    
    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray, **kwargs) -> 'BaseRankingModel':
        """
        Train the ranking model.
        
        Args:
            X: Feature matrix of shape (n_samples, n_features)
            y: Target values of shape (n_samples,)
            **kwargs: Additional arguments for model fitting
            
        Returns:
            self
        """
        pass
    
    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Make predictions using the trained model.
        
        Args:
            X: Feature matrix of shape (n_samples, n_features)
            
        Returns:
            Predicted scores of shape (n_samples,)
        """
        pass
    
    @abstractmethod
    def save(self, path: Union[str, Path]) -> None:
        """
        Save the model to disk.
        
        Args:
            path: Path to save the model to
        """
        pass
    
    @classmethod
    @abstractmethod
    def load(cls, path: Union[str, Path]) -> 'BaseRankingModel':
        """
        Load a model from disk.
        
        Args:
            path: Path to the saved model
            
        Returns:
            Loaded model instance
        """
        pass
    
    def get_feature_importance(self) -> Dict[str, float]:
        """
        Get feature importances from the trained model.
        
        Returns:
            Dictionary mapping feature names to their importance scores
        """
        if self.feature_importances_ is None or self.feature_names_ is None:
            return {}
        return dict(zip(self.feature_names_, self.feature_importances_))
    
    def _validate_input(self, X: np.ndarray, y: np.ndarray = None) -> None:
        """Validate input data."""
        if not isinstance(X, np.ndarray):
            raise ValueError("X must be a numpy array")
        
        if X.ndim != 2:
            raise ValueError(f"X must be 2D, got shape {X.shape}")
        
        if y is not None:
            if not isinstance(y, np.ndarray):
                raise ValueError("y must be a numpy array")
            
            if y.ndim != 1:
                raise ValueError(f"y must be 1D, got shape {y.shape}")
            
            if len(X) != len(y):
                raise ValueError(
                    f"X and y must have the same number of samples. "
                    f"Got X: {len(X)}, y: {len(y)}"
                )


class RandomForestRankingModel(BaseRankingModel):
    """
    A ranking model based on Random Forest regressor.
    
    This is a simple but effective model for learning to rank video segments.
    """
    
    def __init__(self, model_params: Optional[Dict[str, Any]] = None):
        """
        Initialize the Random Forest ranking model.
        
        Args:
            model_params: Parameters to pass to the RandomForestRegressor
        """
        super().__init__(model_params)
        
        # Default parameters
        self.default_params = {
            'n_estimators': 100,
            'max_depth': 10,
            'min_samples_split': 2,
            'min_samples_leaf': 1,
            'random_state': 42,
            'n_jobs': -1  # Use all available cores
        }
        
        # Update with any user-provided parameters
        self.default_params.update(self.model_params)
        
        self.model = RandomForestRegressor(**self.default_params)
        self.feature_scaler = StandardScaler()
    
    def fit(self, X: np.ndarray, y: np.ndarray, **kwargs) -> 'RandomForestRankingModel':
        """
        Train the Random Forest ranking model.
        
        Args:
            X: Feature matrix of shape (n_samples, n_features)
            y: Target values of shape (n_samples,)
            **kwargs: Additional arguments for model fitting
            
        Returns:
            self
        """
        self._validate_input(X, y)
        
        # Scale features
        X_scaled = self.feature_scaler.fit_transform(X)
        
        # Train model
        self.model.fit(X_scaled, y, **kwargs)
        
        # Store feature importances and names if available
        if hasattr(self.model, 'feature_importances_'):
            self.feature_importances_ = self.model.feature_importances_
            
            # Try to get feature names from kwargs
            self.feature_names_ = kwargs.get('feature_names')
            if self.feature_names_ is not None and len(self.feature_names_) != X.shape[1]:
                logger.warning(
                    f"Feature names length ({len(self.feature_names_)}) "
                    f"does not match number of features ({X.shape[1]})"
                )
                self.feature_names_ = None
        
        return self
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Make predictions using the trained model.
        
        Args:
            X: Feature matrix of shape (n_samples, n_features)
            
        Returns:
            Predicted scores of shape (n_samples,)
        """
        self._validate_input(X)
        
        if self.model is None:
            raise RuntimeError("Model has not been trained. Call fit() first.")
        
        # Scale features
        X_scaled = self.feature_scaler.transform(X)
        
        # Make predictions
        return self.model.predict(X_scaled)
    
    def save(self, path: Union[str, Path]) -> None:
        """
        Save the model to disk.
        
        Args:
            path: Path to save the model to (without file extension)
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save model and scaler
        model_path = path.with_suffix('.joblib')
        scaler_path = path.with_name(f"{path.stem}_scaler.joblib")
        
        joblib.dump(self.model, model_path)
        joblib.dump(self.feature_scaler, scaler_path)
        
        # Save metadata
        metadata = {
            'model_type': 'random_forest',
            'feature_names': self.feature_names_,
            'feature_importances': self.feature_importances_.tolist() if self.feature_importances_ is not None else None,
            'model_params': self.model.get_params()
        }
        
        metadata_path = path.with_name(f"{path.stem}_metadata.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    @classmethod
    def load(cls, path: Union[str, Path]) -> 'RandomForestRankingModel':
        """
        Load a model from disk.
        
        Args:
            path: Path to the saved model (without file extension)
            
        Returns:
            Loaded model instance
        """
        path = Path(path)
        
        # Load model and scaler
        model_path = path.with_suffix('.joblib')
        scaler_path = path.with_name(f"{path.stem}_scaler.joblib")
        metadata_path = path.with_name(f"{path.stem}_metadata.json")
        
        if not all(p.exists() for p in [model_path, scaler_path, metadata_path]):
            raise FileNotFoundError(
                f"Could not find all required files for loading model at {path}"
            )
        
        # Load metadata
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        # Create model instance
        model = cls(model_params=metadata.get('model_params', {}))
        
        # Load model and scaler
        model.model = joblib.load(model_path)
        model.feature_scaler = joblib.load(scaler_path)
        
        # Set metadata
        model.feature_names_ = metadata.get('feature_names')
        if 'feature_importances' in metadata and metadata['feature_importances'] is not None:
            model.feature_importances_ = np.array(metadata['feature_importances'])
        
        return model


def get_model(name: str = 'random_forest', **kwargs) -> BaseRankingModel:
    """
    Factory function to get a ranking model by name.
    
    Args:
        name: Name of the model to create
        **kwargs: Additional arguments to pass to the model constructor
        
    Returns:
        An instance of the requested ranking model
        
    Raises:
        ValueError: If the model name is not recognized
    """
    models = {
        'random_forest': RandomForestRankingModel,
    }
    
    model_class = models.get(name.lower())
    if model_class is None:
        raise ValueError(f"Unknown model: {name}. Available models: {list(models.keys())}")
    
    return model_class(**kwargs)
