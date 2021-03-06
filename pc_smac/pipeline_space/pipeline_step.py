from pc_smac.pc_smac.pipeline_space.classification_nodes.adaboost import AdaBoostNode
from pc_smac.pc_smac.pipeline_space.classification_nodes.bernoulli_nb import BernoulliNBNode
from pc_smac.pc_smac.pipeline_space.classification_nodes.decision_tree import DecisionTreeNode
from pc_smac.pc_smac.pipeline_space.classification_nodes.extra_trees import ExtraTreesClassifierNode
from pc_smac.pc_smac.pipeline_space.classification_nodes.gaussian_nb import GaussianNBNode
from pc_smac.pc_smac.pipeline_space.classification_nodes.gradient_boosting import GradientBoostingNode
from pc_smac.pc_smac.pipeline_space.classification_nodes.k_nearest_neighbors import KNearestNeighborsNode
from pc_smac.pc_smac.pipeline_space.classification_nodes.lda import LDANode
from pc_smac.pc_smac.pipeline_space.classification_nodes.liblinear_svc import LibLinear_SVC_Node
from pc_smac.pc_smac.pipeline_space.classification_nodes.libsvm_svc import LibSVM_SVC_Node
from pc_smac.pc_smac.pipeline_space.classification_nodes.multinomial_nb import MultinomialNBNode
from pc_smac.pc_smac.pipeline_space.classification_nodes.passive_aggresive import PassiveAggresiveNode
from pc_smac.pc_smac.pipeline_space.classification_nodes.qda import QDANode
from pc_smac.pc_smac.pipeline_space.classification_nodes.random_forest import RandomForestNode
from pc_smac.pc_smac.pipeline_space.classification_nodes.sgd import SGDNode
from pc_smac.pc_smac.pipeline_space.data_preprocessing_nodes.balancing_node import BalancingNode
from pc_smac.pc_smac.pipeline_space.data_preprocessing_nodes.imputation import ImputationNode
from pc_smac.pc_smac.pipeline_space.data_preprocessing_nodes.one_hot_encoding import OneHotEncodeingNode
from pc_smac.pc_smac.pipeline_space.data_preprocessing_nodes.rescaling.standard_scaler import StandardScalerNode
from pc_smac.pc_smac.pipeline_space.data_preprocessing_nodes.rescaling.minmax_scaler_node import MinMaxScalerNode
from pc_smac.pc_smac.pipeline_space.data_preprocessing_nodes.rescaling.no_rescaling_node import NoRescalingNode
from pc_smac.pc_smac.pipeline_space.data_preprocessing_nodes.rescaling.normalize_node import NormalizeNode
from pc_smac.pc_smac.pipeline_space.feature_preprocessing_nodes.extra_rand_trees import ExtraTreesNode
from pc_smac.pc_smac.pipeline_space.feature_preprocessing_nodes.fast_ica import FastICANode
from pc_smac.pc_smac.pipeline_space.feature_preprocessing_nodes.feature_agglomeration import FeatureAgglomerationNode
from pc_smac.pc_smac.pipeline_space.feature_preprocessing_nodes.kernel_pca import KernelPcaNode
from pc_smac.pc_smac.pipeline_space.feature_preprocessing_nodes.kitchen_sinks import RandomKitchenSinksNode
from pc_smac.pc_smac.pipeline_space.feature_preprocessing_nodes.linear_svm import LinearSVMNode
from pc_smac.pc_smac.pipeline_space.feature_preprocessing_nodes.no_preprocessing import NoPreprocessingNode
from pc_smac.pc_smac.pipeline_space.feature_preprocessing_nodes.nystroem_sampler import NystroemSamplerNode
from pc_smac.pc_smac.pipeline_space.feature_preprocessing_nodes.pca import PcaNode
from pc_smac.pc_smac.pipeline_space.feature_preprocessing_nodes.polynomial import PolynomialFeaturesNode
from pc_smac.pc_smac.pipeline_space.feature_preprocessing_nodes.random_trees_embedding import RandomTreesEmbeddingNode
from pc_smac.pc_smac.pipeline_space.feature_preprocessing_nodes.select_percentile import SelectPercentileNode
from pc_smac.pc_smac.pipeline_space.feature_preprocessing_nodes.select_rates import SelectRatesNode


class PipelineStep(object):

    def __init__(self, name, nodes, caching=False):
        self.step_name = name
        self.nodes = nodes
        self.caching_enabled = caching

    def get_name(self):
        return self.step_name

    def get_nodes(self):
        return self.nodes

    def get_nb_nodes(self):
        return len(self.nodes)

    def get_node_names(self):
        return [node.get_name() for node in self.get_nodes()]

    def is_caching_enabled(self):
        return self.caching_enabled

    def initialize_algorithm(self, node_name, hyperparameters):
        node = self._get_node(node_name)
        return node.initialize_algorithm(hyperparameters)

    def get_node(self, node_name):
        return self._get_node(node_name)

    #### Internal methods ####
    def _get_node(self, node_name):
        temp = [node for node in self.get_nodes() if node.get_name() == node_name]
        return temp[0]


class OneHotEncodingStep(PipelineStep):

    def __init__(self):
        name = "one_hot_encoder"
        nodes = [OneHotEncodeingNode()]
        super(OneHotEncodingStep, self).__init__(name, nodes, caching=False)

class ImputationStep(PipelineStep):

    def __init__(self):
        name = "imputation"
        nodes = [ImputationNode()]
        super(ImputationStep, self).__init__(name, nodes, caching=True)

class RescalingStep(PipelineStep):

    def __init__(self):
        name = "rescaling"
        nodes = [StandardScalerNode(),
                 MinMaxScalerNode(),
                 NoRescalingNode(),
                 NormalizeNode()]
        super(RescalingStep, self).__init__(name, nodes, caching=False)

class BalancingStep(PipelineStep):

    def __init__(self):
        name = "balancing"
        nodes = [BalancingNode()]
        super(BalancingStep, self).__init__(name, nodes, caching=False)

class PreprocessingStep(PipelineStep):

    def __init__(self):
        name = "feature_preprocessor"
        #nodes = [RandomTreesEmbeddingNode()]
        nodes = [ExtraTreesNode(),
                 FastICANode(),
                 FeatureAgglomerationNode(),
                 KernelPcaNode(),
                 RandomKitchenSinksNode(),
                 LinearSVMNode(),
                 NoPreprocessingNode(),
                 NystroemSamplerNode(),
                 PcaNode(),
                 PolynomialFeaturesNode(),
                 RandomTreesEmbeddingNode(),
                 SelectPercentileNode(),
                 SelectRatesNode()]
        super(PreprocessingStep, self).__init__(name, nodes, caching=True)

class ClassificationStep(PipelineStep):

    def __init__(self):
        name = "classifier"
        #nodes = [GradientBoostingNode()]
        nodes = [AdaBoostNode(),
                 BernoulliNBNode(),
                 DecisionTreeNode(),
                 ExtraTreesClassifierNode(),
                 GaussianNBNode(),
                 GradientBoostingNode(),
                 KNearestNeighborsNode(),
                 LDANode(),
                 LibLinear_SVC_Node(),
                 LibSVM_SVC_Node(),
                 MultinomialNBNode(),
                 PassiveAggresiveNode(),
                 QDANode(),
                 RandomForestNode(),
                 SGDNode()]
        super(ClassificationStep, self).__init__(name, nodes, caching=False)
