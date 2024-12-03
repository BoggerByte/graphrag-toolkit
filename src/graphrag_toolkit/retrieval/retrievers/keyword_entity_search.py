# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
import asyncio
from typing import List

from graphrag_toolkit.config import GraphRAGConfig
from graphrag_toolkit.storage.graph_store import GraphStore
from graphrag_toolkit.storage.graph_utils import node_result, search_string_from
from graphrag_toolkit.utils import LLMCache, LLMCacheType
from graphrag_toolkit.retrieval.model import ScoredEntity
from graphrag_toolkit.retrieval.prompts import SIMPLE_EXTRACT_KEYWORDS_PROMPT, EXTENDED_EXTRACT_KEYWORDS_PROMPT

from llama_index.core.base.base_retriever import BaseRetriever
from llama_index.core.prompts import PromptTemplate
from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode
from llama_index.core.async_utils import run_async_tasks

logger = logging.getLogger(__name__)

class KeywordEntitySearch(BaseRetriever):
    def __init__(self,
                 graph_store:GraphStore,
                 llm:LLMCacheType=None, 
                 simple_extract_keywords_template=SIMPLE_EXTRACT_KEYWORDS_PROMPT,
                 extended_extract_keywords_template=EXTENDED_EXTRACT_KEYWORDS_PROMPT,
                 max_keywords=10,
                 expand_entities=False):
        
        self.graph_store = graph_store
        self.llm = llm if llm and isinstance(llm, LLMCache) else LLMCache(
            llm=llm or GraphRAGConfig.response_llm,
            enable_cache=GraphRAGConfig.enable_cache
        )
        self.simple_extract_keywords_template=simple_extract_keywords_template
        self.extended_extract_keywords_template=extended_extract_keywords_template
        self.max_keywords = max_keywords
        self.expand_entities = expand_entities

    
    def _expand_entities(self, scored_entities:List[ScoredEntity]):
        
        if not scored_entities or len(scored_entities) >= self.max_keywords:
            return scored_entities
        
        original_entity_ids = [entity.entity.entityId for entity in scored_entities if entity.score > 0]  
        neighbour_entity_ids = set()
        
        start_entity_ids = original_entity_ids.copy()     

        for limit in range (3, 1, -1):
        
            cypher = f"""
            // expand entities
            MATCH (entity:Entity)
            -[:SUBJECT|OBJECT]->(:Fact)-[:SUPPORTS]->(:Statement)
            <-[:SUPPORTS]-(:Fact)<-[:SUBJECT|OBJECT]-
            (other:Entity)
            WHERE  {self.graph_store.node_id('entity.entityId')} IN $entityIds
            AND NOT {self.graph_store.node_id('other.entityId')} IN $entityIds
            WITH entity, other LIMIT $limit
            RETURN {{
                {node_result('entity', self.graph_store.node_id('entity.entityId'), properties=['value', 'class'])},
                others: collect(DISTINCT {self.graph_store.node_id('other.entityId')})
            }} AS result    
            """

            params = {
                'entityIds': start_entity_ids,
                'limit': limit
            }
        
            results = self.graph_store.execute_query(cypher, params)

            other_entity_ids = [
                other_id
                for result in results
                for other_id in result['result']['others'] 
            ]
            
            neighbour_entity_ids.update(set(other_entity_ids))
            
            start_entity_ids = other_entity_ids
            
      
        cypher = f"""
        // expand entities: score entities by number of facts
        MATCH (entity:Entity)-[:SUBJECT]->(f:Fact)
        WHERE {self.graph_store.node_id('entity.entityId')} IN $entityIds
        WITH entity, count(f) AS score
        RETURN {{
            {node_result('entity', self.graph_store.node_id('entity.entityId'), properties=['value', 'class'])},
            score: score
        }} AS result
        """

        params = {
            'entityIds': list(neighbour_entity_ids)
        }

        results = self.graph_store.execute_query(cypher, params)
        
        neighbour_entities = [
            ScoredEntity.model_validate(result['result'])
            for result in results 
            if result['result']['entity']['entityId'] not in original_entity_ids      
        ]
        
        neighbour_entities.sort(key=lambda e:e.score, reverse=True)

        scored_entities.extend(neighbour_entities[:5])        
        scored_entities.sort(key=lambda e:e.score, reverse=True)

        logger.debug('Expanded entities:\n' + '\n'.join(
            entity.model_dump_json(exclude_unset=True, exclude_defaults=True, exclude_none=True, warnings=False) 
            for entity in scored_entities)
        )

        return scored_entities
        
    async def _get_entities_for_keyword(self, keyword:str) -> List[ScoredEntity]:

        def blocking_query():

            parts = keyword.split('|')

            if len(parts) > 1:

                cypher = f"""
                // get entities for keywords
                MATCH (entity:Entity)
                WHERE entity.search_str = $keyword and entity.class STARTS WITH $classification
                OPTIONAL MATCH (entity)-[r:RELATION]->(:Entity) 
                WITH entity, sum(r.count) AS score ORDER BY score DESC
                RETURN {{
                    {node_result('entity', self.graph_store.node_id('entity.entityId'), properties=['value', 'class'])},
                    score: score
                }} AS result"""

                params = {
                    'keyword': search_string_from(parts[0]),
                    'classification': parts[1]
                }
            else:
                cypher = f"""
                // get entities for keywords
                MATCH (entity:Entity)
                WHERE entity.search_str = $keyword
                OPTIONAL MATCH (entity)-[r:RELATION]->(:Entity) 
                WITH entity, sum(r.count) AS score ORDER BY score DESC
                RETURN {{
                    {node_result('entity', self.graph_store.node_id('entity.entityId'), properties=['value', 'class'])},
                    score: score
                }} AS result"""

                params = {
                    'keyword': search_string_from(parts[0])
                }

            results = self.graph_store.execute_query(cypher, params)

            return [
                ScoredEntity.model_validate(result['result'])
                for result in results
                if result['result']['score'] != 0
            ]

        coro = asyncio.to_thread(blocking_query)
        
        return await coro
                        
    def _get_entities_for_keywords(self, keywords:List[str])  -> List[ScoredEntity]:
        
        tasks = [
            self._get_entities_for_keyword(keyword)
            for keyword in keywords
            if keyword
        ]

        task_results:List[List[ScoredEntity]] = run_async_tasks(tasks)

        scored_entity_mappings = {}

        for result in task_results:
            for scored_entity in result:
                entity_id = scored_entity.entity.entityId
                if entity_id not in scored_entity_mappings:
                    scored_entity_mappings[entity_id] = scored_entity
                else:
                    scored_entity_mappings[entity_id].score += scored_entity.score

        scored_entities = list(scored_entity_mappings.values())

        scored_entities.sort(key=lambda e:e.score, reverse=True)

        logger.debug('Initial entities:\n' + '\n'.join(
            entity.model_dump_json(exclude_unset=True, exclude_defaults=True, exclude_none=True, warnings=False) 
            for entity in scored_entities)
        )

        return scored_entities

        
    async def _extract_keywords(self, s:str, num_keywords:int, prompt_template:str):

        def blocking_llm_call():
            return self.llm.predict(
                PromptTemplate(template=prompt_template),
                text=s,
                max_keywords=num_keywords
            )
        
        coro = asyncio.to_thread(blocking_llm_call)
        
        results = await coro

        keywords = results.split('^')

        return keywords

    async def _get_simple_keywords(self, query, num_keywords):
        simple_keywords = await self._extract_keywords(query, num_keywords, self.simple_extract_keywords_template)
        logger.debug(f'Simple keywords: {simple_keywords}')
        return simple_keywords
    
    async def _get_enriched_keywords(self, query, num_keywords):
        enriched_keywords = await self._extract_keywords(query, num_keywords, self.extended_extract_keywords_template)
        logger.debug(f'Enriched keywords: {enriched_keywords}')
        return enriched_keywords

    def _get_keywords(self, query, max_keywords):
        
        def add_keyword(k):
            if k not in keywords:
                keywords.append(k)
        
        keywords = [] 

        num_keywords = max(int(max_keywords/2), 1)

        tasks = [
            self._get_simple_keywords(query, num_keywords),
            self._get_enriched_keywords(query, num_keywords),
        ]

        task_results = run_async_tasks(tasks)

        for result in task_results:
            for keyword in result:
                add_keyword(keyword)

        logger.debug(f'Keywords: {keywords}')
        
        return keywords

    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        
        query = query_bundle.query_str
        
        keywords = self._get_keywords(query, self.max_keywords)
        scored_entities:List[ScoredEntity] = self._get_entities_for_keywords(keywords)

        if self.expand_entities:
            scored_entities = self._expand_entities(scored_entities)

        return [
            NodeWithScore(
                node=TextNode(text=scored_entity.entity.model_dump_json(exclude_none=True, exclude_defaults=True, indent=2)),
                score=scored_entity.score
            ) 
            for scored_entity in scored_entities
        ]