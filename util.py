import numpy as np
import torch
import numbers
import math


def merge_stat(src, dest):
    for k, v in src.items():
        if not k in dest:
            dest[k] = v
        elif isinstance(v, numbers.Number):
            dest[k] = dest.get(k, 0) + v
        elif isinstance(v, np.ndarray): # for rewards in case of multi-agent
            dest[k] = dest.get(k, 0) + v
        else:
            if isinstance(dest[k], list) and isinstance(v, list):
                dest[k].extend(v)
            elif isinstance(dest[k], list):
                dest[k].append(v)
            else:
                dest[k] = [dest[k], v]

def normal_entropy(std):
    var = std.pow(2)
    entropy = 0.5 + 0.5 * torch.log(2 * var * math.pi)
    return entropy.sum(1, keepdim=True)

def normal_log_density(x, mean, log_std, std):
    var = std.pow(2)
    log_density = -(x - mean).pow(2) / (2 * var) - 0.5 * math.log(2 * math.pi) - log_std
    return log_density.sum(1, keepdim=True)

def multinomials_log_density(actions, log_probs):
    return log_probs.gather(-1, actions.long())

def select_action(args, action_out, status='train'):
    if args.continuous:
        action_mean, _, action_std = action_out
        if status == 'train':
            action = torch.normal(action_mean, action_std)
        elif status == 'test':
            action = action_mean
        return action.detach()
    else:
        log_p_a = action_out
        p_a = [[z.exp() for z in x] for x in log_p_a]
        if status == 'train':
            ret = torch.stack([torch.stack([torch.multinomial(x, 1).detach() for x in p]) for p in p_a])
        elif status == 'test':
            ret = torch.stack([torch.stack([torch.argmax(x, dim=-1).detach().unsqueeze(0) for x in p]) for p in p_a])
        return ret

def translate_action(args, action):
    if args.action_num > 1:
        action_tensor = torch.zeros(tuple(action.size()[:-1])+(args.action_num,))
        if torch.cuda.is_available() and args.cuda:
            action_tensor = action_tensor.cuda()
        action_tensor.scatter_(-1, action, 1)
        # environment takes discrete action
        actual = [action_tensor[:, i, :].squeeze().cpu().data.numpy() for i in range(action_tensor.size(1))]
        action = np.array(actual)
        return action, actual
    else:
        if args.continuous:
            action = action.data[0].numpy()
            cp_action = action.copy()
            # clip and scale action to correct range
            for i in range(len(action)):
                low = env.action_space.low[i]
                high = env.action_space.high[i]
                cp_action[i] = cp_action[i] * args.action_scale
                cp_action[i] = max(-1.0, min(cp_action[i], 1.0))
                cp_action[i] = 0.5 * (cp_action[i] + 1.0) * (high - low) + low
            return action, cp_action
        else:
            actual = np.zeros(len(action))
            for i in range(len(action)):
                low = env.action_space.low[i]
                high = env.action_space.high[i]
                actual[i] = action[i].data.squeeze()[0] * (high - low) / (args.naction_heads[i] - 1) + low
            action = [x.squeeze().data[0] for x in action]
            return action, actual

def prep_obs(state=[]):
    state = np.array(state)
    if len(state.shape) == 2:
        state = np.stack(state, axis=0)
    elif len(state.shape) == 4:
        state = np.concatenate(state, axis=0)
    else:
        raise RuntimeError('The shape of the observation is incorrect.')
    return torch.tensor(state).float()

def cuda_wrapper(tensor, cuda):
    if isinstance(tensor, torch.Tensor):
        if cuda:
            return tensor.cuda()
        else:
            return tensor
    else:
        raise RuntimeError('Please enter a pytorch tensor, now a {} is received.'.format(type(tensor)))

def batchnorm(self, batch):
    if isinstance(batch, torch.Tensor):
        batch_norm = (batch - batch.mean()) / batch.std()
        return batch_norm
    else:
        raise RuntimeError('Please enter a pytorch tensor, now a {} is received.'.format(type(batch)))
