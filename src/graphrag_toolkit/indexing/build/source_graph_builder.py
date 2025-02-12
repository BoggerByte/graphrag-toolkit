# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import logging

from graphrag_toolkit.storage.graph_store import GraphStore
from graphrag_toolkit.indexing.build.graph_builder import GraphBuilder

from llama_index.core.schema import BaseNode

logger = logging.getLogger(__name__)

class SourceGraphBuilder(GraphBuilder):
    
    @classmethod
    def index_key(cls) -> str:
        return 'source'
    
    def build(self, node:BaseNode, graph_client: GraphStore):
            
        source_metadata = node.metadata.get('source', {})
        source_id = source_metadata.get('sourceId', None)

        if source_id:

            logger.debug(f'Inserting source [source_id: {source_id}]')
        
            statements = [
                '// insert source',
                'UNWIND $params AS params',
                f"MERGE (source:Source{{{graph_client.node_id('sourceId')}: '{source_id}'}})"
            ]

            metadata = source_metadata.get('metadata', {})
            
            clean_metadata = {}
            for k, v in metadata.items():
                clean_metadata[k.replace(' ', '_')] = str(v)
        
            if clean_metadata:
                all_properties = ', '.join(f'source.{key} = params.{key}' for key,_ in clean_metadata.items())
                statements.append(f'ON CREATE SET {all_properties} ON MATCH SET {all_properties}')
            
            query = '\n'.join(statements)
            
            graph_client.execute_query_with_retry(query, self._to_params(clean_metadata))

        else:
            logger.warning(f'source_id missing from source node [node_id: {node.node_id}]')