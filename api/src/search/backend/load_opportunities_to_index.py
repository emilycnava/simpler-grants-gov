import logging
from enum import StrEnum
from typing import Iterator, Sequence

from pydantic import Field
from pydantic_settings import SettingsConfigDict
from sqlalchemy import delete, select
from sqlalchemy.orm import noload, selectinload

import src.adapters.db as db
import src.adapters.search as search
from src.api.opportunities_v1.opportunity_schemas import OpportunityV1Schema
from src.db.models.opportunity_models import (
    CurrentOpportunitySummary,
    Opportunity,
    OpportunitySearchIndexQueue,
)
from src.task.task import Task
from src.util.datetime_util import get_now_us_eastern_datetime
from src.util.env_config import PydanticBaseEnvConfig

logger = logging.getLogger(__name__)


class LoadOpportunitiesToIndexConfig(PydanticBaseEnvConfig):
    model_config = SettingsConfigDict(env_prefix="LOAD_OPP_SEARCH_")

    shard_count: int = Field(default=1)  # LOAD_OPP_SEARCH_SHARD_COUNT
    replica_count: int = Field(default=1)  # LOAD_OPP_SEARCH_REPLICA_COUNT

    # TODO - these might make sense to come from some sort of opportunity-search-index-config?
    # look into this a bit more when we setup the search endpoint itself.
    alias_name: str = Field(default="opportunity-index-alias")  # LOAD_OPP_SEARCH_ALIAS_NAME
    index_prefix: str = Field(default="opportunity-index")  # LOAD_OPP_INDEX_PREFIX


class LoadOpportunitiesToIndex(Task):
    class Metrics(StrEnum):
        RECORDS_LOADED = "records_loaded"

    def __init__(
        self,
        db_session: db.Session,
        search_client: search.SearchClient,
        is_full_refresh: bool = True,
        config: LoadOpportunitiesToIndexConfig | None = None,
    ) -> None:
        super().__init__(db_session)

        self.search_client = search_client
        self.is_full_refresh = is_full_refresh

        if config is None:
            config = LoadOpportunitiesToIndexConfig()
        self.config = config

        if is_full_refresh:
            current_timestamp = get_now_us_eastern_datetime().strftime("%Y-%m-%d_%H-%M-%S")
            self.index_name = f"{self.config.index_prefix}-{current_timestamp}"
        else:
            self.index_name = self.config.alias_name
        self.set_metrics({"index_name": self.index_name})

    def run_task(self) -> None:
        if self.is_full_refresh:
            logger.info("Running full refresh")
            self.full_refresh()
        else:
            logger.info("Running incremental load")
            self.incremental_updates_and_deletes()

    def incremental_updates_and_deletes(self) -> None:
        existing_opportunity_ids = self.fetch_existing_opportunity_ids_in_index()

        # Fetch opportunities that need processing from the queue
        queued_opportunities = (
            self.db_session.execute(
                select(Opportunity)
                .join(OpportunitySearchIndexQueue)
                .join(CurrentOpportunitySummary)
                .where(
                    Opportunity.is_draft.is_(False),
                    CurrentOpportunitySummary.opportunity_status.isnot(None),
                )
                .options(selectinload("*"), noload(Opportunity.all_opportunity_summaries))
            )
            .scalars()
            .all()
        )

        # Process updates and inserts
        processed_opportunity_ids = set()
        opportunities_to_index = []

        for opportunity in queued_opportunities:
            logger.info(
                "Processing queued opportunity",
                extra={
                    "opportunity_id": opportunity.opportunity_id,
                    "status": (
                        "update"
                        if opportunity.opportunity_id in existing_opportunity_ids
                        else "insert"
                    ),
                },
            )

            # Add to index batch if it's indexable
            opportunities_to_index.append(opportunity)
            processed_opportunity_ids.add(opportunity.opportunity_id)

        # Bulk index the opportunities (handles both inserts and updates)
        if opportunities_to_index:
            loaded_ids = self.load_records(opportunities_to_index)
            logger.info(f"Indexed {len(loaded_ids)} opportunities")

        # Handle deletes - opportunities in search but not in our processed set
        # and not in our database (or are drafts)
        opportunity_ids_to_delete = existing_opportunity_ids - processed_opportunity_ids

        for opportunity_id in opportunity_ids_to_delete:
            logger.info(
                "Deleting opportunity from search",
                extra={"opportunity_id": opportunity_id, "status": "delete"},
            )

        if opportunity_ids_to_delete:
            self.search_client.bulk_delete(self.index_name, opportunity_ids_to_delete)

        # Clear processed entries from the queue
        if processed_opportunity_ids:
            self.db_session.execute(
                delete(OpportunitySearchIndexQueue).where(
                    OpportunitySearchIndexQueue.opportunity_id.in_(processed_opportunity_ids)
                )
            )
            self.db_session.commit()

    def full_refresh(self) -> None:
        # create the index
        self.search_client.create_index(
            self.index_name,
            shard_count=self.config.shard_count,
            replica_count=self.config.replica_count,
        )

        # load the records
        for opp_batch in self.fetch_opportunities():
            self.load_records(opp_batch)

        # handle aliasing of endpoints
        self.search_client.swap_alias_index(
            self.index_name, self.config.alias_name, delete_prior_indexes=True
        )

    def fetch_opportunities(self) -> Iterator[Sequence[Opportunity]]:
        """
        Fetch the opportunities in batches. The iterator returned
        will give you each individual batch to be processed.

        Fetches all opportunities where:
            * is_draft = False
            * current_opportunity_summary is not None
        """
        return (
            self.db_session.execute(
                select(Opportunity)
                .join(CurrentOpportunitySummary)
                .where(
                    Opportunity.is_draft.is_(False),
                    CurrentOpportunitySummary.opportunity_status.isnot(None),
                )
                .options(selectinload("*"), noload(Opportunity.all_opportunity_summaries))
                .execution_options(yield_per=1000)
            )
            .scalars()
            .partitions()
        )

    def fetch_existing_opportunity_ids_in_index(self) -> set[int]:
        if not self.search_client.alias_exists(self.index_name):
            raise RuntimeError(
                "Alias %s does not exist, please run the full refresh job before the incremental job"
                % self.index_name
            )

        opportunity_ids: set[int] = set()

        for response in self.search_client.scroll(
            self.config.alias_name,
            {"size": 10000, "_source": ["opportunity_id"]},
            include_scores=False,
        ):
            for record in response.records:
                opportunity_ids.add(record["opportunity_id"])

        return opportunity_ids

    def load_records(self, records: Sequence[Opportunity]) -> set[int]:
        logger.info("Loading batch of opportunities...")
        schema = OpportunityV1Schema()
        json_records = []

        loaded_opportunity_ids = set()

        for record in records:
            logger.info(
                "Preparing opportunity for upload to search index",
                extra={
                    "opportunity_id": record.opportunity_id,
                    "opportunity_status": record.opportunity_status,
                },
            )
            json_records.append(schema.dump(record))
            self.increment(self.Metrics.RECORDS_LOADED)

            loaded_opportunity_ids.add(record.opportunity_id)

        self.search_client.bulk_upsert(self.index_name, json_records, "opportunity_id")

        return loaded_opportunity_ids
