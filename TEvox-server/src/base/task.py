import json
from enum import Enum
from typing import List, Union, Optional
from pydantic import BaseModel, Field

import networkx as nx
from networkx.readwrite.text import generate_network_text

from src.base.action import Action


class Task(BaseModel):
    # type: Optional[str] = Field(default="", description="The type of the task")
    name: str = Field(description="The name of the task")
    spec: str = Field(description="The specification of the task")

    def __str__(self):
        return f"{self.name}: {self.spec}"
        # if self.type:
        #     return f"({self.type}) {self.name}: {self.spec}"
        # else:
        #     return f"{self.name}: {self.spec}"


class TaskStatus(Enum):
    NOT_STARTED = 0
    STARTED = 1
    BREAKDOWN = 2
    EXECUTION = 3


class TaskNode(Task):
    id: Optional[int] = Field(default=0, description="The index in the conversation")
    status: TaskStatus = Field(
        default=TaskStatus.NOT_STARTED, description="The status of the task"
    )
    subtasks: List[Task] = Field(
        default_factory=list, description="The subtasks of the task"
    )
    progress: List[Union[Task, Action]] = Field(
        default_factory=list, description="The progress of the task"
    )
    summary: Optional[str] = Field(
        default=None, description="The summary of the task (optional)"
    )

    @classmethod
    def from_task(cls, task: Task):
        # return cls(type=task.type, name=task.name, spec=task.spec)
        return cls(name=task.name, spec=task.spec)

    def get_status(self):
        return self.status

    def set_status(self, status: TaskStatus):
        self.status = status

    def set_subtasks(self, subtasks: List[Task]):
        self.subtasks = subtasks

    def get_subtasks(self):
        return self.subtasks

    def add_progress(
        self, progress: Union[Union[Task, Action], List[Union[Task, Action]]]
    ):
        if isinstance(progress, list):
            self.progress.extend(progress)
        else:
            self.progress.append(progress)

    def get_progress(self):
        return self.progress


