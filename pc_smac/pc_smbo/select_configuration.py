
import math
import itertools
import logging
import typing
import random

import numpy as np

from smac.smbo.acquisition import AbstractAcquisitionFunction
from smac.epm.rf_with_instances import RandomForestWithInstances
from smac.smbo.local_search import LocalSearch
from smac.scenario.scenario import Scenario
from smac.runhistory.runhistory import RunHistory
from smac.stats.stats import Stats

from ConfigSpace.configuration_space import ConfigurationSpace, Configuration

import ConfigSpace.util


class SelectConfiguration(object):

    def __init__(self,
                 scenario: Scenario,
                 stats: Stats,
                 runhistory: RunHistory,
                 model: RandomForestWithInstances,
                 acquisition_func: AbstractAcquisitionFunction,
                 acq_optimizer: LocalSearch,
                 rng: np.random.RandomState):
        self.logger = logging.getLogger("Select Configuration")

        self.config_space = scenario.cs
        self.stats = stats
        self.runhistory = runhistory
        self.model = model
        self.acquisition_func = acquisition_func
        self.acq_optimizer = acq_optimizer
        self.rng = rng

    def run(self, X, Y,
                    incumbent,
                    num_configurations_by_random_search_sorted: int = 1000,
                    num_configurations_by_local_search: int = None,
                    random_leaf_size = 1):

        """Choose next candidate solution with Bayesian optimization.

        Parameters
        ----------
        X : (N, D) numpy array
            Each row contains a configuration and one set of
            instance features.
        Y : (N, O) numpy array
            The function values for each configuration instance pair.
        num_configurations_by_random_search_sorted: int
             number of configurations optimized by random search
        num_configurations_by_local_search: int
            number of configurations optimized with local search
            if None, we use min(10, 1 + 0.5 x the number of configurations on exp average in intensify calls)

        Returns
        -------
        list
            List of 2020 suggested configurations to evaluate.
        """
        self.model.train(X, Y)

        if self.runhistory.empty():
            incumbent_value = 0.0
        elif incumbent is None:
            # TODO try to calculate an incumbent from the runhistory!
            incumbent_value = 0.0
        else:
            incumbent_value = self.runhistory.get_cost(incumbent)

        self.acquisition_func.update(model=self.model, eta=incumbent_value)

        # Get configurations sorted by EI
        next_configs_by_random_search_sorted = \
            self._get_next_by_random_search(
                num_configurations_by_random_search_sorted, _sorted=True)

        if num_configurations_by_local_search is None:
            if self.stats._ema_n_configs_per_intensifiy > 0:
                num_configurations_by_local_search = min(
                    10, math.ceil(0.5 * self.stats._ema_n_configs_per_intensifiy) + 1)
            else:
                num_configurations_by_local_search = 10

        # initiate local search with best configurations from previous runs
        configs_previous_runs = self.runhistory.get_all_configs()
        configs_previous_runs_sorted = self._sort_configs_by_acq_value(configs_previous_runs)
        num_configs_local_search = min(len(configs_previous_runs_sorted), num_configurations_by_local_search)
        next_configs_by_local_search = \
            self._get_next_by_local_search(
                list(map(lambda x: x[1],
                         configs_previous_runs_sorted[:num_configs_local_search])))

        next_configs_by_acq_value = next_configs_by_random_search_sorted + \
                                    next_configs_by_local_search
        next_configs_by_acq_value.sort(reverse=True, key=lambda x: x[0])
        self.logger.debug(
            "First 10 acq func (origin) values of selected configurations: %s" %
            (str([[_[0], _[1].origin] for _ in next_configs_by_acq_value[:10]])))
        next_configs_by_acq_value = [_[1] for _ in next_configs_by_acq_value]

        # Remove dummy acquisition function value
        next_configs_by_random_search = [x[1] for x in
                                         self._get_next_by_random_search_batch(
                                             num_points=len(next_configs_by_acq_value),
                                             leaf_size=random_leaf_size)]
                                             #num_points=num_configurations_by_local_search + num_configurations_by_random_search_sorted)]

        challengers = list(itertools.chain(*zip(next_configs_by_acq_value,
                                                next_configs_by_random_search)))
        return challengers

    def _get_next_by_random_search(self, num_points=1000, _sorted=False):
        """Get candidate solutions via local search.

        Parameters
        ----------
        num_points : int, optional (default=10)
            Number of local searches and returned values.

        _sorted : bool, optional (default=True)
            Whether to sort the candidate solutions by acquisition function
            value.

        Returns
        -------
        list : (acquisition value, Candidate solutions)
        """

        rand_configs = self.config_space.sample_configuration(size=num_points)
        if _sorted:
            for i in range(len(rand_configs)):
                rand_configs[i].origin = 'Random Search (Sorted)'
            return self._sort_configs_by_acq_value(rand_configs)
        else:
            for i in range(len(rand_configs)):
                rand_configs[i].origin = 'Random Search'
            return [(0, rand_configs[i]) for i in range(len(rand_configs))]

    def _get_next_by_random_search_batch(self, num_points=1000, leaf_size=4, _sorted=False):
        """Get candidate solutions via local search.

        Parameters
        ----------
        num_points : int, optional (default=10)
            Number of local searches and returned values.

        _sorted : bool, optional (default=True)
            Whether to sort the candidate solutions by acquisition function
            value.

        Returns
        -------
        list : (acquisition value, Candidate solutions)
        """
        rand_configs = []
        for i in range(0, num_points):
            start_config = self.config_space.sample_configuration()
            batch_of_configs = [start_config]
            i = 1
            while i < leaf_size:
                try:
                    next_config = self.config_space.sample_configuration()
                    # TODO hack for now to combine preprocessing part of one configuration with classification part of all the others
                    next_config_combined = self._combine_configurations(start_config, next_config)
                    batch_of_configs.append(next_config_combined)
                    i += 1
                except ValueError as v:
                    if i > 10:
                        break

            rand_configs.extend(batch_of_configs)
        if _sorted:
            for i in range(len(rand_configs)):
                rand_configs[i].origin = 'Random Search (Sorted)'
            return self._sort_configs_by_acq_value(rand_configs)
        else:
            for i in range(len(rand_configs)):
                rand_configs[i].origin = 'Random Search (Batch)'
            return [(0, rand_configs[i]) for i in range(len(rand_configs))]


    def _get_next_by_local_search(self, init_points=typing.List[Configuration]):
        """Get candidate solutions via local search.

        In case acquisition function values tie, these will be broken randomly.

        Parameters
        ----------
        init_points : typing.List[Configuration]
            initial starting configurations for local search

        Returns
        -------
        list : (acquisition value, Candidate solutions),
               ordered by their acquisition function value
        """
        configs_acq = []

        # Start N local search from different random start points
        for start_point in init_points:
            configuration, acq_val = self._optimize_acq(start_point)

            configuration.origin = 'Local Search'
            configs_acq.append((acq_val[0], configuration))

        # shuffle for random tie-break
        random.shuffle(configs_acq, self.rng.rand)

        # sort according to acq value
        # and return n best configurations
        configs_acq.sort(reverse=True, key=lambda x: x[0])

        return configs_acq

    def _optimize_acq(self, start_point):
        return self.acq_optimizer.maximize(start_point)

    def _sort_configs_by_acq_value(self, configs):

        imputed_configs = map(ConfigSpace.util.impute_inactive_values,
                              configs)
        imputed_configs = [x.get_array()
                           for x in imputed_configs]
        imputed_configs = np.array(imputed_configs,
                                   dtype=np.float64)
        acq_values = self.acquisition_func(imputed_configs)

        # From here
        # http://stackoverflow.com/questions/20197990/how-to-make-argsort-result-to-be-random-between-equal-values
        random = self.rng.rand(len(acq_values))
        # Last column is primary sort key!
        indices = np.lexsort((random.flatten(), acq_values.flatten()))

        # Cannot use zip here because the indices array cannot index the
        # rand_configs list, because the second is a pure python list
        return [(acq_values[ind][0], configs[ind])
                for ind in indices[::-1]]



