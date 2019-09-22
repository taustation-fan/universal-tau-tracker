ALTER TABLE station_pair
    ADD COLUMN fit_period_u DOUBLE PRECISION,
    ADD COLUMN fit_min_radius_km DOUBLE PRECISION,
    ADD COLUMN fit_max_radius_km DOUBLE PRECISION;
