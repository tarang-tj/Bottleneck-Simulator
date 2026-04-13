"""
Operational Bottleneck Simulator
Discrete-event simulation engine using SimPy.
Models multi-stage workflows, queue buildup, throughput, and utilization.
"""

import simpy
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StageConfig:
    name: str
    servers: int          # parallel workers at this stage
    avg_service_time: float   # mean processing time (minutes)
    std_service_time: float   # variability (minutes)


@dataclass
class SimResult:
    stage_name: str
    utilization: float        # fraction of time servers were busy (0–1)
    avg_queue_length: float   # mean queue waiting before this stage
    avg_wait_time: float      # mean time a job waits in queue (minutes)
    avg_service_time: float   # mean actual processing time (minutes)
    throughput: float         # completed jobs per hour
    total_processed: int
    is_bottleneck: bool = False


class BottleneckSimulator:
    def __init__(
        self,
        stages: list[StageConfig],
        arrival_rate: float,   # jobs per hour
        sim_duration: float,   # simulation time in minutes
        seed: int = 42,
    ):
        self.stages = stages
        self.arrival_rate = arrival_rate
        self.sim_duration = sim_duration
        self.seed = seed
        self.rng = np.random.default_rng(seed)

        # Collectors
        self._queue_lengths: dict[str, list[float]] = {s.name: [] for s in stages}
        self._wait_times: dict[str, list[float]] = {s.name: [] for s in stages}
        self._service_times: dict[str, list[float]] = {s.name: [] for s in stages}
        self._busy_time: dict[str, float] = {s.name: 0.0 for s in stages}
        self._processed: dict[str, int] = {s.name: 0 for s in stages}


    def _service_time(self, cfg: StageConfig) -> float:
        t = self.rng.normal(cfg.avg_service_time, cfg.std_service_time)
        return max(t, 0.1)

    def _job(self, env: simpy.Environment, resources: dict[str, simpy.Resource]):
        for stage in self.stages:
            res = resources[stage.name]

            # Record queue length at arrival
            self._queue_lengths[stage.name].append(len(res.queue))

            arrive = env.now
            with res.request() as req:
                yield req
                wait = env.now - arrive
                self._wait_times[stage.name].append(wait)

                svc = self._service_time(stage)
                self._service_times[stage.name].append(svc)
                self._busy_time[stage.name] += svc
                yield env.timeout(svc)

            self._processed[stage.name] += 1

    def _arrivals(self, env: simpy.Environment, resources: dict[str, simpy.Resource]):
        inter_arrival = 60.0 / self.arrival_rate  # convert jobs/hr → minutes
        while True:
            yield env.timeout(self.rng.exponential(inter_arrival))
            env.process(self._job(env, resources))

    def run(self) -> list[SimResult]:
        env = simpy.Environment()
        resources = {s.name: simpy.Resource(env, capacity=s.servers) for s in self.stages}
        env.process(self._arrivals(env, resources))
        env.run(until=self.sim_duration)

        results = []
        for stage in self.stages:
            n = self.stages.index(stage)
            util = self._busy_time[stage.name] / (self.sim_duration * stage.servers)
            avg_q = np.mean(self._queue_lengths[stage.name]) if self._queue_lengths[stage.name] else 0
            avg_w = np.mean(self._wait_times[stage.name]) if self._wait_times[stage.name] else 0
            avg_s = np.mean(self._service_times[stage.name]) if self._service_times[stage.name] else 0
            tp = self._processed[stage.name] / (self.sim_duration / 60)

            results.append(SimResult(
                stage_name=stage.name,
                utilization=round(min(util, 1.0), 3),
                avg_queue_length=round(avg_q, 2),
                avg_wait_time=round(avg_w, 2),
                avg_service_time=round(avg_s, 2),
                throughput=round(tp, 2),
                total_processed=self._processed[stage.name],
            ))

        # Identify bottleneck = highest utilization
        max_util = max(r.utilization for r in results)
        for r in results:
            r.is_bottleneck = (r.utilization == max_util)

        return results


def results_to_df(results: list[SimResult]) -> pd.DataFrame:
    rows = []
    for r in results:
        rows.append({
            "Stage": r.stage_name,
            "Utilization %": round(r.utilization * 100, 1),
            "Avg Queue Length": r.avg_queue_length,
            "Avg Wait (min)": r.avg_wait_time,
            "Avg Service (min)": r.avg_service_time,
            "Throughput (jobs/hr)": r.throughput,
            "Jobs Processed": r.total_processed,
            "Bottleneck": "⚠ YES" if r.is_bottleneck else "",
        })
    return pd.DataFrame(rows)


def default_stages() -> list[StageConfig]:
    """Preset: mirrors a simplified version of the Nuff Cash transaction workflow."""
    return [
        StageConfig("Intake & Validation",   servers=2, avg_service_time=3.5, std_service_time=1.0),
        StageConfig("Fraud Screening",        servers=1, avg_service_time=6.0, std_service_time=2.5),
        StageConfig("Payment Processing",     servers=3, avg_service_time=4.0, std_service_time=1.5),
        StageConfig("Ledger Update",          servers=1, avg_service_time=2.0, std_service_time=0.8),
        StageConfig("Notification Dispatch",  servers=2, avg_service_time=1.5, std_service_time=0.5),
    ]
