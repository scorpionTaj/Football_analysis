"""Match-outcome modelling: features, candidate models, evaluation and MLflow tracking."""

# Acceptance gate for the champion (walk-forward, top-flight holdout). Kept import-light for the API.
TARGETS = {"log_loss": 0.975, "rps": 0.200, "accuracy": 0.535, "ece": 0.02}
