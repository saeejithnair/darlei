from datetime import datetime
from distutils.command.config import config
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

def init_done(unimal_id):
    # unimal_idx = int(unimal_id.split(".")[0].split("-")[1])
    success_metadata = fu.get_files(fu.get_subfolder("metadata", config=copy.deepcopy(cfg)), ".*json")
    error_metadata = fu.get_files(fu.get_subfolder("error_metadata", config=copy.deepcopy(cfg)), ".*json")
    done_metadata = success_metadata + error_metadata
    done_ids = [
        path.split("/")[-1].split(".")[0]
        for path in done_metadata
    ]
    if unimal_id in done_ids:
        return True
    else:
        return False

def init_population(proc_id):
    # Divide work by num nodes and then num procs
    xml_paths = fu.get_files(
        fu.get_subfolder("xml", config=copy.deepcopy(cfg)), ".*xml", sort=True, sort_type="time"
    )[: cfg.EVO.INIT_POPULATION_SIZE]
    xml_paths.sort()
    num_workers = (cfg.EVO.NUM_GPUS * cfg.EVO.NUM_WORKERS_PER_GPU)
    xml_paths = fu.chunkify(xml_paths, cfg.NUM_NODES)[cfg.NODE_ID]
    xml_paths = fu.chunkify(xml_paths, num_workers)[proc_id]

    num_parallel_envs = cfg.NUM_ISAAC_ENVS
    env_spacing = cfg.ISAAC_ENV_SPACING
    horizon_length = cfg.ISAAC_HORIZON_LENGTH

    initialize(config_path="../cfg")

    for xml_path in xml_paths:
        unimal_id = fu.path2id(xml_path)

        if init_done(unimal_id):
            print("{} already done, proc_id: {}".format(unimal_id, proc_id))
            continue
        
        asset_filename = fu.id2path(unimal_id, "xml", config=copy.deepcopy(cfg))
        model_output_dir = os.path.join(cfg.OUT_DIR, "models")
        hydra_config = compose(config_name="config", overrides=[
            "task=Unimal", "headless=True", f"num_envs={num_parallel_envs}", 
            "pipeline=gpu", f"experiment={unimal_id}", 
            f"assetFileName={asset_filename}", f"output_dir={model_output_dir}", 
            f"env_spacing={env_spacing}", f"horizon_length={horizon_length}"
        ])

        try:
            agent.train_agent(hydra_config, yacs_cfg=copy.deepcopy(cfg))
        except Exception as e:
            exu.handle_exception(
                e, "ERROR in init_population::train_agent: {}, process id: {}".format(unimal_id, proc_id), unimal_id=unimal_id
            )

        if eu.get_population_size() >= cfg.EVO.INIT_POPULATION_SIZE:
            break

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

    init_population(args.proc_id)
    print("Node ID: {}, Proc ID: {} finished.".format(cfg.NODE_ID, args.proc_id))


if __name__ == "__main__":
    main()
