from datetime import datetime
from multiprocessing import Pool
from pathlib import Path
import os
import networkx as nx
import random
import sys
import argparse
import copy

from darei import agent
from darei.config import cfg
from darei.envs.morphology import SymmetricUnimal
from darei.utils import similarity as simu
from darei.utils import sample as su
from darei.utils import file as fu
from darei.utils import evo as eu
from darei.utils import exception as exu

import hydra
from omegaconf import DictConfig, OmegaConf
from hydra.utils import to_absolute_path

from hydra import compose, initialize
from omegaconf import OmegaConf


## OmegaConf & Hydra Config

# Resolvers used in hydra configs (see https://omegaconf.readthedocs.io/en/2.1_branch/usage.html#resolvers)
OmegaConf.register_new_resolver('eq', lambda x, y: x.lower()==y.lower())
OmegaConf.register_new_resolver('contains', lambda x, y: x.lower() in y.lower())
OmegaConf.register_new_resolver('if', lambda pred, a, b: a if pred else b)
# allows us to resolve default arguments which are copied in multiple places in the config. used primarily for
# num_ensv
OmegaConf.register_new_resolver('resolve_default', lambda default, arg: default if arg=='' else arg)

def tournament_evolution(proc_id):
    seed = cfg.RNG_SEED + (cfg.EVO.NUM_TOURNAMENTS_PER_GEN * cfg.EVO.NUM_GENERATIONS*cfg.EVO.CUR_GEN_NUM + proc_id) * 100
    min_searched_space_size = cfg.EVO.CUR_GEN_NUM * cfg.EVO.NUM_TOURNAMENTS_PER_GEN
    max_searched_space_size = min_searched_space_size + cfg.EVO.NUM_TOURNAMENTS_PER_GEN + cfg.EVO.INIT_POPULATION_SIZE

    num_parallel_envs = cfg.NUM_ISAAC_ENVS
    env_spacing = cfg.ISAAC_ENV_SPACING

    # Initialize Hydra config
    initialize(config_path="../cfg")

    cur_pop_size = eu.get_population_size()
    print(f"Cur pop size: {cur_pop_size}, max pop size for gen {cfg.EVO.CUR_GEN_NUM}: {max_searched_space_size}")
    while cur_pop_size < max_searched_space_size:
        su.set_seed(seed, use_strong_seeding=True)
        seed += 1
        parent_metadata = eu.select_parent(min_searched_space_size)
        child_id = "{}-{}-{}".format(
            cfg.NODE_ID, proc_id, datetime.now().strftime("%d-%H-%M-%S")
        )
        parent_id = parent_metadata["id"]
        unimal = SymmetricUnimal(
            child_id, init_path=fu.id2path(parent_id, "unimal_init", config=copy.deepcopy(cfg)),
        )
        unimal.mutate()
        unimal.save()

        asset_filename = fu.id2path(child_id, "xml", config=copy.deepcopy(cfg))
        model_output_dir = os.path.join(cfg.OUT_DIR, "models")
        hydra_config = compose(config_name="config", overrides=[
            "task=Unimal", "headless=True", f"num_envs={num_parallel_envs}", 
            "pipeline=gpu", f"experiment={child_id}", 
            f"assetFileName={asset_filename}", f"output_dir={model_output_dir}", 
            f"env_spacing={env_spacing}", f"parent_name={parent_id}"
        ])

        try:
            agent.train_agent(hydra_config, yacs_cfg=copy.deepcopy(cfg))
            print(f"Generation {cfg.EVO.CUR_GEN_NUM}, trained {child_id}")
        except Exception as e:
            exu.handle_exception(
                e, "ERROR in tournament_evolution::train_agent: {}, process id: {}".format(child_id, proc_id), unimal_id=child_id
            )
        cur_pop_size = eu.get_population_size()


    # # Even though video meta files are removed inside ppo, sometimes it might
    # # fail in between creating video. In such cases, we just remove the video
    # # metadata file as master proc uses absence of meta files as sign of completion.
    # video_dir = fu.get_subfolder("videos")
    # video_meta_files = fu.get_files(
    #     video_dir, "{}-{}-.*json".format(cfg.NODE_ID, idx)
    # )
    # for video_meta_file in video_meta_files:
    #     fu.remove_file(video_meta_file)

def parse_args():
    """Parses the arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cfg", dest="cfg_file", help="Config file", required=True, type=str
    )
    parser.add_argument("--proc_id", required=True, type=int)
    parser.add_argument(
        "opts",
        help="See morphology/config.py for all options",
        default=None,
        nargs=argparse.REMAINDER,
    )
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
    return parser.parse_args()

def main():
    # Parse cmd line args
    args = parse_args()

    # Load config options
    cfg.merge_from_file(args.cfg_file)
    cfg.merge_from_list(args.opts)

    # Unclear why this happens, very rare
    if cfg.OUT_DIR == "/tmp":
        exu.handle_exception("", "ERROR TMP")

    tournament_evolution(args.proc_id)
    print("Node ID: {}, Proc ID: {} finished.".format(cfg.NODE_ID, args.proc_id))


if __name__ == "__main__":
    main()
