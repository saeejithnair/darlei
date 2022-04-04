

from distutils.command.config import config
import os
import hydra
from omegaconf import DictConfig, OmegaConf
from hydra.utils import to_absolute_path
import re
import time

import isaacgym
from isaacgymenvs.utils.reformat import omegaconf_to_dict, print_dict

from isaacgymenvs.utils.utils import set_np_formatting, set_seed

from rl_games.common import env_configurations, vecenv
from rl_games.torch_runner import Runner


from isaacgymenvs.learning import amp_continuous
from isaacgymenvs.learning import amp_players
from isaacgymenvs.learning import amp_models
from isaacgymenvs.learning import amp_network_builder
from darei.utils import file as fu

from darei.tools.rlgames_utils import RLGPUEnv, RLGPUAlgoObserver, get_rlgames_env_creator
## OmegaConf & Hydra Config

# # Resolvers used in hydra configs (see https://omegaconf.readthedocs.io/en/2.1_branch/usage.html#resolvers)
# OmegaConf.register_new_resolver('eq', lambda x, y: x.lower()==y.lower())
# OmegaConf.register_new_resolver('contains', lambda x, y: x.lower() in y.lower())
# OmegaConf.register_new_resolver('if', lambda pred, a, b: a if pred else b)
# # allows us to resolve default arguments which are copied in multiple places in the config. used primarily for
# # num_ensv
# OmegaConf.register_new_resolver('resolve_default', lambda default, arg: default if arg=='' else arg)



# class AgentConfig:
#     def __init__(self, agent_id, cfg) -> None:
#         self.cfg = copy.deepcopy(cfg)
#         self.agent_id = agent_id

# def generate_agents(num_workers, agent_ids, cfg):
#     """Generates agents in parallel using multiprocessing."""
#     pool = mp.Pool(num_workers)
#     agents_cfg = [AgentConfig(id, cfg) for id in agent_ids]
#     print(f"Generating initial population P={len(agent_ids)} with N={num_workers} workers.")
#     pool.map(generate_agent, agents_cfg)

#     print(f"Generated initial population.")

# def generate_agent(agent_cfg):
#     """Generates an agent if not already generated, and serializes to file."""
#     # Check if agent has already been generated
#     cfg = agent_cfg.cfg
#     agent_id = agent_cfg.agent_id

#     xml_path = fu.id2path(agent_id, subfolder="xml", base_dir=cfg.OUT_DIR)
#     model_path = fu.id2path(agent_id, subfolder="models", base_dir=cfg.OUT_DIR)

#     is_agent_generated = fu.file_exists(xml_path)
#     is_agent_trained = fu.file_exists(model_path)

#     if is_agent_generated and is_agent_trained:
#         print(f"Agent {agent_id} has already been generated and trained.")
#         return

#     if not is_agent_generated:
#         # If agent was not generated, generate xml for unimal.
#         print(f"Generating unimal for {agent_id}.")
#         generate_unimal(xml_path)

#     # Train agent
#     train_agent(xml_path, model_path)

# register the rl-games adapter to use inside the runner
vecenv.register('RLGPU',
                lambda config_name, num_actors, **kwargs: RLGPUEnv(config_name, num_actors, **kwargs))

# register new AMP network builder and agent
def build_runner(algo_observer):
    runner = Runner(algo_observer)
    runner.algo_factory.register_builder('amp_continuous', lambda **kwargs : amp_continuous.AMPAgent(**kwargs))
    runner.player_factory.register_builder('amp_continuous', lambda **kwargs : amp_players.AMPPlayerContinuous(**kwargs))
    runner.model_builder.model_factory.register_builder('continuous_amp', lambda network, **kwargs : amp_models.ModelAMPContinuous(network))  
    runner.model_builder.network_factory.register_builder('amp', lambda **kwargs : amp_network_builder.AMPBuilder())

    return runner


