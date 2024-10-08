"""
Implements the SprintBoard dataset.

This is a sub-class of BaseDataset that stores the tickets and metadata
set for each ticket in the Sprint Planning Board
"""

from __future__ import annotations

from typing import Self

import pandas as pd

from analytics.datasets.base import BaseDataset
from analytics.datasets.utils import load_json_data_as_df


class SprintBoard(BaseDataset):
    """Stores the GitHub project data for the Sprint Planning Board."""

    ISSUE_DATE_COLS = ["created_date", "closed_date"]
    ISSUE_COLUMN_MAP = {
        "number": "issue_number",
        "createdAt": "created_date",
        "closedAt": "closed_date",
    }
    SPRINT_DATE_COLS = ["sprint_start_date", "milestone_due_date"]
    SPRINT_COLUMN_MAP = {
        "content.number": "issue_number",
        "title": "issue_title",
        "content.type": "type",
        "content.body": "issue_body",
        "status": "status",
        "assignees": "assignees",
        "labels": "labels",
        "content.url": "url",
        "story Points": "points",
        "milestone.title": "milestone",
        "milestone.dueOn": "milestone_due_date",
        "milestone.description": "milestone_description",
        "sprint.title": "sprint",
        "sprint.startDate": "sprint_start_date",
        "sprint.duration": "sprint_duration",
    }

    def __init__(self, df: pd.DataFrame) -> None:
        """Intializes the sprint board dataset."""
        # set named columns
        self.opened_col = "created_date"
        self.closed_col = "closed_date"
        self.sprint_col = "sprint"
        self.sprint_start_col = "sprint_start_date"
        self.sprint_end_col = "sprint_end_date"
        # initialize the parent class
        super().__init__(df)

    def sprint_start(self, sprint: str) -> pd.Timestamp:
        """Return the date on which a given sprint started."""
        sprint_mask = self.df[self.sprint_col] == sprint
        sprint_start = self.df.loc[sprint_mask, self.sprint_start_col].min()
        return sprint_start.tz_localize("UTC")

    def sprint_end(self, sprint: str) -> pd.Timestamp:
        """Return the date on which a given sprint ended."""
        sprint_mask = self.df[self.sprint_col] == sprint
        sprint_end = self.df.loc[sprint_mask, self.sprint_end_col].max()
        return sprint_end.tz_localize("UTC")

    @property
    def sprints(self) -> pd.DataFrame:
        """Return the unique list of sprints with their start and end dates."""
        sprint_cols = [self.sprint_col, self.sprint_start_col, self.sprint_end_col]
        return self.df[sprint_cols].drop_duplicates()

    @property
    def current_sprint(self) -> str | None:
        """Return the name of the current sprint, if a sprint is currently active."""
        return self.get_sprint_name_from_date(pd.Timestamp.today().floor("d"))

    def get_sprint_name_from_date(self, date: pd.Timestamp) -> str | None:
        """Get the name of a sprint from a given date, if that date falls in a sprint."""
        # fmt: off
        date_filter = (
            (self.sprints[self.sprint_start_col] < date)  # after sprint start
            & (self.sprints[self.sprint_end_col] >= date)  # before sprint end
        )
        # fmt: on
        matching_sprints = self.sprints.loc[date_filter, self.sprint_col]
        # if there aren't any sprints return None
        if len(matching_sprints) == 0:
            return None
        # if there are, return the first value as a string
        return str(matching_sprints.squeeze())

    @classmethod
    def load_from_json_files(
        cls,
        sprint_file: str = "data/sprint-data.json",
        issue_file: str = "data/issue-data.json",
    ) -> Self:
        """
        Load the input datasets and instantiate the SprintBoard class.

        Parameters
        ----------
        sprint_file: str
            Path to the local copy of sprint data exported from GitHub
        issue_file: str
            Path to the local copy of issue data exported from GitHub

        Returns
        -------
        Self:
            An instance of the SprintBoard dataset class

        """
        # load and merge input datasets
        df_sprints = load_json_data_as_df(
            file_path=sprint_file,
            column_map=cls.SPRINT_COLUMN_MAP,
            date_cols=cls.SPRINT_DATE_COLS,
            key_for_nested_items="items",
        )
        df_issues = load_json_data_as_df(
            file_path=issue_file,
            column_map=cls.ISSUE_COLUMN_MAP,
            date_cols=cls.ISSUE_DATE_COLS,
        )
        df = df_sprints.merge(df_issues, on="issue_number")
        df = cls._apply_transformations(df)
        return cls(df)

    @classmethod
    def _apply_transformations(cls, df: pd.DataFrame) -> pd.DataFrame:
        """Apply column specific data transformations."""
        # calculate sprint end date
        df["sprint_duration"] = pd.to_timedelta(df["sprint_duration"], unit="day")
        df["sprint_end_date"] = df["sprint_start_date"] + df["sprint_duration"]
        # extract parent issue number from the milestone description
        parent_issue_regex = r"(?: deliverable: \#)(?P<parent_issue_number>\d+)"
        df["parent_issue_number"] = (
            df["milestone_description"]
            .str.extract(pat=parent_issue_regex, expand=False)
            .astype("Int64")
        )
        return df
