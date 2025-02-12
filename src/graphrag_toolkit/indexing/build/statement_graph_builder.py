# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
from typing import Any

from graphrag_toolkit.indexing.model import Statement
from graphrag_toolkit.storage.graph_store import GraphStore
from graphrag_toolkit.indexing.build.graph_builder import GraphBuilder

from llama_index.core.schema import BaseNode
from llama_index.core.schema import NodeRelationship

logger = logging.getLogger(__name__)

class StatementGraphBuilder(GraphBuilder):
    
    @classmethod
    def index_key(cls) -> str:
        return 'statement'
    
    def build(self, node:BaseNode, graph_client: GraphStore, **kwargs:Any):
            
        statement_metadata = node.metadata.get('statement', {})
        
        if statement_metadata:

            statement = Statement.model_validate(statement_metadata)

            logger.debug(f'Inserting statement [statement_id: {statement.statementId}]')

            prev_statement = None
            prev_info = node.relationships.get(NodeRelationship.PREVIOUS, None)
            if prev_info:
                prev_statement = Statement.model_validate(prev_info.metadata.get('statement', None))

            if statement:

                statements = [
                    '// insert statements',
                    'UNWIND $params AS params'
                ]

                statements.extend([
                    f'MERGE (statement:`__Statement__`{{{graph_client.node_id("statementId")}: params.statement_id}})',
                    'ON CREATE SET statement.value=params.value, statement.details=params.details ON MATCH SET statement.value=params.value, statement.details=params.details' 
                ])

                properties = {
                    'statement_id': statement.statementId,
                    'value': statement.value,
                    'details': '\n'.join(s for s in statement.details)
                }

                if statement.chunkId:
                    statements.extend([
                        f'MERGE (chunk:`__Chunk__`{{{graph_client.node_id("chunkId")}: params.chunk_id}})',
                        'MERGE (statement)-[:`__MENTIONED_IN__`]->(chunk)'
                    ])
                    properties['chunk_id'] = statement.chunkId

                if statement.topicId:
                    statements.extend([
                        f'MERGE (topic:`__Topic__`{{{graph_client.node_id("topicId")}: params.topic_id}})',
                        'MERGE (statement)-[:`__BELONGS_TO__`]->(topic)'
                    ])
                    properties['topic_id'] = statement.topicId

                if prev_statement:
                    statements.extend([
                        f'MERGE (prev_statement:`__Statement__`{{{graph_client.node_id("statementId")}: params.prev_statement_id}})',
                        'MERGE (statement)-[:`__PREVIOUS__`]->(prev_statement)'
                    ])
                    properties['prev_statement_id'] = prev_statement.statementId
                
                query = '\n'.join(statements)

                graph_client.execute_query_with_retry(query, self._to_params(properties))

        else:
            logger.warning(f'statement_id missing from statement node [node_id: {node.node_id}]')   