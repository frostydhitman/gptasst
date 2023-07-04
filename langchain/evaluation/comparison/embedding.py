"""A chain for comparing the output of two models using embeddings."""
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np
from pydantic import Field, root_validator

from langchain.callbacks.manager import (
    AsyncCallbackManagerForChainRun,
    CallbackManagerForChainRun,
    Callbacks,
)
from langchain.chains.base import Chain
from langchain.embeddings.base import Embeddings
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.evaluation.schema import PairwiseStringEvaluator
from langchain.math_utils import cosine_similarity


class EmbeddingDistance(str, Enum):
    COSINE = "cosine"
    EUCLIDEAN = "euclidean"
    MANHATTAN = "manhattan"
    CHEBYSHEV = "chebyshev"
    HAMMING = "hamming"


class PairwiseEmbeddingStringEvalChain(Chain, PairwiseStringEvaluator):
    """A chain for comparing the output of two models using embeddings."""

    embeddings: Embeddings = Field(default_factory=OpenAIEmbeddings)
    """The embedding objects to vectorize the outputs."""
    distance_metric: EmbeddingDistance = Field(default=EmbeddingDistance.COSINE)
    """The distance metric to use for comparing the embeddings."""

    @root_validator
    def _validate_distance_metric(cls, values: dict) -> dict:
        """Validate the distance metric.

        Args:
            values (dict): The values to validate.

        Returns:
            dict: The validated values.
        """
        values["distance_metric"] = values["distance_metric"].lower()
        return values

    def _get_metric(self, metric: EmbeddingDistance) -> Any:
        """Get the metric function for the given metric name.

        Args:
            metric (str): The metric name.

        Returns:
            Any: The metric function.
        """
        metrics = {
            EmbeddingDistance.COSINE: self._cosine_distance,
            EmbeddingDistance.EUCLIDEAN: self._euclidean_distance,
            EmbeddingDistance.MANHATTAN: self._manhattan_distance,
            EmbeddingDistance.CHEBYSHEV: self._chebyshev_distance,
            EmbeddingDistance.HAMMING: self._hamming_distance,
        }
        if metric in metrics:
            return metrics[metric]
        else:
            raise ValueError(f"Invalid metric: {metric}")

    @staticmethod
    def _cosine_distance(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        return 1.0 - cosine_similarity(a, b)

    @staticmethod
    def _euclidean_distance(a: np.ndarray, b: np.ndarray) -> np.floating:
        return np.linalg.norm(a - b)

    @staticmethod
    def _manhattan_distance(a: np.ndarray, b: np.ndarray) -> np.floating:
        return np.sum(np.abs(a - b))

    @staticmethod
    def _chebyshev_distance(a: np.ndarray, b: np.ndarray) -> np.floating:
        return np.max(np.abs(a - b))

    @staticmethod
    def _hamming_distance(a: np.ndarray, b: np.ndarray) -> np.floating:
        return np.mean(a != b)

    def _compute_score(self, vectors: np.ndarray) -> float:
        metric = self._get_metric(self.distance_metric)
        score = metric(vectors[0].reshape(1, -1), vectors[1].reshape(1, -1)).item()
        return score

    @property
    def input_keys(self) -> List[str]:
        return ["prediction", "prediction_b"]

    @property
    def output_keys(self) -> List[str]:
        return ["score"]

    def _call(
        self,
        inputs: Dict[str, Any],
        run_manager: CallbackManagerForChainRun | None = None,
    ) -> Dict[str, Any]:
        vectors = np.array(
            self.embeddings.embed_documents(
                [inputs["prediction"], inputs["prediction_b"]]
            )
        )
        score = self._compute_score(vectors)
        return {"score": score}

    async def _acall(
        self,
        inputs: Dict[str, Any],
        run_manager: AsyncCallbackManagerForChainRun | None = None,
    ) -> Dict[str, Any]:
        embedded = await self.embeddings.aembed_documents(
            [inputs["prediction"], inputs["prediction_b"]]
        )
        vectors = np.array(embedded)
        score = self._compute_score(vectors)
        return {"score": score}

    def evaluate_string_pairs(
        self,
        *,
        prediction: str,
        prediction_b: str,
        input: Optional[str] = None,
        reference: Optional[str] = None,
        callbacks: Callbacks = None,
        **kwargs: Any,
    ) -> dict:
        """Evaluate the embedding distance between two predictions.

        Args:
            prediction (str): The output string from the first model.
            prediction_b (str): The output string from the second model.
            input (str): The input or task string.
            callbacks (Callbacks, optional): The callbacks to use.
            reference (str, optional): The reference string, if any.
            **kwargs (Any): Additional keyword arguments.

        Returns:
            dict: A dictionary containing:
                - score: The embedding distance between the two
                    predictions.
        """
        return self(
            inputs={"prediction": prediction, "prediction_b": prediction_b},
            callbacks=callbacks,
        )

    async def aevaluate_string_pairs(
        self,
        *,
        prediction: str,
        prediction_b: str,
        input: Optional[str] = None,
        reference: Optional[str] = None,
        callbacks: Callbacks = None,
        **kwargs: Any,
    ) -> dict:
        """Asynchronously evaluate the embedding distance

        between two predictions.

        Args:
            prediction (str): The output string from the first model.
            prediction_b (str): The output string from the second model.
            input (str): The input or task string.
            callbacks (Callbacks, optional): The callbacks to use.
            reference (str, optional): The reference string, if any.
            **kwargs (Any): Additional keyword arguments.

        Returns:
            dict: A dictionary containing:
                - score: The embedding distance between the two
                    predictions.
        """
        return await self.acall(
            inputs={"prediction": prediction, "prediction_b": prediction_b},
            callbacks=callbacks,
        )