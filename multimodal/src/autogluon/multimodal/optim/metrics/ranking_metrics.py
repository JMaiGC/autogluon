import logging
import math
import operator
from typing import Dict, List, Optional, Tuple, Union

import numpy as np

from ...constants import MAP, NDCG, PRECISION, RECALL

logger = logging.getLogger(__name__)


class RankingMetrics:
    def __init__(
        self,
        pred: Dict[str, Dict],
        target: Dict[str, Dict],
        is_higher_better=True,
    ):
        """
        Evaluation Metrics for information retrieval tasks such as document retrieval, image retrieval, etc.
        Reference: https://www.cs.cornell.edu/courses/cs4300/2013fa/lectures/metrics-2-4pp.pdf

        Parameters
        ----------
        pred:
            the prediction of the ranking model. It has the following form.
            pred = {
                'q1': {
                    'd1': 1,
                    'd3': 0,
                },
                'q2': {
                    'd2': 1,
                    'd3': 1,
                },
            }
            where q refers to queries, and d refers to documents, each query has a few relevant documents.
            0s and 1s are model predicted scores (does not need to be binary).
        target:
            the ground truth query and response relevance which has the same form as pred.
        is_higher_better:
            if higher relevance score means higher ranking.
            if the relevance score is cosine similarity / dot product, it should be set to True;
            if it is Eulidean distance, it should be False.
        """
        self.pred = pred
        self.target = target
        self.is_higher_better = is_higher_better
        # the supported metrics in this script
        self.supported_metrics = {
            "precision": 0,
            "recall": 1,
            "mrr": 2,
            "map": 3,
            "ndcg": 4,
        }

        assert len(pred) == len(
            target
        ), f"The prediction and groudtruth target should have the same number of queries, \
        while there are {len(pred)} queries in prediction and {len(target)} in the target."

        self.results = {}
        for key in target.keys():
            self.results.update({key: [target[key], pred[key]]})

    def compute(self, metrics: Union[str, list] = None, k: Optional[int] = 10):
        """
        compute and return ranking scores.

        Parameters
        ----------
        metrics:
            user provided metrics
        k:
            the cutoff value for NDCG, MAP, Recall, MRR, and Precision

        Returns
        -------
        Computed score.

        """
        if isinstance(metrics, str):
            metrics = [metrics]
        if not metrics:  # no metric is provided
            metrics = self.supported_metrics.keys()

        return_res = {}

        eval_res = np.mean(
            [list(self._compute_one(idx, k)) for idx in self.results.keys()],
            axis=0,
        )

        for metric in metrics:
            metric = metric.lower()
            if metric in self.supported_metrics:
                return_res.update({f"{metric}@{k}": eval_res[self.supported_metrics[metric]]})

        return return_res

    def _compute_one(self, idx, k):
        """
        compute and return the ranking scores for one query.
        for definition of these metrics, please refer to
        https://www.cs.cornell.edu/courses/cs4300/2013fa/lectures/metrics-2-4pp.pdf

        Parameters
        ----------
        idx:
            the index of the query
        k:
            the cutoff value for NDCG, MAP, Recall, MRR, and Precision

        Returns
        -------
        Computed score.
        """
        precision, recall, mrr, mAP, ndcg = 0, 0, 0, 0, 0
        target, pred = self.results[idx][0], self.results[idx][1]

        # sort the ground truth and predictions in descending order
        sorted_target = dict(
            sorted(
                target.items(),
                key=operator.itemgetter(1),
                reverse=self.is_higher_better,
            )
        )
        sorted_pred = dict(
            sorted(
                pred.items(),
                key=operator.itemgetter(1),
                reverse=self.is_higher_better,
            )
        )
        sorted_target_values = list(sorted_target.values())
        sorted_pred_values = list(sorted_pred.values())

        # number of positive relevance in target
        # negative numbers and zero are considered as negative response
        num_pos_target = len([val for val in sorted_target_values if val > 0])

        at_k = k if num_pos_target > k else num_pos_target

        first_k_items_list = list(sorted_pred.items())[0:k]

        rank = 0
        hit_rank = []  # correctly retrieved items
        for key, value in first_k_items_list:
            if key in sorted_target and sorted_target[key] > 0:
                hit_rank.append(rank)
            rank += 1
        count = len(hit_rank)
        # compute the precision and recall
        precision = count / k
        recall = count / num_pos_target

        dcg = 0
        if hit_rank:  # not empty
            # compute the mean reciprocal rank
            mrr = 1 / (hit_rank[0] + 1)
            # compute the mean average precision
            mAP = np.sum([sorted_pred_values[rank] * (i + 1) / (rank + 1) for i, rank in enumerate(hit_rank)])
            # compute the discounted cumulative gain
            dcg = np.sum([1 / math.log(rank + 2, 2) for rank in hit_rank])

        # compute the ideal discounted cumulative gain
        idcg = np.sum([1 / math.log(i + 2, 2) for i in range(at_k)])
        # compute the normalized discounted cumulative gain
        ndcg = dcg / idcg
        mAP /= at_k

        return precision, recall, mrr, mAP, ndcg


def compute_ranking_score(
    results: Dict[str, Dict],
    qrel_dict: Dict[str, Dict],
    metrics: List[str],
    cutoffs: Optional[List[int]] = [5, 10, 20],
):
    """
    Compute the ranking metrics, e.g., NDCG, MAP, Recall, and Precision.
    TODO: Consider MRR.

    Parameters
    ----------
    results:
        The query/document ranking list by the model.
    qrel_dict:
        The groundtruth query and document relevance.
    metrics
        A list of metrics to compute.
    cutoffs:
        The cutoff values for NDCG, MAP, Recall, and Precision.

    Returns
    -------
    A dict of metric scores.
    """
    scores = {}
    evaluator = RankingMetrics(pred=results, target=qrel_dict)
    for k in cutoffs:
        scores.update(evaluator.compute(k=k))

    metric_results = dict()
    for k in cutoffs:
        for per_metric in metrics:
            if per_metric.lower() == NDCG:
                metric_results[f"{NDCG}@{k}"] = 0.0
            elif per_metric.lower() == MAP:
                metric_results[f"{MAP}@{k}"] = 0.0
            elif per_metric.lower() == RECALL:
                metric_results[f"{RECALL}@{k}"] = 0.0
            elif per_metric.lower() == PRECISION:
                metric_results[f"{PRECISION}@{k}"] = 0.0

    for k in cutoffs:
        for per_metric in metrics:
            if per_metric.lower() == NDCG:
                metric_results[f"{NDCG}@{k}"] = round(scores[f"{NDCG}@{k}"], 5)
            elif per_metric.lower() == MAP:
                metric_results[f"{MAP}@{k}"] = round(scores[f"{MAP}@{k}"], 5)
            elif per_metric.lower() == RECALL:
                metric_results[f"{RECALL}@{k}"] = round(scores[f"{RECALL}@{k}"], 5)
            elif per_metric.lower() == PRECISION:
                metric_results[f"{PRECISION}@{k}"] = round(scores[f"{PRECISION}@{k}"], 5)

    return metric_results
