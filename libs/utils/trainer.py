import numpy as np

import torch
import torch.distributed as dist
from torch.utils.data.sampler import Sampler
from torch.optim.lr_scheduler import _LRScheduler


def all_reduce(tensor, op=dist.ReduceOp.SUM, world_size=1):
    tensor = tensor.clone()
    dist.all_reduce(tensor, op)
    tensor.div_(world_size)
    return tensor


class PolyLRScheduler(_LRScheduler):
    def __init__(self, optimizer, power, total_iter, last_iter=-1):
        super(PolyLRScheduler, self).__init__(optimizer, last_epoch=last_iter)
        self.power = power
        self.total_iter = total_iter

    def get_lr(self):
        # The 'last_epoch' variable is used as 'last_iter' indeed.
        last_iter = self.last_epoch
        rate = (1 - float(last_iter) / self.total_iter) ** self.power
        return [base_lr * rate for base_lr in self.base_lrs]


class DistributedSampler4Iter(Sampler):
    def __init__(self, dataset, total_iter, batch_size, world_size, rank,
                 last_iter=-1, rand_seed=666):
        super(DistributedSampler4Iter, self).__init__()
        assert rank < world_size

        self.dataset = dataset
        self.total_iter = total_iter
        self.batch_size = batch_size
        self.world_size = world_size
        self.rank = rank
        self.last_iter = last_iter
        self.rand_seed = rand_seed

        self.indices = self.gen_indices()
        self.called = False

    def __iter__(self):
        if not self.called:
            self.called = True
            return iter(self.indices[(self.last_iter+1)*self.batch_size:])
        else:
            raise RuntimeError('This sampler is not designed to be called
                                more than once!')

    def gen_indices(self):
        np.random.seed(self.rand_seed)

        own_size = self.total_iter * self.batch_size
        all_size = own_size * world_size

        indices = np.arange(len(self.dataset))
        num_repeat = (all_size - 1) // indices.shape[0] + 1
        indices = np.tile(indices, num_repeat)
        indices = indices[:all_size]

        np.random.shuffle(indices)
        beg = self.own_size * self.rank
        end = beg + self.own_size
        indices = indices[beg: end]

        return indices

