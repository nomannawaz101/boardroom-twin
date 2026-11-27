"""Run mode choice. Stub until Phase 6 adds the spend check and the automatic switch to Sample."""

import config

LIVE_DEFAULT: config.RunMode = "full"


def choose_mode() -> config.RunMode:
    mode = config.run_mode()
    return LIVE_DEFAULT if mode == "auto" else mode
