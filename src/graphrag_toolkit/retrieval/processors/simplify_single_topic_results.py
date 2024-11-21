# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import statistics
from typing import List, Dict

from graphrag_toolkit.retrieval.processors import ProcessorBase, ProcessorArgs
from graphrag_toolkit.retrieval.model import SearchResultCollection, SearchResult

from llama_index.core.schema import QueryBundle

class SimplifySingleTopicResults(ProcessorBase):
    def __init__(self, args:ProcessorArgs):
        super().__init__(args)

    def _process_results(self, search_results:SearchResultCollection, query:QueryBundle) -> SearchResultCollection:

        def simplify_result(index:int, search_result:SearchResult):

            if len(search_result.topics) == 1:
                topic = search_result.topics[0]
                search_result.topic = topic.topic
                search_result.statements.extend(topic.statements)
                search_result.topics.clear()
                return search_result
            else:
                return search_result
        
        return self._apply_to_search_results(search_results, simplify_result)