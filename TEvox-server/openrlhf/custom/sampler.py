import uuid
from pydantic import BaseModel, Field
from typing import List

from pymongo import UpdateOne

from openrlhf.custom.mongo import MongoClientProxy


class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: bool = Field(default=True, description="True: active, False: inactive")
    prompt: List[dict] = []
    workspace: str = ""
    branch: str = ""
    commits: List[str] = []


class Trajectory(BaseModel):
    task_id: str
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: bool = Field(default=True, description="True: active, False: inactive")
    prompt: List[dict] = []
    workspace: str = ""
    branch: str = ""
    commits: List[str] = []
    info: dict = Field(default_factory=dict)


def max_divisible(num_tasks, batch_size):
    x = min(num_tasks, batch_size)
    while x > 0:
        if batch_size % x == 0:
            return x
        x -= 1
    return 0


class DatasetSampler:

    def __init__(self):
        self.task_collection = MongoClientProxy.get_collection("task")
        self.traj_collection = MongoClientProxy.get_collection("trajectory")
        self.task_collection.create_index("id", unique=True)
        self.task_collection.create_index("status")
        self.traj_collection.create_index("id", unique=True)
        self.traj_collection.create_index("status")
        self.traj_collection.create_index("task_id")

    def upsert_many_tasks(self, tasks: List[Task], unset: List[str] = [], **kwargs):
        bulk_ops = [
            UpdateOne(
                filter={"id": task.id},
                update={"$set": task.model_dump(**kwargs)},
                upsert=True,
            )
            for task in tasks
        ]
        return self.task_collection.bulk_write(bulk_ops, ordered=False)

    def upsert_many_trajectories(self, trajectories: List[Trajectory], **kwargs):
        bulk_ops = [
            UpdateOne(
                filter={"id": traj.id},
                update={"$set": traj.model_dump(**kwargs)},
                upsert=True,
            )
            for traj in trajectories
        ]
        return self.traj_collection.bulk_write(bulk_ops, ordered=False)

    def get_tasks(self, batch_size: int = 1):
        pipeline = [
            {
                "$match": {
                    "$or": [
                        {"status": True},
                        {"status": {"$exists": False}},
                    ]
                }
            },
            {"$sample": {"size": batch_size}},
        ]
        return [
            Task.model_validate(item)
            for item in self.task_collection.aggregate(pipeline)
        ]

    def get_trajectories(self, task_id: str, batch_size: int = 1):
        pipeline = [
            {
                "$match": {
                    "task_id": task_id,
                    "$or": [
                        {"status": True},
                        {"status": {"$exists": False}},
                    ],
                }
            },
            {"$sample": {"size": batch_size}},
        ]
        return [
            Trajectory.model_validate(item)
            for item in self.traj_collection.aggregate(pipeline)
        ]

    def get_samples(self, batch_size: int = 1):
        tasks = self.get_tasks(batch_size)
        if len(tasks) == 0:
            return []

        samples = []
        tasks = tasks[: max_divisible(len(tasks), batch_size)]
        micro_batch_size = batch_size // len(tasks)

        for task in tasks:
            trajectories = self.get_trajectories(task.id, micro_batch_size)
            if len(trajectories) == micro_batch_size:
                samples.extend(trajectories)
                continue

            new_trajectories = [
                Trajectory(
                    task_id=task.id,
                    prompt=task.prompt,
                )
                for _ in range(micro_batch_size - len(trajectories))
            ]
            if new_trajectories:
                self.upsert_many_trajectories(new_trajectories)
                samples.extend(new_trajectories)

        return samples

    def get_trajectory_with_task(self, trajectory_id: str):
        trajectory = self.traj_collection.find_one({"id": trajectory_id})
        if not trajectory:
            raise ValueError(f"Trajectory with id {trajectory_id} not found")
        trajectory = Trajectory.model_validate(trajectory)

        task = self.task_collection.find_one({"id": trajectory.task_id})
        if not task:
            raise ValueError(f"Task with id {trajectory.task_id} not found")
        task = Task.model_validate(task)

        return trajectory, task


if __name__ == "__main__":
    from openrlhf.custom.prompt import (
        AGENT_SYSTEM_PROMPT,
        AGENT_USER_PROMPT,
    )
    from openrlhf.custom.reward_func import check_tools

    sampler = DatasetSampler()
    res = sampler.upsert_many_tasks(
        [
            Task(
                prompt=[
                    {
                        "role": "system",
                        "content": AGENT_SYSTEM_PROMPT.format(
                            task="The task is to design, develop, and test basic firmware based on the ESP32-S3. The requirement is to print 'Hello World' on the serial monitor using log statements. Note: The development environment has been set up successfully using PlatformIO, along with ESP-IDF framework.",
                            tools=check_tools,
                        ),
                    },
                    {
                        "role": "user",
                        "content": AGENT_USER_PROMPT,
                    },
                ],
                id="0ce7c374-2c4f-47b0-9216-eb4873dd254a",
                branch="init_start",
            ),
        ],
        exclude=["status"],
    )
    # samples = sampler.get_samples(batch_size=4)
    # print(samples)
