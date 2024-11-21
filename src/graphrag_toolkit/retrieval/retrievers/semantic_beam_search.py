# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import List, Set, Tuple, Optional, Any
from queue import PriorityQueue
import numpy as np
import logging

from llama_index.core.base.base_retriever import BaseRetriever
from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode

from graphrag_toolkit.storage.graph_store import GraphStore
from graphrag_toolkit.storage import VectorStore
from graphrag_toolkit.retrieval.utils.statement_utils import get_top_k, SharedEmbeddingCache

logger = logging.getLogger(__name__)

class SemanticBeamGraphSearch(BaseRetriever):
    def __init__(
        self,
        vector_store: VectorStore,
        graph_store: GraphStore,
        embedding_cache: Optional[SharedEmbeddingCache] = None,
        max_depth: int = 3,
        beam_width: int = 10,
        shared_nodes: Optional[List[NodeWithScore]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__()
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.embedding_cache = embedding_cache
        self.max_depth = max_depth
        self.beam_width = beam_width
        self.shared_nodes = shared_nodes

    def get_neighbors(self, statement_id: str) -> List[str]:
        """Get neighboring statements through entity connections."""
        cypher = f"""
        MATCH (e:Entity)-[:SUBJECT|OBJECT]->(:Fact)-[:SUPPORTS]->(s:Statement)
        WHERE {self.graph_store.node_id('s.statementId')} = $statementId
        WITH s, COLLECT(DISTINCT e) AS entities
        UNWIND entities AS entity
        MATCH (entity)-[:SUBJECT|OBJECT]->(:Fact)-[:SUPPORTS]->(e_neighbors:Statement)
        RETURN DISTINCT {self.graph_store.node_id('e_neighbors.statementId')} as statementId
        """
        
        neighbors = self.graph_store.execute_query(cypher, {'statementId': statement_id})
        return [n['statementId'] for n in neighbors]

    def beam_search(
        self, 
        query_embedding: np.ndarray,
        start_statement_ids: List[str]
    ) -> List[Tuple[str, List[str]]]:  # [(statement_id, path), ...]
        visited: Set[str] = set()
        results: List[Tuple[str, List[str]]] = []
        queue: PriorityQueue = PriorityQueue()

        # Get initial embeddings and scores
        start_embeddings = self.embedding_cache.get_embeddings(start_statement_ids)
        start_scores = get_top_k(
            query_embedding,
            start_embeddings,
            len(start_statement_ids)
        )

        # Initialize queue with start statements
        for similarity, statement_id in start_scores:
            queue.put((-similarity, 0, statement_id, [statement_id]))

        while not queue.empty() and len(results) < self.beam_width:
            neg_score, depth, current_id, path = queue.get()

            if current_id in visited:
                continue

            visited.add(current_id)
            results.append((current_id, path))

            if depth < self.max_depth:
                neighbor_ids = self.get_neighbors(current_id)
                
                if neighbor_ids:
                    # Get embeddings for neighbors using shared cache
                    neighbor_embeddings = self.embedding_cache.get_embeddings(neighbor_ids)
                    
                    # Score neighbors
                    scored_neighbors = get_top_k(
                        query_embedding,
                        neighbor_embeddings,
                        self.beam_width
                    )

                    # Add neighbors to queue
                    for similarity, neighbor_id in scored_neighbors:
                        if neighbor_id not in visited:
                            new_path = path + [neighbor_id]
                            queue.put(
                                (-similarity, depth + 1, neighbor_id, new_path)
                            )

        return results

    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        try:
            # 1. Get initial nodes (either shared or fallback)
            initial_statement_ids = []
            if self.shared_nodes:
                initial_statement_ids = [
                    n.node.metadata['statement']['statementId'] 
                    for n in self.shared_nodes
                ]
            else:
                # Fallback to vector similarity
                results = self.vector_store.get_index('statement').top_k(
                    query_bundle,
                    top_k=self.beam_width * 2
                )
                initial_statement_ids = [
                    r['statement']['statementId'] for r in results
                ]

            if not initial_statement_ids:
                return []

            # 2. Perform beam search
            beam_results = self.beam_search(
                query_bundle.embedding,
                initial_statement_ids
            )

            # 3. Create nodes for new statements only
            nodes = []
            initial_ids = set(initial_statement_ids)
            for statement_id, path in beam_results:
                if statement_id not in initial_ids:
                    node = TextNode(
                        text="",  # Placeholder
                        metadata={
                            'statement': {'statementId': statement_id},
                            'search_type': 'beam_search',
                            'depth': len(path),
                            'path': path
                        }
                    )
                    nodes.append(NodeWithScore(node=node, score=0.0))

            return nodes

        except Exception as e:
            logger.error(f"Error in SemanticBeamGraphSearch: {e}")
            return []