from datetime import datetime
from multiprocessing import Pool
from pathlib import Path
import os
import networkx as nx
import random
import copy

from darei.config import cfg
from darei.envs.morphology import SymmetricUnimal
from darei.utils import similarity as simu
from darei.utils import sample as su
from darei.utils import file as fu

def limb_count_pop_init(idx, unimal_id):
    # Build unimals which initialize the population based on number of limbs.
    unimal = SymmetricUnimal(unimal_id)
    num_limbs = su.sample_from_range(cfg.LIMB.NUM_LIMBS_RANGE)
    unimal.mutate(op="grow_limb")
    while unimal.num_limbs < num_limbs:
        unimal.mutate()

    unimal.save()
    return unimal_id


def create_init_unimals():
    init_setup_done_path = os.path.join(cfg.OUT_DIR, "init_setup_done")

    if os.path.isfile(init_setup_done_path):
        print("Init xmls have already been.")
        return

    init_pop_size = cfg.EVO.INIT_POPULATION_SIZE

    # Create unimal xmls. Note that 10*init_pop_size unimals are created for
    # diversity. We remove the ones that are too similar.
    # Generate all unimals on a single node but parallelize using processes.
    p = Pool(cfg.EVO.NUM_CPU_PROCESSES)
    timestamp = datetime.now().strftime("%d-%H-%M-%S")
    idx_unimal_id = [
        (idx, "{}-{}-{}".format(cfg.NODE_ID, idx, timestamp))
        for idx in range(10 * init_pop_size)
    ]

    unimal_ids = p.starmap(globals()[cfg.EVO.INIT_METHOD], idx_unimal_id)

    # Create graph of initial population.
    G = simu.create_graph_from_uids(
        None, unimal_ids, "geom_orientation", graph_type="species", 
        cfg=copy.deepcopy(cfg)
    )
    cc = list(nx.connected_components(G))

    # Remove unimals that are too similar to each other.
    unimals_to_remove = []
    unimals_to_keep = []
    for same_unimals in cc:
        if len(same_unimals) == 1:
            unimals_to_keep.extend(list(same_unimals))
            continue
        remove_unimals = sorted(
            list(same_unimals),
            key=lambda unimal_id: "-".join(unimal_id.split("-")[:2]),
        )
        unimals_to_keep.append(remove_unimals[0])
        remove_unimals = remove_unimals[1:]
        unimals_to_remove.extend(remove_unimals)

    # Number of unimals to add to achieve init_pop_size.
    padding_count = init_pop_size - len(cc)
    if padding_count > 0:
        random.shuffle(unimals_to_remove)
        unimals_to_remove = unimals_to_remove[padding_count:]
    else:
        random.shuffle(unimals_to_keep)
        unimals_to_remove.extend(unimals_to_keep[init_pop_size:])

    for unimal in unimals_to_remove:
        fu.remove_file(fu.id2path(unimal, "xml", config=copy.deepcopy(cfg)))
        fu.remove_file(fu.id2path(unimal, "unimal_init", config=copy.deepcopy(cfg)))
        fu.remove_file(fu.id2path(unimal, "images", config=copy.deepcopy(cfg)))

    Path(init_setup_done_path).touch()
    print("Finished creating init xmls.")