class CachedSelectConfiguration(SelectConfiguration):

    def __init__(self,
                 scenario: Scenario,
                 stats: Stats,
                 runhistory: RunHistory,
                 model: RandomForestWithInstances,
                 acquisition_func: AbstractAcquisitionFunction,
                 acq_optimizer: LocalSearch,
                 rng: np.random.RandomState,
                 constant_pipeline_steps,
                 variable_pipeline_steps):
        super(CachedSelectConfiguration, self).__init__(scenario=scenario,
                                                        stats=stats,
                                                        runhistory=runhistory,
                                                        model=model,
                                                        acquisition_func=acquisition_func,
                                                        acq_optimizer=acq_optimizer,
                                                        rng=rng)

        self.constant_pipeline_steps = constant_pipeline_steps
        self.variable_pipeline_steps = variable_pipeline_steps

    def run(self, X, Y,
            incumbent,
            num_configurations_by_random_search_sorted: int = 1000,
            num_configurations_by_local_search: int = None,
            random_leaf_size = 1):
        """Choose next candidate solution with Bayesian optimization.

        Parameters
        ----------
        X : (N, D) numpy array
            Each row contains a configuration and one set of
            instance features.
        Y : (N, O) numpy array
            The function values for each configuration instance pair.
        num_configurations_by_random_search_sorted: int
             number of configurations optimized by random search
        num_configurations_by_local_search: int
            number of configurations optimized with local search
            if None, we use min(10, 1 + 0.5 x the number of configurations on exp average in intensify calls)

        Returns
        -------
        list
            List of 2020 suggested configurations to evaluate.
        """
        self.model.train(X, Y)

        if self.runhistory.empty():
            incumbent_value = 0.0
        elif incumbent is None:
            # TODO try to calculate an incumbent from the runhistory!
            incumbent_value = 0.0
        else:
            incumbent_value = self.runhistory.get_cost(incumbent)

        self.acquisition_func.update(model=self.model, eta=incumbent_value)

        # Compute preprocessor using marginalization

        # Get configurations sorted by EI
        next_configs_by_random_search_sorted = \
            self._get_next_by_random_search(
                num_configurations_by_random_search_sorted, _sorted=True)

        if num_configurations_by_local_search is None:
            if self.stats._ema_n_configs_per_intensifiy > 0:
                num_configurations_by_local_search = min(
                    10, math.ceil(0.5 * self.stats._ema_n_configs_per_intensifiy) + 1)
            else:
                num_configurations_by_local_search = 10

        # initiate local search with best configurations from previous runs
        configs_previous_runs = self.runhistory.get_all_configs()
        configs_previous_runs_sorted = self._sort_configs_by_acq_value(configs_previous_runs)
        num_configs_local_search = min(len(configs_previous_runs_sorted), num_configurations_by_local_search)
        next_configs_by_local_search = \
            self._get_next_by_local_search(
                list(map(lambda x: x[1],
                         configs_previous_runs_sorted[:num_configs_local_search])))

        next_configs_by_acq_value = next_configs_by_random_search_sorted + \
                                    next_configs_by_local_search
        next_configs_by_acq_value.sort(reverse=True, key=lambda x: x[0])
        self.logger.debug(
            "First 10 acq func (origin) values of selected configurations: %s" %
            (str([[_[0], _[1].origin] for _ in next_configs_by_acq_value[:10]])))
        next_configs_by_acq_value = [_[1] for _ in next_configs_by_acq_value]

        # Remove dummy acquisition function value
        next_configs_by_random_search = [x[1] for x in
                                         self._get_next_by_random_search_batch(
                                             num_points=len(next_configs_by_acq_value),
                                            leaf_size=random_leaf_size)]

        iter_next_configs_by_acq_value = iter(next_configs_by_acq_value)
        iter_next_configs_by_random_search = iter(next_configs_by_random_search)
        challengers = [next(iter_next_configs_by_acq_value) if i % (random_leaf_size+1) == 0 else next(iter_next_configs_by_random_search)
                       for i in range(0, len(next_configs_by_acq_value) + len(next_configs_by_random_search))]
        return challengers

    def _combine_configurations(self, start_config, new_config):
        constant_values = self._get_values(start_config.get_dictionary(), self.constant_pipeline_steps)
        new_config_values = {}
        new_config_values.update(constant_values)

        variable_values = self._get_values(new_config.get_dictionary(), self.variable_pipeline_steps)
        new_config_values.update(variable_values)

        return Configuration(configuration_space=self.config_space,
                             values=new_config_values)

    def _get_values(self, config_dict, pipeline_steps):
        value_dict = {}
        for step_name in pipeline_steps:
            for hp_name in config_dict:
                splt_hp_name = hp_name.split(":")
                if splt_hp_name[0] == step_name:
                    value_dict[hp_name] = config_dict[hp_name]
        return value_dict

    # def _optimize_acq(self, start_point):
    #     return self.acq_optimizer.maximize(start_point, self.runhistory.get_cached_configurations())

    def _sort_configs_by_acq_value(self, configs):
        caching_discounts = self._compute_caching_discounts(configs, self.runhistory.get_cached_configurations())

        imputed_configs = map(ConfigSpace.util.impute_inactive_values,
                              configs)
        imputed_configs = [x.get_array()
                           for x in imputed_configs]
        imputed_configs = np.array(imputed_configs,
                                   dtype=np.float64)
        acq_values = self.acquisition_func(imputed_configs, caching_discounts)

        # From here
        # http://stackoverflow.com/questions/20197990/how-to-make-argsort-result-to-be-random-between-equal-values
        random = self.rng.rand(len(acq_values))
        # Last column is primary sort key!
        indices = np.lexsort((random.flatten(), acq_values.flatten()))

        # Cannot use zip here because the indices array cannot index the
        # rand_configs list, because the second is a pure python list
        return [(acq_values[ind][0], configs[ind])
                for ind in indices[::-1]]

    # TODO the compute caching discounts methods are located in two places: in the select configuration procedure and also in the local search
    def _compute_caching_discounts(self, configs, cached_configs):
        runtime_discounts = []
        for config in configs:
            discount = 0
            for cached_config in cached_configs:
                discount += self._caching_reduction(config, cached_config)
            runtime_discounts.append(discount)
        return runtime_discounts

    def _caching_reduction(self, config, cached_config):
        '''

        Parameters
        ----------
        config:         the new configuration
        cached_config:  the cached configuration

        Returns
        -------
            The runtime discount for this configuration, given the cached configuration if there is one, otherwise 0
        '''
        r = [key for key in cached_config[0].keys() if config[key] != cached_config[0][key]]
        # print("_caching_reduction: {}".format(r))
        if r == []:
            return cached_config[1]
        return 0
