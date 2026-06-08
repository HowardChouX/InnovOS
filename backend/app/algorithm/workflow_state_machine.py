"""
工作流状态机 — 6 阶段管线（从 RootSeek PhaseStateMachine 扩展）
"""
from enum import Enum


class WorkflowPhase(Enum):
    DEMAND_PORTRAIT = "demand_portrait"
    PROBLEM_MODELING = "problem_modeling"
    PATENT_SEARCH = "patent_search"
    SOLUTION_GEN = "solution_gen"
    EVALUATION = "evaluation"
    COMPLETED = "completed"

    @property
    def label(self) -> str:
        return {
            "demand_portrait": "需求画像",
            "problem_modeling": "问题建模",
            "patent_search": "专利检索",
            "solution_gen": "方案生成",
            "evaluation": "方案评估",
            "completed": "完成",
        }[self.value]

    @property
    def order(self) -> int:
        return _PHASE_ORDER[self]


_PHASE_ORDER = {
    WorkflowPhase.DEMAND_PORTRAIT: 0,
    WorkflowPhase.PROBLEM_MODELING: 1,
    WorkflowPhase.PATENT_SEARCH: 2,
    WorkflowPhase.SOLUTION_GEN: 3,
    WorkflowPhase.EVALUATION: 4,
    WorkflowPhase.COMPLETED: 5,
}


class WorkflowEvent(Enum):
    DEMAND_DONE = "demand_done"
    MODELING_DONE = "modeling_done"
    PATENT_DONE = "patent_done"
    SOLUTION_DONE = "solution_done"
    EVAL_DONE = "eval_done"
    RETRY_MODELING = "retry_modeling"
    RETRY_SOLUTION = "retry_solution"


_TRANSITIONS = {
    (WorkflowPhase.DEMAND_PORTRAIT, WorkflowEvent.DEMAND_DONE): WorkflowPhase.PROBLEM_MODELING,
    (WorkflowPhase.PROBLEM_MODELING, WorkflowEvent.MODELING_DONE): WorkflowPhase.PATENT_SEARCH,
    (WorkflowPhase.PATENT_SEARCH, WorkflowEvent.PATENT_DONE): WorkflowPhase.SOLUTION_GEN,
    (WorkflowPhase.SOLUTION_GEN, WorkflowEvent.SOLUTION_DONE): WorkflowPhase.EVALUATION,
    (WorkflowPhase.EVALUATION, WorkflowEvent.EVAL_DONE): WorkflowPhase.COMPLETED,
    (WorkflowPhase.EVALUATION, WorkflowEvent.RETRY_MODELING): WorkflowPhase.PROBLEM_MODELING,
    (WorkflowPhase.EVALUATION, WorkflowEvent.RETRY_SOLUTION): WorkflowPhase.SOLUTION_GEN,
}


class TransitionError(Exception):
    pass


class PhaseStateMachine:
    """6阶段工作流状态机"""

    def __init__(self):
        self._current = WorkflowPhase.DEMAND_PORTRAIT
        self._history: list[tuple[WorkflowPhase, WorkflowEvent, WorkflowPhase]] = []

    @property
    def current(self) -> WorkflowPhase:
        return self._current

    def can_transition(self, event: WorkflowEvent) -> bool:
        return (self._current, event) in _TRANSITIONS

    def transition(self, event: WorkflowEvent) -> WorkflowPhase:
        result = _TRANSITIONS.get((self._current, event))
        if not result:
            raise TransitionError(
                f"无法从 {self._current.label} 通过事件 {event.value} 进行转换"
            )
        new_phase = result
        self._history.append((self._current, event, new_phase))
        self._current = new_phase
        return new_phase

    def can_go_back(self) -> bool:
        return len(self._history) > 0 and self._current != WorkflowPhase.COMPLETED

    def go_back(self) -> WorkflowPhase:
        if not self._history:
            raise TransitionError("没有历史记录")
        from_phase, _event, _to_phase = self._history.pop()
        self._current = from_phase
        return from_phase

    def reset(self) -> None:
        self._current = WorkflowPhase.DEMAND_PORTRAIT
        self._history.clear()

    @property
    def progress(self) -> float:
        return self._current.order / (len(WorkflowPhase) - 1)

    def to_dict(self) -> dict:
        return {
            "currentPhase": self._current.value,
            "currentLabel": self._current.label,
            "progress": self.progress,
            "history": [
                {"from": f.label, "event": e.value, "to": t.label}
                for f, e, t in self._history
            ],
        }
