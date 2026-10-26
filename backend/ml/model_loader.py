import os
import json
import warnings
import joblib

warnings.filterwarnings("ignore", category=UserWarning)

BASE_ML_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "FreshFlow_ML")
MODELS_DIR = os.path.join(BASE_ML_DIR, "models")

class ModelLoader:
    _instance = None

    def __init__(self):
        self.model1_mean = None
        self.model1_q10 = None
        self.model1_q90 = None
        self.model2_risk = None
        self.model1_config = {}
        self.model2_config = {}
        self._load_models()

    def _load_models(self):
        try:
            m1_path = os.path.join(MODELS_DIR, "model1_demand_mean_poisson.joblib")
            q10_path = os.path.join(MODELS_DIR, "model1_demand_q10.joblib")
            q90_path = os.path.join(MODELS_DIR, "model1_demand_q90.joblib")
            m2_path = os.path.join(MODELS_DIR, "model2_ingredient_risk_gbm.joblib")

            if os.path.exists(m1_path):
                self.model1_mean = joblib.load(m1_path)
            if os.path.exists(q10_path):
                self.model1_q10 = joblib.load(q10_path)
            if os.path.exists(q90_path):
                self.model1_q90 = joblib.load(q90_path)
            if os.path.exists(m2_path):
                self.model2_risk = joblib.load(m2_path)

            c1_path = os.path.join(MODELS_DIR, "model1_config.json")
            if os.path.exists(c1_path):
                with open(c1_path, "r") as f:
                    self.model1_config = json.load(f)

            c2_path = os.path.join(MODELS_DIR, "model2_config.json")
            if os.path.exists(c2_path):
                with open(c2_path, "r") as f:
                    self.model2_config = json.load(f)
                    
            print("[ModelLoader] Successfully loaded ML models and configurations.")
        except Exception as e:
            print(f"[ModelLoader] Error loading models: {e}")

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = ModelLoader()
        return cls._instance
