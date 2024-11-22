# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
from lru import LRU
from tqdm import tqdm
from typing import Optional, Any, List, Union

from graphrag_toolkit.indexing.build.graph_builder import GraphBuilder
from graphrag_toolkit.indexing.node_handler import NodeHandler
from graphrag_toolkit.indexing.build.graph_batch_client import GraphBatchClient
from graphrag_toolkit.storage.graph_store import GraphStore
from graphrag_toolkit.storage.graph_store_factory import GraphStoreFactory
from graphrag_toolkit.storage.constants import INDEX_KEY 
from graphrag_toolkit.indexing.build.source_graph_builder import SourceGraphBuilder
from graphrag_toolkit.indexing.build.chunk_graph_builder import ChunkGraphBuilder
from graphrag_toolkit.indexing.build.topic_graph_builder import TopicGraphBuilder
from graphrag_toolkit.indexing.build.statement_graph_builder import StatementGraphBuilder
from graphrag_toolkit.indexing.build.fact_graph_builder import FactGraphBuilder
from graphrag_toolkit.indexing.build.graph_summary_builder import GraphSummaryBuilder

from llama_index.core.bridge.pydantic import PrivateAttr, Field
from llama_index.core.schema import BaseNode

logger = logging.getLogger(__name__)

def default_builders() -> List[GraphBuilder]:
        return [
            SourceGraphBuilder(),
            ChunkGraphBuilder(),
            TopicGraphBuilder(),
            StatementGraphBuilder(),
            FactGraphBuilder(),
            GraphSummaryBuilder()
        ]

GraphInfoType = Union[str, GraphStore]

class GraphConstruction(NodeHandler):

    @staticmethod
    def for_graph_store(graph_info:GraphInfoType=None, **kwargs):
        if isinstance(graph_info, GraphStore):
            return GraphConstruction(graph_client=graph_info, **kwargs)
        else:
            return GraphConstruction(graph_client=GraphStoreFactory.for_graph_store(graph_info, **kwargs), **kwargs)
    
    @staticmethod
    def for_neptune_database(graph_endpoint, **kwargs):
        return GraphConstruction(graph_client=GraphStoreFactory.for_neptune_database(graph_endpoint, **kwargs), **kwargs)
    
    @staticmethod
    def for_neptune_analytics(graph_id, **kwargs):
        return GraphConstruction(graph_client=GraphStoreFactory.for_neptune_analytics(graph_id, **kwargs), **kwargs)
    
    @staticmethod
    def for_dummy_graph_store(*args, **kwargs):
        return GraphConstruction(graph_client=GraphStoreFactory.for_dummy_graph_store(), **kwargs)
    
    graph_client: GraphStore 
    builders:List[GraphBuilder] = Field(
        description='Graph builders',
        default_factory=default_builders
    )
    _node_ids: Optional[Any] = PrivateAttr(default=None)

    def __getstate__(self):
        self._node_ids = None
        return super().__getstate__()
    
    @property
    def node_ids(self):
        if self._node_ids is None:
            self._node_ids = LRU(1000)
        return self._node_ids

    def accept(self, nodes: List[BaseNode], **kwargs: Any):

        builders_dict = {}
        for b in self.builders:
            if b.index_key() not in builders_dict:
                builders_dict[b.index_key()] = []
            builders_dict[b.index_key()].append(b)

        batch_writes_enabled = kwargs['batch_writes_enabled']
        batch_size = kwargs['batch_size']

        logger.debug(f'Batch config: [batch_writes_enabled: {batch_writes_enabled}, batch_size: {batch_size}]')

        with GraphBatchClient(self.graph_client, batch_writes_enabled=batch_writes_enabled, batch_size=batch_size) as batch_client:
        
            node_iterable = nodes if not self.show_progress else tqdm(nodes, desc='Building graph')

            for node in node_iterable:

                node_id = node.node_id
                
                if self.node_ids.has_key(node_id):
                    logger.debug(f'Ignoring duplicate node [node_id: {node_id}]')

                elif [key for key in [INDEX_KEY] if key in node.metadata]:
                    
                    try:
                    
                        index = node.metadata[INDEX_KEY]['index']
                        builders = builders_dict.get(index, None)

                        if builders:
                            [builder.build(node, batch_client, self.node_ids) for builder in builders]
                            self.node_ids[node_id] = None
                        else:
                            logger.debug(f'No builders for node [index: {index}]')

                    except Exception as e:
                        logger.exception('An error occurred while building the graph')
                        raise e
                        
                else:
                    logger.debug(f'Ignoring node [node_id: {node_id}]')
                    
                if batch_client.allow_yield(node):
                    yield node

            batch_nodes = batch_client.apply_batch_operations()
            for node in batch_nodes:
                yield node

        