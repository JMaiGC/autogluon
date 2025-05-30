from __future__ import annotations

from abc import abstractmethod

import numpy as np
import pandas as pd
from sklearn.preprocessing import OneHotEncoder

from autogluon.common.utils.try_import import try_import_imodels
from autogluon.core.models import AbstractModel


class _IModelsModel(AbstractModel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._feature_generator = None
        self._ohe = None
        self._ohe_columns = None
        self._categorical_featnames = None
        self._other_featnames = None

    @abstractmethod
    def get_model(self):
        return NotImplemented

    def get_info(self):
        info = super().get_info()
        info["complexity"] = self.model.complexity_
        return info

    def _preprocess(self, X: pd.DataFrame, is_train=False, **kwargs) -> pd.DataFrame:
        X = super()._preprocess(X, **kwargs)
        if is_train:
            self._categorical_featnames = self._feature_metadata.get_features(valid_raw_types=["category"])
            self._other_featnames = self._feature_metadata.get_features(invalid_raw_types=["category"])
            if self._categorical_featnames:
                self._ohe = OneHotEncoder(dtype=np.uint8, handle_unknown="ignore")
                self._ohe.fit(X=X[self._categorical_featnames])
                self._ohe_columns = self._ohe.get_feature_names_out()
            else:
                self._ohe = None  # otherwise no model is fitted when there are not self._categorical_featnames

        if self._ohe is not None:
            X_index = X.index
            X_ohe = self._ohe.transform(X[self._categorical_featnames])
            X_ohe = pd.DataFrame.sparse.from_spmatrix(X_ohe, columns=self._ohe_columns, index=X_index)
            if self._other_featnames:
                X = pd.concat([X[self._other_featnames], X_ohe], axis=1)
            else:
                X = X_ohe

        return X.fillna(0)

    def _fit(self, X: pd.DataFrame, y: pd.Series, **kwargs):  # training data  # training labels
        model_cls = self.get_model()
        X = self.preprocess(X, is_train=True)
        params = self._get_model_params()
        self.model = model_cls(**params)
        self.model.fit(X, y, feature_names=X.columns.values.tolist())

    def _set_default_params(self):
        default_params = {
            "random_state": 0,
        }
        for param, val in default_params.items():
            self._set_default_param_value(param, val)

    @classmethod
    def supported_problem_types(cls) -> list[str] | None:
        return ["binary", "multiclass", "regression"]

    def _get_default_auxiliary_params(self) -> dict:
        default_auxiliary_params = super()._get_default_auxiliary_params()
        extra_auxiliary_params = dict(
            get_features_kwargs=dict(
                valid_raw_types=["int", "float", "category"],
            ),
        )
        default_auxiliary_params.update(extra_auxiliary_params)
        return default_auxiliary_params


class RuleFitModel(_IModelsModel):
    ag_key = "IM_RULEFIT"
    ag_name = "RuleFit"

    def get_model(self):
        try_import_imodels()
        from imodels import RuleFitClassifier, RuleFitRegressor

        if self.problem_type in ["regression", "softclass"]:
            return RuleFitRegressor
        else:
            return RuleFitClassifier


class GreedyTreeModel(_IModelsModel):
    ag_key = "IM_GREEDYTREE"
    ag_name = "GreedyTree"

    def get_model(self):
        try_import_imodels()
        from imodels import GreedyTreeClassifier
        from sklearn.tree import DecisionTreeRegressor

        if self.problem_type in ["regression", "softclass"]:
            return DecisionTreeRegressor
        else:
            return GreedyTreeClassifier


class BoostedRulesModel(_IModelsModel):
    ag_key = "IM_BOOSTEDRULES"
    ag_name = "BoostedRules"

    def get_model(self):
        try_import_imodels()
        from imodels import BoostedRulesClassifier

        if self.problem_type in ["binary"]:
            return BoostedRulesClassifier
        else:
            raise Exception("Boosted Rule Set only supports binary classification!")


class HSTreeModel(_IModelsModel):
    ag_key = "IM_HSTREE"
    ag_name = "HierarchicalShrinkageTree"

    def get_model(self):
        try_import_imodels()
        from imodels import HSTreeClassifierCV, HSTreeRegressorCV

        if self.problem_type in ["regression", "softclass"]:
            return HSTreeRegressorCV
        else:
            return HSTreeClassifierCV


class FigsModel(_IModelsModel):
    ag_key = "IM_FIGS"
    ag_name = "Figs"

    def get_model(self):
        try_import_imodels()
        from imodels import FIGSClassifier, FIGSRegressor

        if self.problem_type in ["regression", "softclass"]:
            return FIGSRegressor
        else:
            return FIGSClassifier
