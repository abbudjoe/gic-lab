"""Exact source-locator grammar shared by profile and runtime validation."""

from __future__ import annotations


def open_query_task_source_matches(task_source: str, query: str) -> bool:
    """Match either a bare query locator or a source citation plus exact query suffix."""

    binding = f"query={query}"
    return task_source == binding or task_source.endswith(f" {binding}")


def dataset_slice_task_source(
    dataset_id: str,
    start_idx: int,
    end_idx: int,
) -> str:
    """Return the canonical half-open dataset-slice locator."""

    return f"{dataset_id}[{start_idx}:{end_idx}]"
