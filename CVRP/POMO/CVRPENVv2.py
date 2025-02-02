
from dataclasses import dataclass
import torch

from CVRProblemDefv2 import get_random_problems, augment_xy_data_by_8_fold

@dataclass
class Reset_State:
    depot_xy: torch.Tensor = None
    # shape: (batch, 1, 2)
    node_xy: torch.Tensor = None
    # shape: (batch, problem, 2)
    node_demand: torch.Tensor = None
    # shape: (batch, problem)


@dataclass
class Step_State:
    BATCH_IDX: torch.Tensor = None
    POMO_IDX: torch.Tensor = None
    # shape: (batch, pomo)
    selected_count: int = None
    current_node: torch.Tensor = None
    # shape: (batch, pomo)
    ninf_mask: torch.Tensor = None
    # shape: (batch, pomo, problem+1)
    finished: torch.Tensor = None
    # shape: (batch, pomo)

@dataclass
class Mask_State:
    mask_Matrix = None
    # shape : (batch,prob,prob)
    Matrix_ninf = None
    # shape : (batch,prob,prob)

class CVRPEnv2:
    def __init__(self, **env_params):

        # Const @INIT
        ####################################
        self.env_params = env_params
        self.problem_size = env_params['problem_size']
        self.pomo_size = env_params['pomo_size']
        # Const @Load_Problem
        ####################################
        self.batch_size = None
        self.BATCH_IDX = None
        self.POMO_IDX = None
        # IDX.shape: (batch, pomo)
        self.depot_node_xy = None
        # shape: (batch, problem+1, 2)
        self.depot_node_demand = None
        # shape: (batch, problem+1)
        self.time_ = None
        self.Matrix_index = None
        self.selected_matrix = None
        self.accum_mat = None
        self.shape = None

        # Dynamic-1
        ####################################
        self.selected_count = None
        self.current_node = None
        # shape: (batch, pomo)
        self.selected_node_list = None
        # shape: (batch, pomo, 0~)

        # Dynamic-2
        ####################################
        self.at_the_depot = None
        # shape: (batch, pomo)
        self.load = None
        # shape: (batch, pomo)
        self.visited_ninf_flag = None
        # shape: (batch, pomo, problem+1)
        self.ninf_mask = None
        # shape: (batch, pomo, problem+1)
        self.finished = None
        # shape: (batch, pomo)
        self.mask_Matrix = None
        # shape : (batch,prob,prob)
        self.matrix_ninf = None

        # states to return
        ####################################
        self.reset_state = Reset_State()
        self.step_state = Step_State()
        self.mask_state = Mask_State()


    def load_problems(self, batch_size, aug_factor=1):
        self.batch_size = batch_size

        # day's range 20190101 ~ 20191230
        depot_xy, node_xy, node_demand = get_random_problems(batch_size, self.problem_size)
        # self.shape = self.demand.size(1)
        # depot_xy = torch.zeros((batch_size,1,2))
        if aug_factor > 1:
            if aug_factor == 8:
                self.batch_size = self.batch_size * 8
                depot_xy = augment_xy_data_by_8_fold(depot_xy)
                node_xy = augment_xy_data_by_8_fold(node_xy)
                node_demand = self.node_demand.repeat(8, 1)
            else:
                raise NotImplementedError

        self.depot_node_xy = torch.cat((depot_xy, node_xy), dim=1) # 원래
        # shape: (batch, problem+1, 2)
        # 일반 조건
        self.time_ = node_xy[:,:,0]*60 + node_xy[:,:,1]
        # x축 조건
        # self.time_ = node_xy[:,:,0] + node_xy[:,:,1]

        condition_1 = torch.abs(self.time_[:,None,:].transpose(1,2) - self.time_[:,None,:]) < node_demand[:,None,:].expand(batch_size, self.problem_size, self.problem_size).transpose(1, 2)
        condition_2 = torch.abs(self.time_[:,None,:].transpose(1,2) - self.time_[:,None,:]) > 500
        self.mask_Matrix = condition_1 + condition_2
        # self.mask_Matrix = torch.abs(self.time_[:, None, :].transpose(1, 2) - self.time_[:, None, :]) < 60
        # self.mask_Matrix = (self.time_[:, None, :].transpose(1, 2) - self.time_[:, None, :]) < 60
        # shape: (batch, pomo, problemsize)
        self._ninf = torch.zeros(size=(self.batch_size, self.problem_size, self.problem_size))
        self._ninf[self.mask_Matrix] = float('-inf')
        depot_plus = torch.zeros(size=(self.batch_size, self.problem_size, 1))
        self.matrix_ninf = torch.cat((depot_plus, self._ninf), dim=2)
        zero_plus = torch.zeros(size=(self.batch_size, 1, self.problem_size + 1))
        self.matrix_ninf = torch.cat((zero_plus, self.matrix_ninf), dim=1)

        depot_demand = torch.zeros(size=(self.batch_size, 1))
        # shape: (batch, 1)
        self.depot_node_demand = torch.cat((depot_demand, node_demand), dim=1)
        # shape: (batch, problem+1)

        self.BATCH_IDX = torch.arange(self.batch_size)[:, None].expand(self.batch_size, self.problem_size)
        self.POMO_IDX = torch.arange(self.problem_size)[None, :].expand(self.batch_size,self.problem_size)

        self.reset_state.depot_xy = depot_xy
        self.reset_state.node_xy = node_xy #원래
        self.reset_state.node_demand = node_demand

        self.step_state.BATCH_IDX = self.BATCH_IDX
        self.step_state.POMO_IDX = self.POMO_IDX

        self.mask_state.mask_Matrix = self.mask_Matrix
        self.mask_state.Matrix_ninf = self.matrix_ninf

    def reset(self):
        self.selected_count = 0
        self.current_node = None
        # shape: (batch, pomo)

        self.selected_node_list = torch.zeros((self.batch_size, self.problem_size, 0), dtype=torch.long)
        # shape: (batch, pomo, 0~)

        self.at_the_depot = torch.ones(size=(self.batch_size, self.problem_size), dtype=torch.bool)
        # shape: (batch, pomo)
        self.load = torch.ones(size=(self.batch_size, self.problem_size))
        # shape: (batch, pomo)
        self.visited_ninf_flag = torch.zeros(size=(self.batch_size, self.problem_size, self.problem_size+1))
        # shape: (batch, pomo, problem+1)
        self.ninf_mask = torch.zeros(size=(self.batch_size, self.problem_size, self.problem_size+1))
        # shape: (batch, pomo, problem+1)
        self.finished = torch.zeros(size=(self.batch_size, self.problem_size), dtype=torch.bool)
        # shape: (batch, pomo)
        self.accum_mat = torch.zeros(size=(self.batch_size, self.problem_size, self.problem_size+1))
        # shape: (batch, pomo, problem+1)

        reward = None
        done = False
        return self.reset_state, reward, done

    def pre_step(self):
        self.step_state.selected_count = self.selected_count
        self.step_state.current_node = self.current_node
        self.step_state.ninf_mask = self.ninf_mask
        self.step_state.finished = self.finished

        reward = None
        done = False
        return self.step_state, reward, done

    def step(self, selected):
        # selected.shape: (batch, pomo)

        # Dynamic-1
        ####################################
        self.selected_count += 1
        self.current_node = selected
        # shape: (batch, pomo)
        self.selected_node_list = torch.cat((self.selected_node_list, self.current_node[:, :, None]), dim=2)
        # shape: (batch, pomo, 0~)

        # Dynamic-2batch_size, self.problem_size
        ####################################
        self.at_the_depot = (selected == 0)

        demand_list = self.depot_node_demand[:, None, :].expand(self.batch_size, self.problem_size, -1)
        # shape: (batch, pomo, problem+1)
        gathering_index = selected[:, :, None]
        # shape: (batch, pomo, 1)

        self.Matrix_index = gathering_index.expand(self.batch_size,self.problem_size,self.problem_size+1)
        # shape:  (batch, pomo,problem_size)

        selected_demand = demand_list.gather(dim=2, index=gathering_index).squeeze(dim=2)
        # shape: (batch, pomo)
        self.load -= selected_demand
        self.load[self.at_the_depot] = 1 # refill loaded at the depot

        self.visited_ninf_flag[self.BATCH_IDX, self.POMO_IDX, selected] = float('-inf')
        # shape: (batch, pomo, problem+1)
        self.visited_ninf_flag[:, :, 0][~self.at_the_depot] = 0  # depot is considered unvisited, unless you are AT the depot

        Matrix_list = self.mask_state.Matrix_ninf
        self.selected_matrix = Matrix_list.gather(dim=1, index=self.Matrix_index)
        # depot_plus = torch.zeros(size=(self.batch_size, self.pomo_size, 1))
        # matrix_inif = torch.cat((selected_matrix, depot_plus), dim=2)

        self.ninf_mask = self.visited_ninf_flag.clone()
        round_error_epsilon = 0.00001
        demand_too_large = self.load[:, :, None] + round_error_epsilon < demand_list
        # shape: (batch, pomo, problem+1)
        self.ninf_mask[demand_too_large] = float('-inf')

        self.accum_mat = self.accum_mat + self.selected_matrix
        self.accum_mat[self.at_the_depot] = 0
        self.ninf_mask += self.accum_mat

        # shape : (batch, pomo, problemsize)

        newly_finished = (self.visited_ninf_flag == float('-inf')).all(dim=2)
        # shape: (batch, pomo)
        self.finished = self.finished + newly_finished
        # shape: (batch, pomo)

        # do not mask depot for finished episode.
        self.ninf_mask[:, :, 0][self.finished] = 0

        self.step_state.selected_count = self.selected_count
        self.step_state.current_node = self.current_node
        self.step_state.ninf_mask = self.ninf_mask
        self.step_state.finished = self.finished

        # returning values
        done = self.finished.all()
        if done:
            reward = -self._get_travel_distance()  # note the minus sign!
        else:
            reward = None

        return self.step_state, reward, done

    def _get_travel_distance(self):
        gathering_index = self.selected_node_list[:, :, :, None].expand(-1, -1, -1, 2)
        # shape: (batch, pomo, selected_list_length, 2)
        all_xy = self.depot_node_xy[:, None, :, :].expand(-1, self.problem_size, -1, -1)
        # all_xy = self.depot_node_xy[:, None, :, :].expand(-1, self.shape, -1, -1)
        # shape: (batch, pomo, problem+1, 2)

        ordered_seq = all_xy.gather(dim=2, index=gathering_index)
        # shape: (batch, pomo, selected_list_length, 2)

        rolled_seq = ordered_seq.roll(dims=2, shifts=-1)
        segment_lengths = ((ordered_seq-rolled_seq)**2).sum(3).sqrt()
        # shape: (batch, pomo, selected_list_length)

        travel_distances = segment_lengths.sum(2)
        # shape: (batch, pomo)
        return travel_distances

