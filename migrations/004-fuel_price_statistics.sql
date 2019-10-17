DROP VIEW fuel_price_statistics;
CREATE OR REPLACE VIEW fuel_price_statistics (station_id, station_name, station_short_name, station_level, system_name, last_reading, min_price, max_price, last_price) AS
WITH fuel_price_reading_grouped AS (
    SELECT station_id,
           MAX("when") AS last_timestamp,
           MIN(price_per_g) AS min_price,
           MAX(price_per_g) AS max_price
    FROM fuel_price_reading 
    GROUP BY station_id
)
SELECT station.id,
       station.name,
       station.short,
       station.level,
       system.name,
       fuel_price_reading_grouped.last_timestamp, 
       fuel_price_reading_grouped.min_price,
       fuel_price_reading_grouped.max_price,
       fuel_price_reading.price_per_g AS last_price
  FROM station
  JOIN system ON station.system_id = system.id
  JOIN fuel_price_reading_grouped
       ON station.id = fuel_price_reading_grouped.station_id
  JOIN fuel_price_reading
       ON station.id = fuel_price_reading.station_id AND fuel_price_reading."when" = fuel_price_reading_grouped.last_timestamp;
