
import torch
import numpy as np
import os
import random

def get_random_problems(batch_size, problem_size):

    depot_xy = torch.rand(size=(batch_size, 1, 2))
    # depot_xy = torch.rand(1,24, size=(batch_size, 1, 2))/float(24)
    # shape: (batch, 1, 2)

    # node_xy = torch.rand(size=(batch_size, problem_size, 2))
    node_x = torch.randint(1, 25, size=(batch_size, problem_size,1)) #/ float(4*10*24)
    node_y = torch.randint(1, 60, size=(batch_size, problem_size,1)) #/ float(60)

    # node_x = torch.zeros(size=(batch_size, problem_size, 1))  # / float(4*10*24)
    # node_y = torch.randint(1, 1440, size=(batch_size, problem_size, 1))  / float(1440)

    node_xy = torch.cat((node_x,node_y),dim = 2)
    # shape: (batch, problem, 2)

    if problem_size == 20:
        demand_scaler = 30
    elif problem_size == 50:
        demand_scaler = 40
    elif problem_size == 100:
        demand_scaler = 50
    else:
        raise NotImplementedError
    demand_scaler = 300
    node_demand = torch.randint(40, 60, size=(batch_size, problem_size)) / float(demand_scaler)
    # shape: (batch, problem)

    return depot_xy, node_xy, node_demand


def augment_xy_data_by_8_fold(xy_data):
    # xy_data.shape: (batch, N, 2)

    x = xy_data[:, :, [0]]
    y = xy_data[:, :, [1]]
    # x,y shape: (batch, N, 1)

    dat1 = torch.cat((x, y), dim=2)
    dat2 = torch.cat((1 - x, y), dim=2)
    dat3 = torch.cat((x, 1 - y), dim=2)
    dat4 = torch.cat((1 - x, 1 - y), dim=2)
    dat5 = torch.cat((y, x), dim=2)
    dat6 = torch.cat((1 - y, x), dim=2)
    dat7 = torch.cat((y, 1 - x), dim=2)
    dat8 = torch.cat((1 - y, 1 - x), dim=2)

    aug_xy_data = torch.cat((dat1, dat2, dat3, dat4, dat5, dat6, dat7, dat8), dim=0)
    # shape: (8*batch, N, 2)

    return aug_xy_data
