import numpy as np
from scipy.optimize import least_squares

def run_network_adjustment(active_tree_numbers, tree_to_idx, idx_to_tree, trees_dict, measurements):
    """Executes high-precision nonlinear least-squares coordinate projections."""
    num_active_trees = len(active_tree_numbers)
    initial_coordinates = np.zeros(num_active_trees * 2)

    for t_num, (gx, gy) in trees_dict.items():
        i = tree_to_idx[t_num]
        initial_coordinates[2*i] = gx
        initial_coordinates[2*i+1] = gy

    def error_function(coords):
        residuals = []
        t1_idx = tree_to_idx.get(1, 0)
        t2_idx = tree_to_idx.get(2, 1)
        
        # Heavy virtual anchoring penalty system
        residuals.append(coords[2*t1_idx] * 10000)      # Lock Tree 1 X to 0
        residuals.append(coords[2*t1_idx+1] * 10000)    # Lock Tree 1 Y to 0
        residuals.append(coords[2*t2_idx+1] * 10000)    # Lock Tree 2 Y to 0
        
        for u, v, d_measured in measurements:
            idx_u, idx_v = tree_to_idx[u] * 2, tree_to_idx[v] * 2
            x_u, y_u = coords[idx_u], coords[idx_u+1]
            x_v, y_v = coords[idx_v], coords[idx_v+1]
            
            d_calculated = np.sqrt((x_u - x_v)**2 + (y_u - y_v)**2)
            residuals.append(d_calculated - d_measured)
        return np.array(residuals)

    result = least_squares(error_function, initial_coordinates, method='trf', ftol=1e-10, xtol=1e-10)
    final_coords = result.x

    x_coords = {idx_to_tree[i]: final_coords[2*i] for i in range(num_active_trees)}
    y_coords = {idx_to_tree[i]: final_coords[2*i+1] for i in range(num_active_trees)}
    
    return x_coords, y_coords
