ALTER TABLE station_pair RENAME COLUMN fit_min_radius_km TO fit_min_distance_km;
ALTER TABLE station_pair RENAME COLUMN fit_max_radius_km TO fit_max_distance_km;
ALTER TABLE station_pair ADD COLUMN fit_phase DOUBLE PRECISION;
