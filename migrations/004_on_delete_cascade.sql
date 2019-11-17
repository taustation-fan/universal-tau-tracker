ALTER TABLE career_task_reading
        DROP CONSTRAINT career_task_reading_batch_submission_id_fkey,
        ADD  CONSTRAINT career_task_reading_batch_submission_id_fkey
            FOREIGN KEY (batch_submission_id) REFERENCES career_batch_submission (id)
            ON DELETE CASCADE;

ALTER TABLE career_task_reading
        DROP CONSTRAINT career_task_reading_career_task_id_fkey,
        ADD CONSTRAINT career_task_reading_career_task_id_fkey
            FOREIGN KEY (career_task_id) REFERENCES career_task (id)
            ON DELETE CASCADE;

ALTER TABLE station_distance_reading
    DROP CONSTRAINT station_distance_reading_station_pair_id_fkey,
    ADD CONSTRAINT station_distance_reading_station_pair_id_fkey
        FOREIGN KEY (station_pair_id) REFERENCES station_pair (id)
            ON DELETE CASCADE;

ALTER TABLE station_pair
    DROP CONSTRAINT station_pair_station_a_id_fkey,
    ADD CONSTRAINT station_pair_station_a_id_fkey
        FOREIGN KEY (station_a_id) REFERENCES station (id)
            ON DELETE CASCADE;

ALTER TABLE station_pair
    DROP CONSTRAINT station_pair_station_b_id_fkey,
    ADD CONSTRAINT station_pair_station_b_id_fkey
        FOREIGN KEY (station_b_id) REFERENCES station (id)
            ON DELETE CASCADE;
