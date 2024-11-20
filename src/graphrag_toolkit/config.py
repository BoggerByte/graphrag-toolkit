# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import os
import json
from dataclasses import dataclass
from typing import Optional, Union

from llama_index.llms.bedrock import Bedrock
from llama_index.embeddings.bedrock import BedrockEmbedding
from llama_index.core.settings import Settings
from llama_index.core.embeddings.utils import EmbedType
from llama_index.core.llms import LLM
from llama_index.core.base.embeddings.base import BaseEmbedding

LLMType = Union[LLM, str]

DEFAULT_EXTRACTION_MODEL = 'anthropic.claude-3-sonnet-20240229-v1:0'
DEFAULT_RESPONSE_MODEL = 'anthropic.claude-3-sonnet-20240229-v1:0'
DEFAULT_EVALUATION_MODEL = 'anthropic.claude-3-sonnet-20240229-v1:0'
DEFAULT_EMBEDDINGS_MODEL = 'cohere.embed-english-v3'
DEFAULT_RERANKING_MODEL = 'mixedbread-ai/mxbai-rerank-xsmall-v1'
DEFAULT_EMBEDDINGS_DIMENSIONS = 1024
DEFAULT_EXTRACTION_PIPELINE_NUM_WORKERS = 2
DEFAULT_EXTRACTION_PIPELINE_BATCH_SIZE = 4
DEFAULT_BUILD_PIPELINE_NUM_WORKERS = 2
DEFAULT_BUILD_PIPELINE_BATCH_SIZE = 25
DEFAULT_BUILD_PIPELINE_BATCH_WRITES_ENABLED = True
DEFAULT_ENABLE_CACHE = False

def _is_json_string(s):
    try:
        json.loads(s)
        return True
    except ValueError:
        return False

