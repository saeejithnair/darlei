import numpy as np
import os
from pathlib import Path
import copy
import argparse
import sys
import multiprocessing as mp
import subprocess

from darei.utils import file as fu
from darei.config import cfg, dump_cfg
from darei.tools import evolution
from darei.utils import evo as eu
import time
import signal

class DAREI:
    def __init__(self) -> None:
        pass

    def run(self):
        if cfg.NODE_ID == 0:
            self.setup_population()
        else:
            self.wait_till_init()

        self.init_population()

        self.run_tournament()

    def launch_subproc(self, proc_id, script_name, additional_args=""):
        cfg_path = os.path.join(cfg.OUT_DIR, cfg.CFG_DEST)
        cfg_path = os.path.abspath(cfg_path)
        gpu_device_idx = (proc_id % cfg.EVO.NUM_GPUS)
        cuda_selection = f"CUDA_VISIBLE_DEVICES={gpu_device_idx}"
        cwd = os.path.dirname(os.path.realpath(__file__)) 
        cmd = "{} python {} --cfg {} --proc_id {} NODE_ID {} {}".format(
            cuda_selection, script_name, cfg_path, proc_id, 
            cfg.NODE_ID, additional_args
        )
        print(f"Launching cmd: {cmd}")
        p = subprocess.Popen(
            cmd, shell=True, executable="/bin/bash", preexec_fn=os.setsid,
            cwd=cwd
        )
        return p

    def kill_pg(self, p):
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGTERM)
        except ProcessLookupError:
            pass


    def relaunch_proc(self, p, proc_id, script_name, additional_args=""):
        # Kill the process group
        self.kill_pg(p)
        # Launch the subproc again
        print("Node ID: {}, proc-id: {} relaunching {}".format(
            cfg.NODE_ID, proc_id, script_name))
        p = self.launch_subproc(proc_id, script_name, additional_args)
        return p


    def wait_or_kill(self, subprocs, search_space_size, script_name, additional_args=""):
        # Main process will wait till we have done search
        while eu.get_population_size() < search_space_size:
            time.sleep(10)  # 10 secs

            # Re-launch subproc if exit was due to error
            new_subprocs = []
            for idx in range(len(subprocs)):
                p, proc_id = subprocs[idx]
                poll = p.poll()

                is_error_path = os.path.join(
                    cfg.OUT_DIR, "{}_{}".format(cfg.NODE_ID, p.pid)
                )
                if os.path.exists(is_error_path) or poll:
                    fu.remove_file(is_error_path)
                    p = self.relaunch_proc(p, proc_id, script_name, additional_args)

                new_subprocs.append((p, proc_id))

            subprocs = new_subprocs

        # if eu.should_save_video():
        #     video_dir = fu.get_subfolder("videos")
        #     reg_str = "{}-.*json".format(cfg.NODE_ID)
        #     while len(fu.get_files(video_dir, reg_str)) > 0:
        #         time.sleep(60)

        # Ensure that all process will close, dangling process will prevent docker
        # from exiting.
        for p, _ in subprocs:
            self.kill_pg(p)


    def init_population(self):
        """Trains generated unimals from initial population and serializes 
        model controllers to disk.
        """
        num_workers = (cfg.EVO.NUM_GPUS * cfg.EVO.NUM_WORKERS_PER_GPU)
        subprocs = []
        script_name = "tools/init_population.py"

        additional_args = f"NUM_ISAAC_ENVS {cfg.NUM_ISAAC_ENVS} ISAAC_ENV_SPACING {cfg.ISAAC_ENV_SPACING}"
        print(f"Launching {num_workers} workers to initialize population.")
        for idx in range(num_workers):
            p = self.launch_subproc(idx, script_name, additional_args)
            subprocs.append((p, idx))

        self.wait_or_kill(subprocs, search_space_size=cfg.EVO.INIT_POPULATION_SIZE,
            script_name=script_name, additional_args=additional_args)

    def run_tournament(self):
        num_workers = (cfg.EVO.NUM_GPUS * cfg.EVO.NUM_WORKERS_PER_GPU)
        subprocs = []
        script_name = "tools/tournament_evolution.py"
        additional_args = f"NUM_ISAAC_ENVS {cfg.NUM_ISAAC_ENVS} ISAAC_ENV_SPACING {cfg.ISAAC_ENV_SPACING}"
        for cur_gen_idx in range(cfg.EVO.NUM_GENERATIONS):
            updated_args = f"{additional_args} EVO.CUR_GEN_NUM {cur_gen_idx}"
            for idx in range(num_workers):
                p = self.launch_subproc(idx, script_name, additional_args=updated_args)
                subprocs.append((p, idx))

            max_searched_space_size = (cfg.EVO.INIT_POPULATION_SIZE + 
                (cur_gen_idx + 1) * cfg.EVO.NUM_TOURNAMENTS_PER_GEN)

            self.wait_or_kill(subprocs, search_space_size=max_searched_space_size,
                script_name=script_name, additional_args=updated_args)

    def setup_population(self):
        """Generates unimals in initial population and serializes to disk in 
        XML format.
        """
        init_setup_path = os.path.join(cfg.OUT_DIR, "init_setup_done")

        if fu.file_exists(init_setup_path):
            print(f"Population has already been setup.")
            return

        # Creates models of all unimals in initial population.
        evolution.create_init_unimals()

        # Indicates that population has been already created.
        Path(init_setup_path).touch()
        print(f"Setup population.")

    def wait_till_init(self):
        init_setup_done_path = os.path.join(cfg.OUT_DIR, "init_setup_done")
        max_wait = 3600  # one hour
        time_waited = 0
        while not os.path.exists(init_setup_done_path):
            time.sleep(60)
            time_waited += 60
            if time_waited >= max_wait:
                print("Initial xmls not made. Exiting!")
                sys.exit(1)



def setup_output_dir():
    os.makedirs(cfg.OUT_DIR, exist_ok=True)
    # Make subfolders
    subfolders = [
        "models",
        "metadata",
        "xml",
        "unimal_init",
        "rewards",
        "videos",
        "error_metadata",
        "images",
    ]
    for folder in subfolders:
        os.makedirs(os.path.join(cfg.OUT_DIR, folder), exist_ok=True)


def parse_args():
    """Parses the arguments."""
    parser = argparse.ArgumentParser(description="Train a RL agent")
    parser.add_argument(
        "--cfg", dest="cfg_file", help="Config file", required=True, type=str
    )
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

def calculate_max_iters():
    # Iter here refers to 1 cycle of experience collection and policy update.
    cfg.PPO.MAX_ITERS = (
        int(cfg.PPO.MAX_STATE_ACTION_PAIRS)
        // cfg.PPO.TIMESTEPS
        // cfg.PPO.NUM_ENVS
    )

def main():
    # Parse cmd line args
    args = parse_args()

    # Load config options
    cfg.merge_from_file(args.cfg_file)
    cfg.merge_from_list(args.opts)
    # Infer OPTIM.MAX_ITERS
    calculate_max_iters()
    setup_output_dir()
    cfg.freeze()

    # Save the config
    dump_cfg()

    darei = DAREI()
    darei.run()


if __name__ == "__main__":
    main()
