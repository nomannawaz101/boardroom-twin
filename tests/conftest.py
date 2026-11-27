"""Runs before any test module imports config, so tests never read the laptop's settings file."""

import os

os.environ["BOARDROOM_SKIP_ENV_FILE"] = "1"
os.environ["LITELLM_MODEL"] = "fake-main"
os.environ["LITELLM_MODEL_FAST"] = "fake-fast"