@dataclass
class _GraphRAGConfig:

    _extraction_llm: Optional[LLM] = None
    _response_llm: Optional[LLM] = None 
    _evaluation_llm: Optional[LLM] = None 
    _embed_model: Optional[BaseEmbedding] = None
    _embed_dimensions: Optional[int] = None
    _reranking_model: Optional[str] = None
    _extraction_pipeline_num_workers: Optional[int] = None
    _extraction_pipeline_batch_size: Optional[int] = None
    _build_pipeline_num_workers: Optional[int] = None
    _build_pipeline_batch_size: Optional[int] = None
    _build_pipeline_batch_writes_enabled: Optional[bool] = None
    _enable_cache: Optional[bool] = None

    @property
    def extraction_pipeline_num_workers(self) -> int:
        if self._extraction_pipeline_num_workers is None:
            self.extraction_pipeline_num_workers = DEFAULT_EXTRACTION_PIPELINE_NUM_WORKERS

        return self._extraction_pipeline_num_workers

    @extraction_pipeline_num_workers.setter
    def extraction_pipeline_num_workers(self, num_workers:int) -> None:
        self._extraction_pipeline_num_workers = num_workers

    @property
    def extraction_pipeline_batch_size(self) -> int:
        if self._extraction_pipeline_batch_size is None:
            self.extraction_pipeline_batch_size = DEFAULT_EXTRACTION_PIPELINE_BATCH_SIZE

        return self._extraction_pipeline_batch_size

    @extraction_pipeline_batch_size.setter
    def extraction_pipeline_batch_size(self, batch_size:int) -> None:
        self._extraction_pipeline_batch_size = batch_size

    @property
    def build_pipeline_num_workers(self) -> int:
        if self._build_pipeline_num_workers is None:
            self.build_pipeline_num_workers = DEFAULT_BUILD_PIPELINE_NUM_WORKERS

        return self._build_pipeline_num_workers

    @build_pipeline_num_workers.setter
    def build_pipeline_num_workers(self, num_workers:int) -> None:
        self._build_pipeline_num_workers = num_workers

    @property
    def build_pipeline_batch_size(self) -> int:
        if self._build_pipeline_batch_size is None:
            self.build_pipeline_batch_size = DEFAULT_BUILD_PIPELINE_BATCH_SIZE

        return self._build_pipeline_batch_size

    @build_pipeline_batch_size.setter
    def build_pipeline_batch_size(self, batch_size:int) -> None:
        self._build_pipeline_batch_size = batch_size

    @property
    def build_pipeline_batch_writes_enabled(self) -> bool:
        if self._build_pipeline_batch_writes_enabled is None:
            self.build_pipeline_batch_writes_enabled = DEFAULT_BUILD_PIPELINE_BATCH_WRITES_ENABLED

        return self._build_pipeline_batch_writes_enabled

    @build_pipeline_batch_writes_enabled.setter
    def build_pipeline_batch_writes_enabled(self, batch_writes_enabled:bool) -> None:
        self._build_pipeline_batch_writes_enabled = batch_writes_enabled

    @property
    def enable_cache(self) -> bool:
        if self._enable_cache is None:
            self.enable_cache = DEFAULT_ENABLE_CACHE
        return self._enable_cache

    @enable_cache.setter
    def enable_cache(self, enable_cache:bool) -> None:
        self._enable_cache = enable_cache
   
    @property
    def extraction_llm(self) -> LLM:
        if self._extraction_llm is None:
            self.extraction_llm = os.environ.get('EXTRACTION_MODEL', DEFAULT_EXTRACTION_MODEL)
        return self._extraction_llm

    @extraction_llm.setter
    def extraction_llm(self, llm: LLMType) -> None:
        if isinstance(llm, LLM):
            self._extraction_llm = llm
        else:
            if _is_json_string(llm):
                self._extraction_llm = Bedrock.from_json(llm)
            else:
                json_str = f'''{{
                    "model": "{llm}",
                    "temperature": 0.0,
                    "max_tokens": 4096,
                    "streaming": true
                }}'''
                self._extraction_llm = Bedrock.from_json(json_str)
        self._extraction_llm.callback_manager = Settings.callback_manager

    @property
    def response_llm(self) -> LLM:
        if self._response_llm is None:
            self.response_llm = os.environ.get('RESPONSE_MODEL', DEFAULT_RESPONSE_MODEL)
            
        return self._response_llm

    @response_llm.setter
    def response_llm(self, llm: LLMType) -> None:
        if isinstance(llm, LLM):
            self._response_llm = llm
        else:
            if _is_json_string(llm):
                self._response_llm = Bedrock.from_json(llm)
            else:
                json_str = f'''{{
                    "model": "{llm}",
                    "temperature": 0.0,
                    "max_tokens": 4096,
                    "streaming": true
                }}'''
                self._response_llm = Bedrock.from_json(json_str)
        self._response_llm.callback_manager = Settings.callback_manager
       
    @property
    def evaluation_llm(self) -> LLM:
        if self._evaluation_llm is None:
            self.evaluation_llm = os.environ.get('EVALUATION_MODEL', DEFAULT_EVALUATION_MODEL)
            
        return self._evaluation_llm

    @evaluation_llm.setter
    def evaluation_llm(self, llm: LLMType) -> None:
        if isinstance(llm, LLM):
            self._evaluation_llm = llm
        else:
            if _is_json_string(llm):
                self._evaluation_llm = Bedrock.from_json(llm)
            else:
                json_str = f'''{{
                    "model": "{llm}",
                    "temperature": 0.0,
                    "max_tokens": 4096,
                    "streaming": true
                }}'''
                self._evaluation_llm = Bedrock.from_json(json_str)
        self._evaluation_llm.callback_manager = Settings.callback_manager
       
    @property
    def embed_model(self) -> BaseEmbedding:
        if self._embed_model is None:
            self.embed_model = os.environ.get('EMBEDDINGS_MODEL', DEFAULT_EMBEDDINGS_MODEL)

        return self._embed_model

    @embed_model.setter
    def embed_model(self, embed_model: EmbedType) -> None:
        if isinstance(embed_model, str):
            if _is_json_string(embed_model):
                self._embed_model = BedrockEmbedding.from_json(embed_model) 
            else:
                json_str = f'''{{
                    "model_name": "{embed_model}"
                }}'''
                self._embed_model = BedrockEmbedding.from_json(json_str) 
        else:
            self._embed_model = embed_model
        self._embed_model.callback_manager = Settings.callback_manager

    @property
    def embed_dimensions(self) -> int:
       if self._embed_dimensions is None:
           self.embed_dimensions = int(os.environ.get('EMBEDDINGS_DIMENSIONS', DEFAULT_EMBEDDINGS_DIMENSIONS))
           
       return self._embed_dimensions

    @embed_dimensions.setter
    def embed_dimensions(self, embed_dimensions: int) -> None:
       self._embed_dimensions = embed_dimensions

    @property
    def reranking_model(self) -> str:
       if self._reranking_model is None:
           self._reranking_model = os.environ.get('RERANKING_MODEL', DEFAULT_RERANKING_MODEL)
           
       return self._reranking_model

    @reranking_model.setter
    def reranking_model(self, reranking_model: str) -> None:
       self._reranking_model = reranking_model
    
GraphRAGConfig = _GraphRAGConfig()