def save_metadata(model_output_dir, unimal_id, max_epochs, train_time, parent_id=None, yacs_cfg=None):
    reg_str = r'.*\[(.*)\].pth'
    model_files = fu.get_files(model_output_dir, reg_str, sort=True, sort_type="time")
    best_model = model_files[-1]
    assert(str(max_epochs+1) in best_model)
    p = re.compile(reg_str)
    result = p.search(best_model)
    reward = result.group(1)

    metadata = {}
    metadata["reward"] = reward
    metadata["id"] = unimal_id
    metadata["train_time"] = train_time

    if parent_id == None or parent_id == 'None':
        metadata["lineage"] = "{}".format(unimal_id)
    else:
        parent_metadata_path = os.path.join(fu.get_subfolder("metadata", config=yacs_cfg), "{}.json".format(parent_id))
        parent_metadata = fu.load_json(parent_metadata_path)
        metadata["lineage"] = "{}/{}".format(parent_metadata["lineage"], unimal_id)

    path = os.path.join(fu.get_subfolder("metadata", config=yacs_cfg), "{}.json".format(unimal_id))
    fu.save_json(metadata, path)
    print(f"Saved metadata to {path}")


def train_agent(hydra_cfg: DictConfig, yacs_cfg=None):
    # ensure checkpoints can be specified as relative paths
    if hydra_cfg.checkpoint:
        hydra_cfg.checkpoint = to_absolute_path(hydra_cfg.checkpoint)

    hydra_cfg_dict = omegaconf_to_dict(hydra_cfg)
    print_dict(hydra_cfg_dict)

    # set numpy formatting for printing only
    set_np_formatting()

    # sets seed. if seed is -1 will pick a random one
    hydra_cfg.seed = set_seed(hydra_cfg.seed, torch_deterministic=hydra_cfg.torch_deterministic)

    # `create_rlgpu_env` is environment construction function which is passed to RL Games and called internally.
    # We use the helper function here to specify the environment config.
    create_rlgpu_env = get_rlgames_env_creator(
        omegaconf_to_dict(hydra_cfg.task),
        hydra_cfg.task_name,
        hydra_cfg.sim_device,
        hydra_cfg.rl_device,
        hydra_cfg.graphics_device_id,
        hydra_cfg.headless,
        multi_gpu=hydra_cfg.multi_gpu,
    )

    env_configurations.register('rlgpu', {
        'vecenv_type': 'RLGPU',
        'env_creator': lambda **kwargs: create_rlgpu_env(**kwargs),
    })

    rlg_config_dict = omegaconf_to_dict(hydra_cfg.train)

    # convert CLI arguments into dictionory
    # create runner and set the settings
    runner = build_runner(RLGPUAlgoObserver())
    runner.load(rlg_config_dict)
    runner.reset()

    # dump config dict
    experiment_dir = os.path.join(hydra_cfg.train.params.config.train_dir, hydra_cfg.train.params.config.name)
    os.makedirs(experiment_dir, exist_ok=True)
    with open(os.path.join(experiment_dir, 'config.yaml'), 'w') as f:
        f.write(OmegaConf.to_yaml(hydra_cfg))

    start = time.time()
    runner.run({
        'train': not hydra_cfg.test,
        'play': hydra_cfg.test,
    })
    end = time.time()
    time_elapsed = end - start

    # Dir where model actually gets saved. IsaacGym creates "nn" subfolder automatically.
    model_output_dir = os.path.join(experiment_dir, 'nn')
    save_metadata(model_output_dir, 
                  hydra_cfg.train.params.config.name, 
                  hydra_cfg.train.params.config.max_epochs,
                  train_time=time_elapsed,
                  parent_id=hydra_cfg.train.params.config.parent_name,
                  yacs_cfg=yacs_cfg)

def generate_unimal(xml_path):
    pass

@hydra.main(config_name="config", config_path="./cfg")
def main(hydra_cfg: DictConfig):
    train_agent(hydra_cfg)

if __name__ == "__main__":
    main()
