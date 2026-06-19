"""The custom workflow engine (PRD §7.2, §10): runs → steps → agent_runs.

M1 runs pipelines synchronously (via FastAPI BackgroundTasks). M2 swaps the dispatch
layer for a durable queue + worker without changing pipeline code.
"""

from captureos.workflows.engine import NeedsInput, StepContext, run_pipeline

__all__ = ["NeedsInput", "StepContext", "run_pipeline"]
