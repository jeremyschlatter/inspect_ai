from typing import Any, Callable, cast

from inspect_ai import Task, eval, score
from inspect_ai._util.constants import PKG_NAME
from inspect_ai._util.registry import registry_info
from inspect_ai.dataset import Sample
from inspect_ai.scorer import (
    Metric,
    Score,
    Scorer,
    Value,
    accuracy,
    includes,
    match,
    mean,
    metric,
    scorer,
    std,
    var,
)
from inspect_ai.scorer._metric import (
    MetricDeprecated,
    MetricProtocol,
    SampleScore,
    metric_create,
)
from inspect_ai.scorer._metrics.std import stderr
from inspect_ai.scorer._target import Target
from inspect_ai.solver._task_state import TaskState

# declare some metrics using the various forms supported (function,
# function returning Metric, class deriving from Metric) as well
# as using implicit and explicit names


@metric
def accuracy1(correct: str = "C") -> Metric:
    def metric(scores: list[SampleScore]) -> int | float:
        return 1

    return metric


@metric(name="accuracy2")
def acc_fn(correct: str = "C") -> Metric:
    def metric(scores: list[SampleScore]) -> int | float:
        return 1

    return metric


@metric
class Accuracy3(MetricDeprecated):
    def __init__(self, correct: str = "C") -> None:
        self.correct = correct

    def __call__(self, scores: list[Score]) -> int | float:
        return 1


@metric(name="accuracy4")
class AccuracyNamedCls(MetricProtocol):
    def __init__(self, correct: str = "C") -> None:
        self.correct = correct

    def __call__(self, scores: list[SampleScore]) -> int | float:
        return 1


@metric
def list_metric() -> Metric:
    def metric(scores: list[SampleScore]) -> Value:
        return [1, 2, 3]

    return metric


@metric
def deprecated_metric() -> Metric:
    def metric(scores: list[Score]) -> Value:
        return len(scores)

    return metric


@metric
def dict_metric() -> Metric:
    def metric(scores: list[SampleScore]) -> Value:
        return {"one": 1, "two": 2, "three": 3}

    return metric


def test_metric_registry() -> None:
    registry_assert(accuracy1, "accuracy1")
    registry_assert(acc_fn, "accuracy2")
    registry_assert(Accuracy3, "Accuracy3")
    registry_assert(AccuracyNamedCls, "accuracy4")


def test_metric_call() -> None:
    registry_assert(accuracy1(), "accuracy1")
    registry_assert(acc_fn(), "accuracy2")
    registry_assert(Accuracy3(), "Accuracy3")
    registry_assert(AccuracyNamedCls(), "accuracy4")


def test_metric_create() -> None:
    metric_create_assert("accuracy1", correct="C")
    metric_create_assert("accuracy1", correct="C")
    metric_create_assert("Accuracy3", correct="C")
    metric_create_assert("accuracy4", correct="C")


def test_inspect_metrics() -> None:
    registry_assert(accuracy, f"{PKG_NAME}/accuracy")
    registry_assert(accuracy(), f"{PKG_NAME}/accuracy")


def test_deprecated_metric() -> None:
    def check_log(log):
        assert log.results and (
            list(log.results.scores[0].metrics.keys()) == ["deprecated_metric"]
        )

    task = Task(
        dataset=[Sample(input="What is 1 + 1?", target=["2", "2.0", "Two"])],
        scorer=match(),
        metrics=[deprecated_metric()],
    )

    log = eval(tasks=task, model="mockllm/model")[0]
    check_log(log)


def test_list_metric() -> None:
    def check_log(log):
        assert log.results and (
            list(log.results.scores[0].metrics.keys())
            == ["list_metric-1", "list_metric-2", "list_metric-3"]
        )

    task = Task(
        dataset=[Sample(input="What is 1 + 1?", target=["2", "2.0", "Two"])],
        scorer=match(),
        metrics=[list_metric()],
    )

    # normal eval
    log = eval(tasks=task, model="mockllm/model")[0]
    check_log(log)


def test_dict_metric() -> None:
    def check_log(log):
        assert log.results and (
            list(log.results.scores[0].metrics.keys()) == ["one", "two", "three"]
        )

    task = Task(
        dataset=[Sample(input="What is 1 + 1?", target=["2", "2.0", "Two"])],
        scorer=match(),
        metrics=[dict_metric()],
    )

    # normal eval
    log = eval(tasks=task, model="mockllm/model")[0]
    check_log(log)


def test_alternative_metrics() -> None:
    # check that we get the alternative metrics
    def check_log(log):
        assert log.results and (
            list(log.results.scores[0].metrics.keys())
            == [
                "accuracy",
                "accuracy1",
                "Accuracy3",
                "std",
            ]
        )

    task = Task(
        dataset=[Sample(input="What is 1 + 1?", target=["2", "2.0", "Two"])],
        scorer=match(),
        metrics=[accuracy(), accuracy1(), Accuracy3(), std()],
    )

    # normal eval
    log = eval(tasks=task, model="mockllm/model")[0]
    check_log(log)

    # eval log w/ different scorer (that still uses accuracy)
    log = score(log, scorers=[includes()])
    check_log(log)


