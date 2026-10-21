import os

DATA_FILE = "survey_data.csv"
TREES_FILE = "active_trees.csv"

def init_files():
    """Seeds defaults for base maps on very first load if files do not exist."""
    if not os.path.exists(TREES_FILE):
        with open(TREES_FILE, "w") as f:
            f.write("tree,x,y\n")
            f.write("1,0.0,0.0\n")   # Tree 1 origin
            f.write("2,3.0,0.0\n")   # Tree 2 horizontal anchor
            f.write("3,0.0,4.0\n")   # Tree 3 perpendicular point

    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            f.write("tree_a,tree_b,distance\n")
            f.write("1,2,3.00\n")   # 3-4-5 Starter Triangle Baseline
            f.write("2,3,5.00\n")
            f.write("1,3,4.00\n")

def load_trees():
    """Reads coordinates dictionary from disk storage ledger."""
    trees_dict = {}
    with open(TREES_FILE, "r") as f:
        next(f)
        for line in f:
            if line.strip():
                t_num, gx, gy = line.strip().split(",")
                trees_dict[int(t_num)] = (float(gx), float(gy))
    return trees_dict

def save_trees(trees_dict):
    """Completely rewrites active positions file on update triggers."""
    with open(TREES_FILE, "w") as f:
        f.write("tree,x,y\n")
        for t_id, (x, y) in sorted(trees_dict.items()):
            f.write(f"{t_id},{x},{y}\n")

def load_measurements(trees_dict):
    """Parses existing physical tape records, filtering orphaned entries."""
    measurements = []
    with open(DATA_FILE, "r") as f:
        next(f)
        for line in f:
            if line.strip():
                u, v, d = line.strip().split(",")
                if int(u) in trees_dict and int(v) in trees_dict:
                    measurements.append((int(u), int(v), float(d)))
    return measurements

def save_measurements(measurements):
    """Completely rewrites measurement logs on modifications or removals."""
    with open(DATA_FILE, "w") as f:
        f.write("tree_a,tree_b,distance\n")
        for u, v, d in measurements:
            f.write(f"{u},{v},{d}\n")

def append_measurement(u, v, d):
    """Quick append optimization directly to tape log backend files."""
    with open(DATA_FILE, "a") as f:
        f.write(f"{int(u)},{int(v)},{float(d)}\n")
