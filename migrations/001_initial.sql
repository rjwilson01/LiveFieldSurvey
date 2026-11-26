CREATE TABLE IF NOT EXISTS dataset_serial_counters (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    next_serial INTEGER NOT NULL CHECK (next_serial > 0)
);

INSERT INTO dataset_serial_counters (singleton, next_serial)
VALUES (TRUE, 1)
ON CONFLICT (singleton) DO NOTHING;

CREATE TABLE IF NOT EXISTS survey_datasets (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL,
    serial INTEGER NOT NULL UNIQUE CHECK (serial > 0),
    dataset_id TEXT NOT NULL UNIQUE,
    next_tree_id INTEGER NOT NULL DEFAULT 3 CHECK (next_tree_id >= 3),
    map_axis_layout TEXT NOT NULL DEFAULT 'X horizontal, Y vertical',
    mirror_map_x BOOLEAN NOT NULL DEFAULT FALSE,
    mirror_map_y BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS survey_trees (
    dataset_id BIGINT NOT NULL REFERENCES survey_datasets(id) ON DELETE CASCADE,
    tree_id INTEGER NOT NULL CHECK (tree_id > 0),
    x INTEGER NOT NULL DEFAULT 0 CHECK (x >= 0),
    y INTEGER NOT NULL DEFAULT 0 CHECK (y >= 0),
    PRIMARY KEY (dataset_id, tree_id)
);

CREATE TABLE IF NOT EXISTS survey_measurements (
    record_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_id BIGINT NOT NULL REFERENCES survey_datasets(id) ON DELETE CASCADE,
    tree_a INTEGER NOT NULL,
    tree_b INTEGER NOT NULL,
    distance_mm DOUBLE PRECISION NOT NULL CHECK (distance_mm > 0),
    CHECK (tree_a <> tree_b),
    UNIQUE (dataset_id, tree_a, tree_b),
    FOREIGN KEY (dataset_id, tree_a) REFERENCES survey_trees(dataset_id, tree_id) ON DELETE CASCADE,
    FOREIGN KEY (dataset_id, tree_b) REFERENCES survey_trees(dataset_id, tree_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS survey_measurements_dataset_pair_idx
    ON survey_measurements (dataset_id, tree_a, tree_b);