@metric
def complex_metric() -> Metric:
    def metric(scores: list[SampleScore]) -> int | float:
        total = 0.0
        for complex_score in scores:
            if isinstance(complex_score.score.value, dict):
                total = (
                    total
                    + cast(int, complex_score.score.value["one"])
                    + cast(int, complex_score.score.value["two"])
                    + cast(int, complex_score.score.value["three"])
                )
        return total

    return metric


@scorer(
    metrics=[
        {"one": [mean()], "two": [mean(), std()], "three": [mean(), std()]},
        complex_metric(),
    ]
)
def complex_scorer() -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        return Score(value={"one": 1, "two": 2, "three": 3})

    return score


def test_complex_metrics() -> None:
    def check_log(log):
        assert len(log.results.scores) == 4
        assert log.results.scores[0].name == "complex_scorer"
        assert log.results.scores[0].metrics["complex_metric"].value == 6

    task = Task(
        dataset=[Sample(input="What is 1 + 1?", target=["2", "2.0", "Two"])],
        scorer=complex_scorer(),
    )

    # normal eval
    log = eval(tasks=task, model="mockllm/model")[0]
    check_log(log)


@scorer(
    metrics=[
        {"*": [mean()]},
    ]
)
def wildcard_scorer() -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        return Score(value={"one": 1, "two": 2, "three": 3})

    return score


def test_wildcard() -> None:
    def check_log(log):
        assert len(log.results.scores) == 4
        assert log.results.scores[1].name == "one"
        assert log.results.scores[1].metrics["mean"].value == 1

    task = Task(
        dataset=[Sample(input="What is 1 + 1?", target=["2", "2.0", "Two"])],
        scorer=wildcard_scorer(),
    )

    # normal eval
    log = eval(tasks=task, model="mockllm/model")[0]
    check_log(log)


def registry_assert(metric: Metric | Callable[..., Metric], name: str) -> None:
    info = registry_info(metric)
    assert info.name == name


def metric_create_assert(name: str, **kwargs: Any) -> None:
    metric = metric_create(name, **kwargs)
    assert metric([]) == 1


@metric
def nested_dict_metric(correct: str = "C") -> Metric:
    def metric(scores: list[SampleScore]) -> Value:
        return {"key1": 1.0, "key2": 2.0}

    return metric


@scorer(
    metrics=[
        {"*": [nested_dict_metric()]},
    ]
)
def nested_dict_scorer() -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        return Score(value={"one": 1, "two": 2, "three": 3})

    return score


def test_nested_dict_metrics() -> None:
    def check_log(log):
        assert len(log.results.scores) == 4
        assert log.results.scores[1].name == "one"
        assert len(log.results.scores[1].metrics.values()) == 2
        assert (
            log.results.scores[1].metrics["nested_dict_metric_key1"].name
            == "nested_dict_metric_key1"
        )

    task = Task(
        dataset=[Sample(input="What is 1 + 1?", target=["2", "2.0", "Two"])],
        scorer=nested_dict_scorer(),
    )

    # normal eval
    log = eval(tasks=task, model="mockllm/model")[0]
    check_log(log)


@metric
def nested_list_metric(correct: str = "C") -> Metric:
    def metric(scores: list[SampleScore]) -> Value:
        return [1.0, 2.0]

    return metric


@scorer(
    metrics=[
        {"*": [nested_list_metric()]},
    ]
)
def nested_list_scorer() -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        return Score(value={"one": 1, "two": 2, "three": 3})

    return score


def test_nested_list_metrics() -> None:
    def check_log(log):
        assert len(log.results.scores) == 4
        assert log.results.scores[1].name == "one"
        assert len(log.results.scores[1].metrics.values()) == 2
        assert (
            log.results.scores[1].metrics["nested_list_metric_0"].name
            == "nested_list_metric_0"
        )

    task = Task(
        dataset=[Sample(input="What is 1 + 1?", target=["2", "2.0", "Two"])],
        scorer=nested_list_scorer(),
    )

    # normal eval
    log = eval(tasks=task, model="mockllm/model")[0]
    check_log(log)


def test_variance():
    metric = var()
    result = metric(scores=[SampleScore(score=Score(value=i)) for i in range(10)])
    assert round(result, 3) == 9.167
    assert metric([SampleScore(score=Score(value=4))]) == 0.0


def test_stderr():
    metric = stderr()
    se = metric([SampleScore(score=Score(value=i)) for i in range(10)])
    assert round(se, 3) == 0.957


def test_clustered_stderr():
    metric = stderr(cluster="my_cluster")
    se = metric(
        [
            SampleScore(score=Score(value=i), sample_metadata={"my_cluster": i % 4})
            for i in range(20)
        ]
    )
    assert round(se, 3) == 0.645