class TaskStack:

    def __init__(self):
        self._tasks = []
        self._actions = []
        self._progress = []

    def add_actions(self, actions: Union[Action, List[Action]]):
        if isinstance(actions, list):
            self._actions.extend(actions)
        else:
            self._actions.append(actions)

    def get_actions(self):
        return self._actions

    def clear_progress(self):
        self._progress = []

    def add_progress(self, progress: Union[str, List[str]]):
        if isinstance(progress, list):
            self._progress.extend(progress)
        else:
            self._progress.append(progress)

    def get_progress(self):
        return self._progress

    def push_task(self, task: Task):
        self._tasks.append(task)

    def pop_task(self):
        return self._tasks.pop()

    def set_current_task(self, task):
        self._tasks[-1] = task

    def get_current_task(self):
        return self._tasks[-1]

    def get_parent_task(self):
        if len(self._tasks) < 2:
            return None
        return self._tasks[-2]

    def get_all_tasks(self):
        return self._tasks

    def get_final_task(self):
        return self._tasks[0]

    def is_empty(self):
        return not self._tasks

    def __len__(self):
        return len(self._tasks)

    def __str__(self):
        return "\n\n".join([f"| {task} |" for task in self._tasks])

    def tree(self):
        root_task = self.get_final_task()
        task_tree = TaskTree()
        stack = [(root_task, None)]
        while stack:
            current_task, parent = stack.pop()
            task_tree.add_node(current_task, parent)
            for subtask in reversed(current_task.get_subtasks()):
                stack.append((subtask, current_task))
        return str(task_tree)

    def model_dump(self):
        tasks = []
        for t in self._tasks:
            v = t.status.value
            task = t.model_dump()
            task["status"] = v
            tasks.append(task)
        return {
            "tasks": tasks,
            "progress": self._progress,
        }

    @classmethod
    def model_validate(cls, data: dict):
        instance = cls()
        instance._tasks = [
            TaskNode.model_validate(task_data) for task_data in data.get("tasks", [])
        ]
        instance._progress = data.get("progress", [])
        return instance

    def save_to_file(self, filepath: str):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, indent=4, ensure_ascii=False)

    @classmethod
    def load_from_file(cls, filepath: str):
        with open(filepath, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        return cls.model_validate(raw_data)


class TaskTree:

    def __init__(self, root: TaskNode = None):
        self.id = 0
        self.graph = nx.DiGraph()
        self.current_task = None
        self.root = None
        if root:
            self.add_node(node=root)
            self.root = self.get_root_node()
            self.current_task = self.root

    def get_root_node(self) -> TaskNode:
        if self.root:
            return self.root
        for node in self.graph.nodes:
            if self.graph.in_degree(node) == 0:
                self.root = TaskNode.model_validate(self.graph.nodes[node]["data"])
                return self.root
        return None

    def is_root_node(self, node: TaskNode) -> bool:
        if self.root:
            return node.id == self.root.id
        if node.id not in self.graph:
            return False
        return self.graph.in_degree(node.id) == 0

    def set_current_task(self, task: TaskNode):
        self.current_task = task

    def get_current_task(self):
        return self.current_task

    def add_node(self, node: TaskNode, parent: TaskNode = None):
        self.id += 1
        node.id = self.id
        self.graph.add_node(
            node.id,
            data=node.model_dump(),
            # label=f"<id={node.id}>{node}</id={node.id}>",
            label=f"{node}",
        )
        if parent:
            self.graph.add_edge(parent.id, node.id)

    def delete_node(self, node: TaskNode):
        if node.id in self.graph:
            self.graph.remove_node(node.id)

    def update_node(self, node: TaskNode):
        if node.id not in self.graph:
            return
        if self.root and self.root.id == node.id:
            self.root = node
        self.graph.nodes[node.id]["data"] = node.model_dump()
        # self.graph.nodes[node.id]["label"] = f"<id={node.id}>{node}</id={node.id}>"
        self.graph.nodes[node.id]["label"] = f"{node}"

    def get_parent_node(self, child: TaskNode) -> TaskNode:
        predecessors = list(self.graph.predecessors(child.id))
        if predecessors:
            return TaskNode.model_validate(self.graph.nodes[predecessors[0]]["data"])
        return None

    def get_child_nodes(self, parent: TaskNode) -> list:
        return [
            TaskNode.model_validate(self.graph.nodes[node]["data"])
            for node in list(self.graph.successors(parent.id))
        ]

    def set_child_nodes(self, parent: TaskNode, children: list[TaskNode]) -> None:
        for child in children:
            self.add_node(child, parent)

    def get_node_by_id(self, node_id: int) -> TaskNode:
        if node_id in self.graph.nodes:
            return TaskNode.model_validate(self.graph.nodes[node_id]["data"])
        return None

    def get_leaf_nodes(self) -> list[TaskNode]:
        leaves = []
        for node_id in self.graph.nodes:
            if self.graph.out_degree(node_id) == 0:
                leaves.append(
                    TaskNode.model_validate(self.graph.nodes[node_id]["data"])
                )
        return leaves

    def __str__(self) -> str:
        return "\n".join(generate_network_text(self.graph))


if __name__ == "__main__":
    tree = TaskTree()

    # Initialize nodes (id will be auto-assigned)
    root_node = TaskNode(name="Root", spec="This is the root node")
    child_node1 = TaskNode(name="Child1", spec="First child node")
    child_node2 = TaskNode(name="Child2", spec="Second child node")

    # Add nodes to the tree
    tree.add_node(root_node)
    tree.add_node(child_node1, parent=root_node)
    tree.add_node(child_node2, parent=root_node)

    for node in tree.graph.nodes:
        print(node)
        print(tree.graph.nodes[node])

    # Retrieve and print the root node
    print("Root Node:", tree.get_root_node())

    # Retrieve and print the child nodes of the root
    print("Child Nodes:")
    for child in tree.get_child_nodes(root_node):
        print(child)

    # Lookup a node by its id and print it
    lookup_id = 2
    found_node = tree.get_node_by_id(lookup_id)
    print(f"Node with id={lookup_id}:", found_node)

    print(tree)

    # Example usage: build a task stack and display its tree structure

    # Create a TaskStack instance
    task_stack = TaskStack()

    # Create tasks with subtasks
    root_task = TaskNode(name="Project", spec="Complete the project")
    design_task = TaskNode(name="Design", spec="Design the system architecture")
    implementation_task = TaskNode(name="Implementation", spec="Implement the features")
    testing_task = TaskNode(name="Testing", spec="Test the application")

    # Organize hierarchy: root_task has two subtasks; one of them has a subtask
    root_task.set_subtasks([design_task, implementation_task])
    implementation_task.set_subtasks([testing_task])

    # Push tasks onto the stack (order: final task first)
    task_stack.push_task(root_task)
    task_stack.push_task(design_task)
    task_stack.push_task(implementation_task)
    task_stack.push_task(testing_task)

    # Output the tree structure derived from the task stack
    print("TaskStack Tree:")
    print(task_stack.tree())

    # Dump the model data from task_stack
    print("TaskStack model dump:")
    print(task_stack.model_dump())

    # Save task stack to a file
    filepath = "task_stack.json"
    task_stack.save_to_file(filepath)
    print(f"TaskStack saved to {filepath}")

    # Load task stack from the file and display its tree structure
    loaded_task_stack = TaskStack.load_from_file(filepath)
    print("Loaded TaskStack Tree:")
    print(loaded_task_stack.model_dump())
